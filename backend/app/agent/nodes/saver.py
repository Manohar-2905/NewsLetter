"""Output: save the newsletter and 'send' it (simulated)."""

from __future__ import annotations

from ...tools.generate_newsletter import render
from ...tools.save_newsletter import save_newsletter
from .common import ctx_for


def save_node(state: dict) -> dict:
    ctx = ctx_for(state)
    cfg = state.get("config") or {}
    review = state.get("review") or {}
    newsletter = dict(state["newsletter"])
    ctx.emit("saving", "started", "Saving the newsletter")

    if not review.get("passed"):
        remaining = [i["message"] for i in review.get("issues", []) if i["severity"] == "error"]
        notice = (
            "Automated quality review still flagged issues after the maximum number of revisions: "
            + "; ".join(remaining[:3])
        )
        disclosures = list(newsletter.get("disclosures") or [])
        if notice not in disclosures:
            disclosures.insert(0, notice)
        newsletter["disclosures"] = disclosures
        newsletter = render(newsletter)

    output = save_newsletter(newsletter, cfg.get("output_format", "html"), state["run_id"], review)
    status = "completed" if review.get("passed") else "completed_with_issues"
    approved_note = " Approved by a human reviewer." if state.get("approved") else ""
    message = (
        "Newsletter generated, reviewed and saved." if status == "completed"
        else "Newsletter saved, but the automated review could not resolve every issue (disclosed in the newsletter)."
    ) + approved_note
    ctx.emit("saving", "completed", f"Saved {output['primary_file']}", {"output": output})
    ctx.emit("send", "completed", f"Simulated send. Subject: {newsletter['subject']}")
    return {"newsletter": newsletter, "output": output, "status": status, "message": message}
