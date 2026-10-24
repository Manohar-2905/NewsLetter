"""Tool: save_newsletter — writes the newsletter to the output folder safely.

Both HTML and Markdown are saved (rendering is free), plus a JSON file with
sources and the review report. File names are slugified and confined to the
output directory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..utils.text import slugify

EXTENSIONS = {"html": "html", "markdown": "md", "md": "md"}


def _safe_path(directory: Path, filename: str) -> Path:
    path = (directory / filename).resolve()
    if directory.resolve() not in path.parents:
        raise ValueError("Refusing to write outside the output directory")
    return path


def save_newsletter(
    newsletter: dict,
    output_format: str = "html",
    run_id: str = "",
    review: dict | None = None,
    output_dir: str | None = None,
) -> dict:
    directory = Path(output_dir or get_settings().output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}_{slugify(newsletter.get('title') or 'newsletter', 40)}_{(run_id or 'local')[:8]}"

    files = {}
    html_path = _safe_path(directory, f"{base}.html")
    html_path.write_text(newsletter["html"], encoding="utf-8")
    files["html"] = html_path.name
    md_path = _safe_path(directory, f"{base}.md")
    md_path.write_text(newsletter["markdown"], encoding="utf-8")
    files["markdown"] = md_path.name

    meta = {
        "run_id": run_id,
        "subject": newsletter.get("subject"),
        "title": newsletter.get("title"),
        "generated_at": newsletter.get("generated_at"),
        "primary_format": output_format,
        "sources": [
            {k: s.get(k) for k in ("headline", "publisher", "published_at", "url", "based_on")}
            for s in newsletter.get("sections", [])
        ],
        "review": review,
        "files": files,
    }
    meta_path = _safe_path(directory, f"{base}.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    files["metadata"] = meta_path.name

    primary_key = "markdown" if output_format in ("markdown", "md") else "html"
    return {
        "directory": str(directory),
        "files": files,
        "primary_file": files[primary_key],
        "primary_format": primary_key,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
