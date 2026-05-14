"""
Data models for the video rendering pipeline.
Designed to mirror MongoDB document structure for future integration.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NewsSource:
    """Represents the source of a news article."""
    id: Optional[str] = None
    name: str = ""


@dataclass
class NewsArticle:
    """
    Represents a news article document.
    Mirrors the MongoDB schema for seamless future integration.
    """
    url: str = ""
    title: str = ""
    description: str = ""
    urlToImage: str = ""
    source: NewsSource = field(default_factory=NewsSource)
    publishedAt: str = ""
    author: Optional[str] = None
    content: Optional[str] = None
    title_hi: str = ""
    content_hi: str = ""
    summary_hi: str = ""
    viral_tags: str = ""
    uploaded: bool = False

    @property
    def source_name(self) -> str:
        """Convenience accessor for the source name."""
        return self.source.name

    @classmethod
    def from_dict(cls, data: dict) -> "NewsArticle":
        """
        Factory method to create a NewsArticle from a dictionary.
        This is the bridge for future MongoDB integration — 
        just pass the document dict directly.
        """
        source_data = data.get("source", {})
        source = NewsSource(
            id=source_data.get("id"),
            name=source_data.get("name", "")
        )
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            urlToImage=data.get("urlToImage", ""),
            source=source,
            publishedAt=data.get("publishedAt", ""),
            author=data.get("author"),
            content=data.get("content"),
            title_hi=data.get("title_hi", ""),
            content_hi=data.get("content_hi", ""),
            summary_hi=data.get("summary_hi", ""),
            viral_tags=" ".join(data.get("viral_tags", [])) if isinstance(data.get("viral_tags"), list) else data.get("viral_tags", ""),
            uploaded=data.get("uploaded", False),
        )
