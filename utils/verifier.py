import re
from typing import Dict, List

import google.generativeai as genai
from tavily import TavilyClient

from utils.helpers import (
    clean_source_urls,
    extract_json_from_text,
    get_domain,
    is_trusted_domain,
)
from utils.prompts import VERIFICATION_PROMPT

ALLOWED_STATUSES = {"VERIFIED", "INACCURATE", "FALSE", "NOT ENOUGH DATA"}


def search_evidence(tavily_client: TavilyClient, claim_text: str, max_results: int = 5) -> List[Dict]:
    """Fetch evidence snippets from Tavily."""
    result = tavily_client.search(
        query=(
            "Fact check this claim using reliable sources (official pages, "
            f"trusted news, research reports): {claim_text}"
        ),
        search_depth="advanced",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
    )
    return result.get("results", []) if isinstance(result, dict) else []


def _extract_numbers(text: str) -> List[float]:
    pattern = re.compile(
        r"(?<!\w)(\d+(?:,\d{3})*(?:\.\d+)?)\s*(billion|million|trillion|bn|mn|tn)?",
        flags=re.IGNORECASE,
    )
    matches = pattern.findall(text)
    values = []
    for raw_number, unit in matches:
        try:
            number = float(raw_number.replace(",", ""))
            unit = (unit or "").lower()
            if unit in {"billion", "bn"}:
                number *= 1_000_000_000
            elif unit in {"million", "mn"}:
                number *= 1_000_000
            elif unit in {"trillion", "tn"}:
                number *= 1_000_000_000_000
            values.append(number)
        except ValueError:
            continue
    return values


def _extract_years(text: str) -> List[int]:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    return [int(year) for year in years]


def _rule_based_status(claim_text: str, model_status: str, evidence_results: List[Dict]) -> str:
    claim_numbers = _extract_numbers(claim_text)
    claim_years = _extract_years(claim_text)
    claim_lower = claim_text.lower()
    evidence_text = " ".join(
        f"{item.get('title', '')} {item.get('content', '')}" for item in evidence_results
    )
    evidence_numbers = _extract_numbers(evidence_text)
    evidence_years = _extract_years(evidence_text)

    trusted_hits = 0
    for item in evidence_results:
        if is_trusted_domain(get_domain(item.get("url", ""))):
            trusted_hits += 1

    if not evidence_results:
        return "NOT ENOUGH DATA"

    # Impossible values are usually false.
    if claim_numbers:
        for number in claim_numbers:
            if number >= 1_000_000_000 and ("population" in claim_lower):
                return "FALSE"

    # Date contradiction for founding/established claims.
    if ("founded" in claim_lower or "established" in claim_lower) and claim_years and evidence_years:
        claim_year = claim_years[0]
        nearest_year = min(evidence_years, key=lambda y: abs(y - claim_year))
        year_gap = abs(claim_year - nearest_year)
        if year_gap >= 2:
            return "INACCURATE"

    # Compare numeric mismatch severity.
    if claim_numbers and evidence_numbers:
        claim_value = claim_numbers[0]
        nearest = min(evidence_numbers, key=lambda x: abs(x - claim_value))
        if claim_value > 0:
            ratio = abs(claim_value - nearest) / claim_value
            if ratio > 0.65:
                if trusted_hits >= 1 or len(evidence_results) >= 3:
                    return "FALSE" if trusted_hits >= 2 else "INACCURATE"
            if ratio > 0.2:
                return "INACCURATE"

    if model_status == "NOT ENOUGH DATA" and (evidence_numbers or evidence_years) and len(evidence_results) >= 2:
        return "INACCURATE"

    if len(evidence_results) <= 1 and trusted_hits == 0:
        return "NOT ENOUGH DATA"

    return model_status


def _score_confidence(status: str, trusted_source_count: int, source_count: int) -> float:
    base = {
        "VERIFIED": 0.72,
        "INACCURATE": 0.74,
        "FALSE": 0.78,
        "NOT ENOUGH DATA": 0.4,
    }.get(status, 0.5)
    confidence = base + min(0.18, trusted_source_count * 0.06) + min(0.08, source_count * 0.02)
    if status == "NOT ENOUGH DATA":
        confidence = min(confidence, 0.62)
    return max(0.0, min(1.0, round(confidence, 2)))


def _pick_top_sources(search_results: List[Dict], max_sources: int = 3) -> List[str]:
    ranked = sorted(
        search_results,
        key=lambda item: (
            0 if is_trusted_domain(get_domain(item.get("url", ""))) else 1,
            len(item.get("content", "")) * -1,
        ),
    )
    urls = [item.get("url", "") for item in ranked if item.get("url")]
    return clean_source_urls(urls)[:max_sources]


def build_evidence_block(search_results: List[Dict]) -> str:
    lines = []
    for idx, item in enumerate(search_results, start=1):
        title = item.get("title", "")
        snippet = item.get("content", "")
        url = item.get("url", "")
        lines.append(f"[{idx}] Title: {title}\nSnippet: {snippet}\nURL: {url}\n")
    return "\n".join(lines)


def verify_single_claim(
    model: genai.GenerativeModel,
    tavily_client: TavilyClient,
    claim: Dict,
    evidence_cache: Dict[str, List[Dict]],
) -> Dict:
    claim_text = claim["claim_text"]
    claim_type = claim.get("claim_type", "general")
    page_number = claim.get("page_number")

    cache_key = " ".join(claim_text.lower().split())
    if cache_key in evidence_cache:
        evidence_results = evidence_cache[cache_key]
    else:
        evidence_results = search_evidence(tavily_client, claim_text=claim_text)
        evidence_cache[cache_key] = evidence_results

    evidence_block = build_evidence_block(evidence_results)

    if not evidence_results:
        return {
            "claim_text": claim_text,
            "page_number": page_number,
            "claim_type": claim_type,
            "status": "NOT ENOUGH DATA",
            "correct_information": "No useful live search evidence was found.",
            "confidence_score": 0.2,
            "evidence_summary": "Tavily did not return enough relevant sources.",
            "source_urls": [],
            "source_domains": [],
        }

    prompt = (
        f"{VERIFICATION_PROMPT}\n\n"
        f"Claim: {claim_text}\n"
        f"Claim type: {claim_type}\n\n"
        f"Evidence:\n{evidence_block}"
    )

    model_note = ""
    try:
        response = model.generate_content(prompt)
        parsed = extract_json_from_text(response.text if response else "")
    except Exception:
        parsed = {}
        model_note = (
            " Gemini reasoning was temporarily limited (possibly API quota/rate limit), "
            "so this result used rule-based checks from available evidence."
        )

    model_status = str(parsed.get("status", "NOT ENOUGH DATA")).strip().upper()
    if model_status not in ALLOWED_STATUSES:
        model_status = "NOT ENOUGH DATA"

    status = _rule_based_status(claim_text, model_status, evidence_results)

    source_urls = _pick_top_sources(evidence_results, max_sources=3)
    domains = [get_domain(url) for url in source_urls]
    trusted_count = sum(1 for d in domains if is_trusted_domain(d))
    confidence = _score_confidence(status, trusted_count, len(source_urls))

    return {
        "claim_text": claim_text,
        "page_number": page_number,
        "claim_type": claim_type,
        "status": status,
        "correct_information": str(parsed.get("correct_information", "")).strip()
        or "No correction details available.",
        "confidence_score": confidence,
        "evidence_summary": str(parsed.get("evidence_summary", "")).strip()
        or f"No summary provided.{model_note}",
        "source_urls": source_urls,
        "source_domains": domains,
    }


def verify_claims(
    claims: List[Dict],
    gemini_api_key: str,
    tavily_api_key: str,
) -> List[Dict]:
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    tavily_client = TavilyClient(api_key=tavily_api_key)

    results = []
    evidence_cache: Dict[str, List[Dict]] = {}
    for claim in claims:
        checked = verify_single_claim(
            model=model,
            tavily_client=tavily_client,
            claim=claim,
            evidence_cache=evidence_cache,
        )
        results.append(checked)
    return results

