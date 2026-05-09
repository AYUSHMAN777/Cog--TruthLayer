import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

from dotenv import load_dotenv


def setup_environment() -> None:
    """Load local .env values if present."""
    load_dotenv()


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Gemini sometimes returns JSON wrapped in markdown.
    This helper tries to safely recover a JSON object.
    """
    if not text:
        return {}

    cleaned = text.strip()
    cleaned = re.sub(r"^```json", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^```", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def clean_source_urls(urls: List[str]) -> List[str]:
    """Remove duplicates while preserving order."""
    seen = set()
    clean_urls = []
    for url in urls:
        if not url or not isinstance(url, str):
            continue
        if url in seen:
            continue
        seen.add(url)
        clean_urls.append(url)
    return clean_urls


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def is_trusted_domain(domain: str) -> bool:
    if not domain:
        return False

    trusted_keywords = [
        ".gov",
        ".edu",
        "statista.com",
        "worldbank.org",
        "imf.org",
        "oecd.org",
        "mckinsey.com",
        "gartner.com",
        "forrester.com",
        "bloomberg.com",
        "reuters.com",
        "wsj.com",
        "ft.com",
        "cnbc.com",
        "bbc.com",
        "nytimes.com",
        "wikipedia.org",
        "britannica.com",
        "investopedia.com",
        "crunchbase.com",
        "openai.com",
        "google.com",
        "microsoft.com",
        "nvidia.com",
    ]
    return any(keyword in domain for keyword in trusted_keywords)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

