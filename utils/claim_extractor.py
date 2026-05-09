import re
from typing import Dict, List

import google.generativeai as genai

from utils.helpers import extract_json_from_text
from utils.prompts import CLAIM_EXTRACTION_PROMPT


def _rule_based_claims(text: str) -> List[Dict]:
    """
    Lightweight fallback extraction when LLM extraction fails or returns empty.
    Keeps the app usable during API quota/rate-limit periods.
    """
    claims: List[Dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if len(line) < 20:
            continue

        has_number = bool(re.search(r"\d", line))
        has_percent = "%" in line
        has_year = bool(re.search(r"\b(19|20)\d{2}\b", line))
        has_money = any(token in line.lower() for token in ["usd", "dollar", "revenue", "$"])

        if not (has_number or has_percent or has_year or has_money):
            continue

        claim_type = "general"
        lower_line = line.lower()
        if has_percent:
            claim_type = "percentage"
        elif has_money or any(k in lower_line for k in ["market", "revenue", "valuation"]):
            claim_type = "market_size"
        elif has_year:
            claim_type = "date_timeline"
        elif any(k in lower_line for k in ["population", "users", "growth"]):
            claim_type = "statistics"

        claims.append({"claim_text": line, "claim_type": claim_type})
    return claims


def _extract_claims_from_page(model: genai.GenerativeModel, page_text: str) -> List[Dict]:
    if not page_text.strip():
        return []

    try:
        response = model.generate_content(
            [
                CLAIM_EXTRACTION_PROMPT,
                f"Page text:\n{page_text}",
            ]
        )
    except Exception:
        # If API is rate-limited temporarily, use fallback extraction.
        return _rule_based_claims(page_text)
    parsed = extract_json_from_text(response.text if response else "")
    claims = parsed.get("claims", [])

    valid_claims = []
    for item in claims:
        claim_text = str(item.get("claim_text", "")).strip()
        claim_type = str(item.get("claim_type", "general")).strip() or "general"
        if claim_text:
            valid_claims.append(
                {
                    "claim_text": claim_text,
                    "claim_type": claim_type,
                }
            )
    if valid_claims:
        return valid_claims
    return _rule_based_claims(page_text)


def _normalize_claim_text(text: str) -> str:
    return " ".join(text.lower().split())


def _chunk_text(text: str, chunk_size: int = 3500) -> List[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size
    return chunks


def extract_claims(pages: List[Dict], gemini_api_key: str) -> List[Dict]:
    """Extract factual claims from all pages using Gemini."""
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    all_claims: List[Dict] = []
    seen_claims = set()
    for page in pages:
        page_number = page.get("page_number")
        page_text = page.get("text", "")

        for chunk in _chunk_text(page_text):
            page_claims = _extract_claims_from_page(model, chunk)
            for claim in page_claims:
                normalized = _normalize_claim_text(claim["claim_text"])
                if normalized in seen_claims:
                    continue
                seen_claims.add(normalized)
                claim["page_number"] = page_number
                all_claims.append(claim)

    return all_claims

