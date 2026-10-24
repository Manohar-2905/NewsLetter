# Newsletter Agent

An autonomous AI agent that turns a plain-English goal into a researched, source-linked newsletter, using free tools wherever it can.

```
"Create a newsletter about the latest developments in Agentic AI and autonomous coding agents"
        │
        ▼
Plan ─► Research ─► Select ─► Summarize ─► Write ─► Review ─► (Revise ≤2×) ─► [Human approval] ─► Save / "Send"
          ▲    │
          └────┘  too few results? the agent widens the time window and queries
```

- **Frontend:** React + Vite + Tailwind CSS + Lucide icons + React Router (landing page at `/`, agent workspace at `/agent`, run history at `/runs`). Theme: jet black `#0a0a0a`, cerulean `#007ba7`, neon rose `#ff2d95`
- **Backend:** Python, FastAPI, Pydantic
- **Agent:** LangGraph, with conditional routing, a review/revision loop, and Human-in-the-Loop pauses via `interrupt()` with a SQLite checkpointer
- **Models:** Google Gemini by default (free tier). OpenAI and local Ollama are optional.
- **Research:** Google News RSS, the GDELT DOC API, publisher RSS feeds, and the Hacker News Algolia API, all free with no key. Tavily is optional.

---

## 1. What is free and what can cost money

| Component | Cost | Notes |
|---|---|---|
| Google News RSS, GDELT, publisher RSS, Hacker News API | **Free**, no key | Public endpoints with their own rate limits. GDELT allows about one request every 5 s, and the agent waits for that. |
| **Gemini API** (default) | **Free tier with quotas** | Limits are set per Google Cloud project and change over time; check yours in Google AI Studio. Developers have reported roughly 20 requests/day for 3.x Flash and roughly 500/day for 3.x Flash-Lite on the free tier. That's why the default is `gemini-3.5-flash-lite`. If you enable billing on the project, usage beyond the free tier is charged. |
| OpenAI API | **Paid** per token | Optional. A ChatGPT Plus/Pro subscription **does not** include API credits. |
| Ollama | **Free** (runs locally) | Needs enough RAM/VRAM. An 8B model needs about 8 GB RAM, and quality is lower than hosted models. |
| Tavily search | Free tier, then paid | Optional. Used only if listed in `SEARCH_PROVIDER` and a key is set. |

**Cost controls built in:**

- About 5 model calls per newsletter: plan, relevance check, one batched summary call, writing, and review. Each revision adds 1 to 3 calls.
- Deduplication, scoring, rendering, link and HTML checks are all deterministic Python, not LLM calls.
- Research results are cached for 30 minutes.
- Article text is capped at 4,000 characters, and output tokens are capped.
- A per-minute rate limit gets **one** retry (waiting at most 30 s). An exhausted daily quota or a bad key is **never** retried.
- The agent **never switches provider silently.** It switches only if you set `LLM_FALLBACK_PROVIDER`, and then it reports the switch in the progress log.

---

## 2. Project structure

```
newsletter-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app (CORS, /api/health, /api/config)
│   │   ├── config.py               Settings from .env + startup validation
│   │   ├── cli.py                  `python -m app.cli "goal"` (terminal mode)
│   │   ├── api/routes/agent.py     REST + SSE endpoints
│   │   ├── schemas/                Pydantic request/response models
│   │   ├── agent/
│   │   │   ├── graph.py            LangGraph workflow + run_newsletter_agent(goal)
│   │   │   ├── state.py            Workflow state (JSON-serialisable, checkpointed)
│   │   │   ├── context.py          Per-run model clients + progress events
│   │   │   ├── prompts.py          Grounding / anti-prompt-injection prompts
│   │   │   └── nodes/              planner, researcher, selector, summarizer,
│   │   │                           writer, critic (review+revise), human_review, saver
│   │   ├── tools/                  The agent's real tools:
│   │   │   ├── search_news.py          search_news(topic) + fetch_article_content
│   │   │   ├── summarize_article.py    summarize_article(article)
│   │   │   ├── generate_newsletter.py  generate_newsletter(articles, config)
│   │   │   ├── review_newsletter.py    review_newsletter(newsletter, articles)
│   │   │   └── save_newsletter.py      save_newsletter(newsletter, format)
│   │   ├── services/               gemini / openai / ollama providers, retry+quota
│   │   │                           wrapper, background run manager
│   │   └── utils/                  text cleanup, dedupe, file cache
│   ├── tests/                      59 pytest tests (all external calls mocked)
│   ├── output/                     Saved newsletters (.html, .md, .json)
│   ├── data/                       Run records, cache, LangGraph checkpoints (auto-created)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── main.jsx                createBrowserRouter: / , /agent , /runs , *
    │   ├── App.jsx                 Layout (Header + <Outlet/> + Footer) + AgentProvider
    │   ├── index.css               Tailwind v4 @theme brand tokens (jet / cerulean / rose)
    │   ├── contexts/AgentContext.js  createContext + useAgent + AgentProvider
    │   ├── components/             Header (navItems), Footer, Logo, Container, Button, Card,
    │   │   │                       TopicForm, SettingsPanel, ProgressTimeline, ArticleList,
    │   │   │                       NewsletterPreview, ReviewReport, ApprovalPanel … (index.js barrel)
    │   │   └── landing/            Hero, StatsStrip, WorkflowSection, FeatureGrid,
    │   │                           ModesSection, CostSection, CallToAction
    │   ├── pages/                  Home (landing), Agent (workspace), Runs, NotFound
    │   ├── hooks/useAgentRun.js    SSE progress + polling fallback
    │   ├── services/agentService.js
    │   └── conf/conf.js
    ├── vite.config.js              Proxies /api → http://localhost:8000
    └── package.json
```

The frontend layout follows the conventions in [hiteshchoudhary/chai-aur-react](https://github.com/hiteshchoudhary/chai-aur-react) (see `12MegaBlog`):

- a `components/` folder with an `index.js` barrel export
- PascalCase component files
- `createBrowserRouter` in `main.jsx` with `App` as the layout (`<Outlet />`), like `12MegaBlog`
- a Header that maps over a `navItems` array (`name`, `slug`, `active`)
- shared state through a context file (`createContext` + `useAgent` + `AgentProvider`), like `TodoContext` in `10todocontextLocal`
- a `conf/conf.js` file for Vite env variables
- a service class exported as a singleton instance (like `authService`)
- `try/catch` blocks with `"Service :: method :: error"` logs

---

## 3. Prerequisites

- **Python 3.10+** (tested with 3.10 and 3.13)
- **Node.js 20+** (tested with 22)
- A free **Gemini API key** from <https://aistudio.google.com/apikey>

---

## 4. Setup (Windows commands first, macOS/Linux in comments)

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
```

Open `backend/.env` and set at least:

```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
```

Start the API:

```powershell
uvicorn app.main:app --reload --port 8000
```

Configuration problems are printed at startup, for example a missing key. You can also see them at <http://localhost:8000/api/config>. API docs are at <http://localhost:8000/docs>.

### Frontend (in a second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The landing page explains the agent. Type a topic in the hero box (or click **Launch agent**) to open the workspace at `/agent`, choose settings, and click **Run Agent**. Past runs are listed at `/runs`.

### Terminal-only usage

```powershell
cd backend
python -m app.cli "Create a newsletter about cybersecurity news" --mode hitl --format markdown
```

### From Python

```python
from app.agent.graph import run_newsletter_agent, resume_newsletter_agent

result = run_newsletter_agent("Create a weekly newsletter on the latest AI agent news")
print(result["status"], result["newsletter"]["subject"], result["output"])

# Human-in-the-loop
r = run_newsletter_agent("Startup funding news in India", mode="hitl")
r = resume_newsletter_agent(r["run_id"], "revise", "Remove article 2 and shorten the intro")
r = resume_newsletter_agent(r["run_id"], "approve")
```

Options: `provider`, `output_format` (`html`/`markdown`), `article_count` (1–7), `tone`, `mode` (`autonomous`/`hitl`), `lookback_days`.

---

## 5. Optional providers

**OpenAI (paid):** set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default `gpt-5-mini`). Then pick "OpenAI" in the UI, or set `LLM_PROVIDER=openai`. You can also use it only as an independent critic with `CRITIC_PROVIDER=openai`. In that setup Gemini writes and OpenAI reviews.

**Ollama (free, local):**

1. Install from <https://ollama.com>.
2. Run `ollama pull llama3.1:8b`, and keep `ollama serve` running.
3. Set `OLLAMA_ENABLED=true` (and optionally `OLLAMA_MODEL` / `OLLAMA_BASE_URL`).

A good free combination is `LLM_FALLBACK_PROVIDER=ollama`: the agent switches to your local model only if the Gemini quota runs out, and says so in the log.

**Research sources:** `SEARCH_PROVIDER=google_news,gdelt,rss,hackernews` (default). Edit `RSS_FEEDS` to add publisher feeds for your subjects. The default feeds are tech-focused, but Google News and GDELT cover any topic. Add `tavily` plus `TAVILY_API_KEY` if you want it.

---

## 6. How the agent works

| Step | What happens |
|---|---|
| **Plan** | The LLM turns the goal into a topic, 2–4 search queries, keywords, a time window and quality criteria. If no model is available, it falls back to keyword extraction. |
| **Research** | `search_news` queries every configured source for real articles and records title, publisher, URL and date. Failed sources are logged, never invented. If fewer relevant results than needed come back, the agent **broadens** the search (doubles the time window, uses keyword queries) and runs again, once. |
| **Select** | Deduplicates by normalised URL and headline similarity. Scores relevance (55%), recency (20%), source quality (20%), plus a small bonus for direct links. Allows at most 2 articles per publisher. One optional LLM call re-checks relevance. If nothing qualifies, it returns `no_results` and does **not** pad the list. |
| **Fetch** | For selected articles only, fetches readable text when `robots.txt` allows it. Paywalls (401/402/403) are respected. Google News links are redirect wrappers, so those items use the headline/excerpt and are flagged as limited. |
| **Summarize** | One batched call. Source text is wrapped in `<source>` tags and treated as untrusted (known injection phrases are neutralised). Headlines are never rewritten. Each summary records whether it came from full text, an excerpt or the headline only. Any article that fails is retried alone, then falls back to the publisher's excerpt. |
| **Write** | The LLM writes only the framing: subject, title, intro, takeaways, conclusion. Article sections, links and dates are rendered deterministically into HTML (inline-styled, email-friendly) and Markdown. Transparency notes list limited-information articles, missing dates and shortfalls. |
| **Review** | `review_newsletter` runs deterministic checks: article count, duplicates, valid links, required sections, HTML tag balance, Markdown links, **numbers in summaries that don't appear in the source**, unsupported superlatives, and keyword relevance. Then an LLM reviewer checks factual consistency with the sources and summary quality. The result is a structured pass/fail report with issues and fixes. |
| **Revise** | Flagged summaries are rewritten strictly from their source. Duplicates and off-topic items are replaced with reserve articles (or dropped), and the framing is rewritten. The loop runs at most `MAX_REVISIONS=2` times. If issues remain, the status becomes `completed_with_issues` and the issues are disclosed **inside** the newsletter. |
| **Human-in-the-Loop** | The run pauses with `interrupt()`, and its state is saved in `backend/data/checkpoints.sqlite`. **Approve** saves the draft. **Request changes** has the LLM turn your feedback into actions (remove article N, rewrite article N, change the tone or intro), then the draft goes back through write → review. Paused runs survive page reloads and backend restarts. |
| **Save / send** | Writes `.html`, `.md` and `.json` (sources + review) to `backend/output/`, and shows the subject and content as a simulated send. |

**Run statuses:** `queued`, `running`, `awaiting_approval`, `completed`, `completed_with_issues`, `no_results`, `failed`.

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/agent/run` | Start a run: `{goal, mode, article_count, tone, output_format, provider, lookback_days}` → `202 {run_id}` |
| GET | `/api/agent/{run_id}` | Status, events, results, review, download links |
| GET | `/api/agent/{run_id}/events` | Server-Sent Events progress stream (`?after=N` to resume) |
| POST | `/api/agent/{run_id}/approve` | Approve a paused draft |
| POST | `/api/agent/{run_id}/revise` | `{feedback}`: request changes |
| GET | `/api/agent/{run_id}/download?format=html\|markdown\|json` | Download the saved files |
| GET | `/api/agent/runs` | Recent runs |
| GET | `/api/config` | Non-secret settings (providers configured, warnings) |

API keys stay on the server and are never returned to the browser.

---

## 7. Tests

```powershell
cd backend
.venv\Scripts\activate
python -m pytest -q
```

The 59 tests mock every external call, so they need no network, no keys and no paid API. They cover:

- invalid input
- successful multi-source research, source failures, the 30-day filter, caching, robots.txt and paywalls
- duplicate removal, selection limits and diversity
- batch and per-article summarization failures
- HTML/Markdown generation and validation, unsupported-number detection
- critic failure with the 2-revision limit, and a successful revision
- autonomous runs, no-results runs
- HITL approve, revise, and resume after a restart
- API endpoints and SSE, downloads
- Gemini/OpenAI error mapping, rate-limit retry, quota exhaustion (with no silent switch), and quota running out mid-run

Frontend production build: `cd frontend && npm run build`.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| "Provider 'gemini' is not configured" | Add `GEMINI_API_KEY` to `backend/.env` and restart uvicorn. |
| "Gemini free-tier daily quota is exhausted" | The quota resets at midnight Pacific time. Wait, use a lighter model (`*-flash-lite`), configure `LLM_FALLBACK_PROVIDER=ollama`, or enable billing (which is charged). |
| "Gemini rate limit reached" | Too many requests per minute. The agent waits once automatically; if it still fails, try again in a minute. |
| "Gemini model not found" | Model names change. Pick a current one from <https://ai.google.dev/gemini-api/docs/models> and set `GEMINI_MODEL`. |
| "OpenAI quota/credits exhausted" | Add API credits at platform.openai.com. A ChatGPT subscription is separate from API billing. |
| `no_results` status | The topic is too narrow for the time window. Pick a longer window (14/30 days) or broaden the topic. Check the agent log for source errors (for example, a firewall blocking news.google.com). |
| Many "headline only" articles | Google News links can't be fetched directly, and some sites block bots. These summaries are disclosed as limited. Adding publisher feeds to `RSS_FEEDS` gives more full-text sources. |
| Frontend shows "Cannot reach the backend" | Start uvicorn on port 8000, or set `VITE_BACKEND_URL` when running `npm run dev`. |
| GDELT errors | GDELT rejects very short or unusual queries and limits request rate. Other sources keep working. |

---

## 9. Limitations (please read)

- **Automated review is not proof of accuracy.** It catches unsupported numbers, missing links, duplicates and many semantic issues, but an LLM can still misread a source. Every summary links to its original. Check important facts there.
- Summaries based on a headline or excerpt carry less information. They are labelled as such.
- Article "freshness" depends on the dates the sources report. Items without a date are kept but ranked lower and marked "Date not available".
- No email is sent: "sending" means saving and displaying the subject and content.
- Run records and checkpoints are local files (`backend/data/`). That's fine for a single machine, not for a multi-server deployment.
- Free-tier quotas and model names are controlled by the providers and change over time.
