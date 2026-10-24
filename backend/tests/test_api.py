"""API tests using FastAPI's TestClient. Runs execute synchronously in tests."""

import pytest
from fastapi.testclient import TestClient

import app.services.run_manager as rm
from app.agent.context import RunContext
from app.agent.graph import build_graph
from tests.conftest import FakeLLM


@pytest.fixture
def client(monkeypatch, mock_research, tmp_path):
    llm = FakeLLM()

    def fake_context(run_id, provider, sink=None, **kw):
        return RunContext(run_id, provider, llm=llm, sink=sink, build_models=False)

    monkeypatch.setattr(rm, "RunContext", fake_context)
    manager = rm.RunManager(store=rm.RunStore(tmp_path / "runs"), graph=build_graph(),
                            executor_submit=lambda fn, *args: fn(*args))  # run inline
    monkeypatch.setattr(rm, "_manager", manager)
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health_and_config(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    cfg = client.get("/api/config").json()
    assert cfg["default_provider"] == "gemini"
    assert "test-key" not in str(cfg)  # secrets never exposed


@pytest.mark.parametrize("payload", [{"goal": ""}, {"goal": "   "}, {"goal": "!!!"}, {"goal": "ai news", "article_count": 20},
                                     {"goal": "ai news", "output_format": "pdf"}])
def test_invalid_requests(client, payload):
    assert client.post("/api/agent/run", json=payload).status_code == 422


def test_autonomous_run_and_download(client):
    resp = client.post("/api/agent/run", json={"goal": "Agentic AI and autonomous coding agents", "article_count": 5})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    status = client.get(f"/api/agent/{run_id}").json()
    assert status["status"] == "completed"
    assert status["result"]["newsletter"]["subject"]
    assert len(status["result"]["articles"]) == 5
    steps = {e["step"] for e in status["events"]}
    assert {"planning", "research", "selection", "summarization", "writing", "review", "saving"} <= steps
    html = client.get(f"/api/agent/{run_id}/download?format=html")
    assert html.status_code == 200 and "<html" in html.text
    md = client.get(f"/api/agent/{run_id}/download?format=markdown")
    assert md.status_code == 200 and md.text.startswith("# ")
    assert client.get(f"/api/agent/{run_id}/download?format=exe").status_code == 422


def test_sse_stream(client):
    run_id = client.post("/api/agent/run", json={"goal": "Agentic AI news"}).json()["run_id"]
    with client.stream("GET", f"/api/agent/{run_id}/events") as resp:
        body = "".join(resp.iter_text())
    assert "event: progress" in body
    assert "event: end" in body


def test_hitl_approve_and_revise_endpoints(client):
    run_id = client.post("/api/agent/run", json={"goal": "Agentic AI news", "mode": "hitl"}).json()["run_id"]
    assert client.get(f"/api/agent/{run_id}").json()["status"] == "awaiting_approval"
    assert client.get(f"/api/agent/{run_id}/download").status_code == 409  # not saved yet

    assert client.post(f"/api/agent/{run_id}/revise", json={"feedback": "x"}).status_code == 422
    revised = client.post(f"/api/agent/{run_id}/revise", json={"feedback": "Use a more casual tone"})
    assert revised.status_code == 200
    assert client.get(f"/api/agent/{run_id}").json()["status"] == "awaiting_approval"

    approved = client.post(f"/api/agent/{run_id}/approve")
    assert approved.status_code == 200
    final = client.get(f"/api/agent/{run_id}").json()
    assert final["status"] == "completed"
    assert final["downloads"]["html"]
    # approving again is a conflict
    assert client.post(f"/api/agent/{run_id}/approve").status_code == 409


def test_unknown_run(client):
    assert client.get("/api/agent/doesnotexist").status_code == 404
    assert client.post("/api/agent/doesnotexist/approve").status_code == 404


def test_provider_not_configured(client):
    resp = client.post("/api/agent/run", json={"goal": "Agentic AI news", "provider": "openai"})
    assert resp.status_code == 400
    assert "OPENAI_API_KEY" in resp.json()["detail"]


def test_runs_persist_in_store(client, tmp_path):
    run_id = client.post("/api/agent/run", json={"goal": "Agentic AI news"}).json()["run_id"]
    store = rm.RunStore(tmp_path / "runs")  # fresh store reads JSON from disk
    assert store.get(run_id)["status"] == "completed"
    assert client.get("/api/agent/runs").json()[0]["run_id"] == run_id


def test_delete_run(client):
    run_id = client.post("/api/agent/run", json={"goal": "Agentic AI news"}).json()["run_id"]
    assert client.get(f"/api/agent/{run_id}").status_code == 200

    del_resp = client.delete(f"/api/agent/{run_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"status": "deleted", "run_id": run_id}

    assert client.get(f"/api/agent/{run_id}").status_code == 404
    assert client.delete(f"/api/agent/{run_id}").status_code == 404

