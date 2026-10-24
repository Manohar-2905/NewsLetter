"""The agent's tools.

Each tool is a plain, testable Python function. They are also registered as
LangChain tools (`AGENT_TOOLS`) so they can be inspected or bound to a model.
"""

from langchain_core.tools import StructuredTool

from .generate_newsletter import generate_newsletter
from .review_newsletter import review_newsletter
from .save_newsletter import save_newsletter
from .search_news import fetch_article_content, search_news
from .summarize_article import summarize_article, summarize_articles

AGENT_TOOLS = [
    StructuredTool.from_function(search_news, name="search_news",
                                 description="Retrieve real news articles for a topic from free RSS feeds and public APIs."),
    StructuredTool.from_function(fetch_article_content, name="fetch_article_content",
                                 description="Fetch readable article text when robots.txt and access controls allow it."),
    StructuredTool.from_function(summarize_article, name="summarize_article",
                                 description="Create a source-grounded summary of one article."),
    StructuredTool.from_function(generate_newsletter, name="generate_newsletter",
                                 description="Generate an HTML or Markdown newsletter from summarised articles."),
    StructuredTool.from_function(review_newsletter, name="review_newsletter",
                                 description="Review a newsletter for relevance, accuracy, completeness and format validity."),
    StructuredTool.from_function(save_newsletter, name="save_newsletter",
                                 description="Save the newsletter to the output directory."),
]

__all__ = [
    "AGENT_TOOLS",
    "search_news",
    "fetch_article_content",
    "summarize_article",
    "summarize_articles",
    "generate_newsletter",
    "review_newsletter",
    "save_newsletter",
]
