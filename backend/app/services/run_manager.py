"""Runs agent workflows in the background and persists their progress.

* Run records (status, events, results) are saved as JSON in data/runs/.
* LangGraph state is checkpointed in SQLite, so a run waiting for human
  approval can be resumed even after the server restarts.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from langgraph.types import Command

from ..agent.context import RunContext, drop_context, get_context, register_context, set_event_sink
from ..agent.graph import build_graph, initial_state, normalize_config, sqlite_checkpointer, summarize_result
from ..agent.nodes.human_review import MAX_HUMAN_ROUNDS
from ..config import get_settings
from .llm_base import LLMAuthError, LLMError, LLMNotConfiguredError, LLMQuotaError

logger = logging.getLogger(__name__)

TERMINAL = {"completed", "completed_with_issues", "no_results", "failed"}
WAITING = {"awaiting_approval"}


class RunNotFound(Exception):
    pass


class RunConflict(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    """Thread-safe JSON-file store for run records."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._runs: dict[str, dict] = {}
        for path in self.dir.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                self._runs[record["run_id"]] = record
            except (OSError, json.JSONDecodeError, KeyError):
                logger.warning("Skipping unreadable run file %s", path)

    def _save(self, record: dict) -> None:
        path = self.dir / f"{record['run_id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, default=str), encoding="utf-8")
        tmp.replace(path)

    def create(self, record: dict) -> dict:
        with self._lock:
            self._runs[record["run_id"]] = record
            self._save(record)
            return record

    def get(self, run_id: str) -> dict:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                raise RunNotFound(run_id)
            return json.loads(json.dumps(record, default=str))  # defensive copy

    def update(self, run_id: str, **fields) -> dict:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                raise RunNotFound(run_id)
            record.update(fields)
            record["updated_at"] = _now()
            self._save(record)
            return record

    def delete(self, run_id: str) -> bool:
        with self._lock:
            if run_id not in self._runs:
                raise RunNotFound(run_id)
            del self._runs[run_id]
            path = self.dir / f"{run_id}.json"
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
            return True

    def add_event(self, run_id: str, event: dict) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return
            if event.get("step") == "data":
                partial = (event.get("data") or {}).get("partial") or {}
                if not isinstance(record.get("result"), dict):
                    record["result"] = {}
                record["result"].update(partial)
            else:
                event = {**event, "id": len(record["events"])}
                record["events"].append(event)
            record["updated_at"] = _now()
            self._save(record)

    def list(self, limit: int = 20) -> list[dict]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda r: r.get("created_at", ""), reverse=True)[:limit]
            return [
                {k: r.get(k) for k in ("run_id", "goal", "status", "created_at", "updated_at")}
                | {"subject": ((r.get("result") or {}).get("newsletter") or {}).get("subject")}
                for r in runs
            ]

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._runs.values())


class RunManager:
    def __init__(self, store: RunStore | None = None, graph=None, max_workers: int = 2,
                 executor_submit: Callable | None = None):
        settings = get_settings()
        self.store = store or RunStore(Path(settings.data_dir) / "runs")
        self.graph = graph or build_graph(sqlite_checkpointer())
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="agent")
        self._submit = executor_submit or self._executor.submit
        set_event_sink(self.store.add_event)
        self._recover_interrupted_runs()

    def _recover_interrupted_runs(self) -> None:
        for record in self.store.all():
            if record.get("status") in ("queued", "running"):
                self.store.update(record["run_id"], status="failed",
                                  error="The server restarted while this run was in progress. Please start it again.")

    # -- helpers ---------------------------------------------------------
    def _thread(self, run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 60}

    def _execute(self, run_id: str, payload) -> None:
        self.store.update(run_id, status="running", error=None)
        try:
            self.graph.invoke(payload, self._thread(run_id))
            result = summarize_result(self.graph, run_id)
            ctx = get_context(run_id)
            result["llm_calls"] = ctx.llm_calls
            status = result["status"]
            self.store.update(run_id, status=status, result=result, message=result.get("message"))
            if status == "awaiting_approval":
                self.store.add_event(run_id, {
                    "step": "approval", "status": "waiting", "ts": _now(), "data": {},
                    "message": "Draft ready. Waiting for your approval or change requests.",
                })
            else:
                drop_context(run_id)
        except (LLMQuotaError, LLMAuthError, LLMNotConfiguredError) as exc:
            self._fail(run_id, str(exc))
        except LLMError as exc:
            self._fail(run_id, f"Model provider error: {exc}")
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Run %s failed", run_id)
            self._fail(run_id, f"Unexpected error: {exc.__class__.__name__}: {exc}")

    def _fail(self, run_id: str, message: str) -> None:
        try:
            partial = summarize_result(self.graph, run_id)
        except Exception:
            partial = None
        self.store.add_event(run_id, {"step": "error", "status": "failed", "message": message, "ts": _now(), "data": {}})
        update = {"status": "failed", "error": message}
        if partial:
            partial["status"] = "failed"
            update["result"] = partial
        self.store.update(run_id, **update)
        drop_context(run_id)

    # -- public API ------------------------------------------------------
    def start(self, goal: str, options: dict) -> dict:
        settings = get_settings()
        cfg = normalize_config(options)
        if not settings.provider_configured(cfg["provider"]):
            raise LLMNotConfiguredError(
                f"Provider '{cfg['provider']}' is not configured on the server. "
                + {"gemini": "Add GEMINI_API_KEY to backend/.env (free key at https://aistudio.google.com/apikey).",
                   "openai": "Add OPENAI_API_KEY to backend/.env (paid API usage).",
                   "ollama": "Install Ollama, pull a model and set OLLAMA_ENABLED=true."}.get(cfg["provider"], ""),
                cfg["provider"],
            )
        run_id = uuid.uuid4().hex
        ctx = RunContext(run_id, cfg["provider"], sink=self.store.add_event)
        if ctx.llm is None:
            raise LLMNotConfiguredError(ctx.llm_error or "Model provider unavailable", cfg["provider"])
        register_context(ctx)
        record = {
            "run_id": run_id,
            "goal": goal,
            "config": cfg,
            "status": "queued",
            "message": "",
            "error": None,
            "created_at": _now(),
            "updated_at": _now(),
            "events": [],
            "result": {},
        }
        self.store.create(record)
        self._submit(self._execute, run_id, initial_state(run_id, goal, cfg))
        return record

    def get(self, run_id: str) -> dict:
        return self.store.get(run_id)

    def _require_waiting(self, run_id: str) -> dict:
        record = self.store.get(run_id)
        if record["status"] != "awaiting_approval":
            raise RunConflict(f"Run is '{record['status']}', not awaiting approval.")
        return record

    def approve(self, run_id: str) -> dict:
        self._require_waiting(run_id)
        self.store.update(run_id, status="running")
        self._submit(self._execute, run_id, Command(resume={"action": "approve"}))
        return self.store.get(run_id)

    def revise(self, run_id: str, feedback: str) -> dict:
        record = self._require_waiting(run_id)
        rounds = int((record.get("result") or {}).get("human_rounds") or 0)
        if rounds >= MAX_HUMAN_ROUNDS:
            raise RunConflict(f"Maximum of {MAX_HUMAN_ROUNDS} change requests reached. Please approve the draft.")
        get_context(run_id, record["config"].get("provider"))  # rebuild after restart if needed
        self.store.update(run_id, status="running")
        self._submit(self._execute, run_id, Command(resume={"action": "revise", "feedback": feedback}))
        return self.store.get(run_id)

    def output_path(self, run_id: str, fmt: str) -> Path:
        record = self.store.get(run_id)
        output = (record.get("result") or {}).get("output")
        if not output:
            raise RunConflict("This run has no saved newsletter yet.")
        key = {"html": "html", "markdown": "markdown", "md": "markdown", "json": "metadata"}.get(fmt)
        if key is None:
            raise ValueError("format must be html, markdown or json")
        directory = Path(output["directory"]).resolve()
        path = (directory / output["files"][key]).resolve()
        if directory not in path.parents or not path.exists():
            raise RunConflict("Saved file not found on the server.")
        return path

    def delete(self, run_id: str) -> bool:
        drop_context(run_id)
        try:
            record = self.store.get(run_id)
            output = (record.get("result") or {}).get("output")
            if output and "files" in output and "directory" in output:
                directory = Path(output["directory"]).resolve()
                for f in output["files"].values():
                    fp = (directory / f).resolve()
                    if directory in fp.parents and fp.exists():
                        try:
                            fp.unlink()
                        except OSError:
                            pass
        except Exception:
            pass
        return self.store.delete(run_id)


_manager: RunManager | None = None


def get_manager() -> RunManager:
    global _manager
    if _manager is None:
        _manager = RunManager()
    return _manager
