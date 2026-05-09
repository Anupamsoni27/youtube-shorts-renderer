"""
Mock news data for development and testing.
Replace this with MongoDB queries in production.
"""

from app.models import NewsArticle

# Raw dict — exactly as it would come from MongoDB
MOCK_NEWS_DICT = {
    "_id": {"$oid": "69fd09b044d3da0823fc66ea"},
    "url": "https://www.fool.com.au/2026/05/07/can-this-red-hot-asx-materials-stock-keep-charging-higher/",
    "author": "Aaron Bell",
    "content": "ASX materials stock Imdex Ltd (ASX: IMD) is in focus today after another big jump during yesterday's trade. \r\nIt is an Australian mining equipment and technology company operating globally.\r\nIts tech… [+2351 chars]",
    "description": "Is this rocketing company a buy, hold, or sell?\nThe post Can this red hot ASX materials stock keep charging higher? appeared first on The Motley Fool Australia.",
    "publishedAt": "2026-05-06T23:57:00Z",
    "source": {"id": None, "name": "Motley Fool Australia"},
    "title": "Can this red hot ASX materials stock keep charging higher?",
    "uploaded": None,
    "urlToImage": "https://www.fool.com.au/wp-content/uploads/2022/03/construction-1200x675.jpg",
}


def get_mock_news() -> NewsArticle:
    """
    Returns a mock NewsArticle for testing.
    In production, replace with: NewsArticle.from_dict(mongodb_document)
    """
    return NewsArticle.from_dict(MOCK_NEWS_DICT)
