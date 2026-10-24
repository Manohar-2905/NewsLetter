"""Command-line entry point.

    python -m app.cli "Create a newsletter about the latest cybersecurity news"
    python -m app.cli "Agentic AI news" --mode hitl --format markdown --count 6
"""

import argparse
import json
import logging

from .agent.graph import resume_newsletter_agent, run_newsletter_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Newsletter Agent once.")
    parser.add_argument("goal")
    parser.add_argument("--mode", choices=["autonomous", "hitl"], default="autonomous")
    parser.add_argument("--format", choices=["html", "markdown"], default="html")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--tone", default="professional")
    parser.add_argument("--provider", choices=["gemini", "openai", "ollama"], default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    result = run_newsletter_agent(args.goal, mode=args.mode, output_format=args.format,
                                  article_count=args.count, tone=args.tone, provider=args.provider)
    while result["status"] == "awaiting_approval":
        print("\n=== DRAFT ===\n")
        print((result["newsletter"] or {}).get("markdown", ""))
        answer = input("\nApprove? [y] or type the changes you want: ").strip()
        if answer.lower() in ("", "y", "yes"):
            result = resume_newsletter_agent(result["run_id"], "approve")
        else:
            result = resume_newsletter_agent(result["run_id"], "revise", answer)

    print("\n=== RESULT ===")
    print(json.dumps({k: result.get(k) for k in ("status", "message", "output", "warnings")}, indent=2))
    if result.get("newsletter"):
        print("\nSubject:", result["newsletter"]["subject"])


if __name__ == "__main__":
    main()
