"""Application configuration.

All settings are read from environment variables (or a `.env` file in the
`backend/` folder). Nothing secret is ever sent to the browser.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

SUPPORTED_PROVIDERS = ("gemini", "openai", "ollama")
SUPPORTED_SEARCH_SOURCES = ("google_news", "gdelt", "rss", "hackernews", "tavily")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM providers -------------------------------------------------
    llm_provider: str = "gemini"
    # Optional: an explicitly configured fallback provider ("" = none).
    # The agent never switches provider unless you set this yourself.
    llm_fallback_provider: str = ""
    # Optional: a second provider used only as an independent critic.
    critic_provider: str = ""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_enabled: bool = False

    llm_timeout_seconds: int = 60
    llm_max_output_tokens: int = 4096

    # --- Research ------------------------------------------------------
    # Comma separated list of research sources, in priority order.
    search_provider: str = "google_news,gdelt,rss,hackernews"
    rss_feeds: str = (
        "https://techcrunch.com/feed/,"
        "https://www.theverge.com/rss/index.xml,"
        "https://feeds.arstechnica.com/arstechnica/index,"
        "https://www.wired.com/feed/rss,"
        "https://www.technologyreview.com/feed/,"
        "https://venturebeat.com/feed/"
    )
    tavily_api_key: str = ""  # optional semantic search; used automatically when set
    tavily_search_depth: str = "advanced"  # basic | advanced
    tavily_max_results: int = 8
    tavily_max_queries: int = 4
    max_rewritten_queries: int = 4
    news_language: str = "en"
    news_country: str = "US"
    default_lookback_days: int = 7
    http_timeout_seconds: int = 10
    max_candidates_per_query: int = 25
    research_cache_ttl_minutes: int = 30
    fetch_article_content: bool = True
    max_article_chars: int = 4000
    use_llm_relevance_filter: bool = True

    # --- Agent behaviour -----------------------------------------------
    max_revisions: int = 2
    max_research_rounds: int = 2
    min_articles: int = 5
    max_articles: int = 7

    # --- Server --------------------------------------------------------
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    output_dir: str = Field(default=str(BACKEND_DIR / "output"))
    data_dir: str = Field(default=str(BACKEND_DIR / "data"))

    # --- Helpers -------------------------------------------------------
    @property
    def search_sources(self) -> list[str]:
        return [s.strip().lower() for s in self.search_provider.split(",") if s.strip()]

    @property
    def rss_feed_list(self) -> list[str]:
        return [u.strip() for u in self.rss_feeds.split(",") if u.strip()]

    @property
    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    def provider_configured(self, provider: str) -> bool:
        provider = (provider or "").lower()
        if provider == "gemini":
            return bool(self.gemini_api_key)
        if provider == "openai":
            return bool(self.openai_api_key)
        if provider == "ollama":
            return self.ollama_enabled
        return False

    def provider_status(self) -> list[dict]:
        """Describe each provider for the UI without exposing any secret."""
        return [
            {
                "id": "gemini",
                "label": "Google Gemini",
                "model": self.gemini_model,
                "configured": self.provider_configured("gemini"),
                "cost_note": "Free tier with daily quotas (varies by project); paid beyond that if billing is enabled.",
            },
            {
                "id": "openai",
                "label": "OpenAI",
                "model": self.openai_model,
                "configured": self.provider_configured("openai"),
                "cost_note": "Optional. API usage is billed per token (a ChatGPT subscription does not include API credits).",
            },
            {
                "id": "ollama",
                "label": "Ollama (local)",
                "model": self.ollama_model,
                "configured": self.provider_configured("ollama"),
                "cost_note": "Free, runs on your computer. Needs enough RAM/GPU for the chosen model.",
            },
        ]

    def validate_startup(self) -> list[str]:
        """Return human readable configuration warnings."""
        warnings: list[str] = []
        if self.llm_provider not in SUPPORTED_PROVIDERS:
            warnings.append(
                f"LLM_PROVIDER='{self.llm_provider}' is not supported. Use one of {SUPPORTED_PROVIDERS}."
            )
        elif not self.provider_configured(self.llm_provider):
            warnings.append(
                f"Default provider '{self.llm_provider}' is not configured. "
                "Set GEMINI_API_KEY (free key from https://aistudio.google.com/apikey), "
                "or choose another provider."
            )
        for src in self.search_sources:
            if src not in SUPPORTED_SEARCH_SOURCES:
                warnings.append(f"Unknown research source '{src}' in SEARCH_PROVIDER (ignored).")
        if "tavily" in self.search_sources and not self.tavily_api_key:
            warnings.append("SEARCH_PROVIDER includes 'tavily' but TAVILY_API_KEY is empty (Tavily skipped).")
        if not any(s in self.search_sources for s in ("google_news", "gdelt", "rss", "hackernews", "tavily")):
            warnings.append("No usable research source configured; research will return no articles.")
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
