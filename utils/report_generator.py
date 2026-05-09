import io
import json
from typing import Dict, List, Tuple

import pandas as pd

from utils.helpers import utc_timestamp


def results_to_dataframe(results: List[Dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(
            columns=[
                "claim_text",
                "page_number",
                "claim_type",
                "status",
                "correct_information",
                "confidence_score",
                "evidence_summary",
                "source_urls",
                "source_domains",
            ]
        )

    df = pd.DataFrame(results)
    if "source_urls" in df.columns:
        df["source_urls"] = df["source_urls"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else ""
        )
    if "source_domains" in df.columns:
        df["source_domains"] = df["source_domains"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else ""
        )
    if "confidence_score" in df.columns:
        df["confidence_score"] = df["confidence_score"].apply(
            lambda x: round(float(x), 2) if x is not None else 0.0
        )
    return df


def generate_summary(results: List[Dict]) -> Dict:
    total = len(results)
    verified = sum(1 for r in results if r.get("status") == "VERIFIED")
    false = sum(1 for r in results if r.get("status") == "FALSE")
    inaccurate = sum(1 for r in results if r.get("status") == "INACCURATE")
    not_enough = sum(1 for r in results if r.get("status") == "NOT ENOUGH DATA")
    accuracy = (verified / total * 100) if total else 0

    return {
        "total_claims": total,
        "verified_claims": verified,
        "false_claims": false,
        "inaccurate_claims": inaccurate,
        "not_enough_data_claims": not_enough,
        "accuracy_percentage": round(accuracy, 2),
    }


def build_download_files(results: List[Dict]) -> Tuple[bytes, bytes]:
    df = results_to_dataframe(results)
    summary = generate_summary(results)
    generated_at = utc_timestamp()

    if not df.empty:
        df.insert(0, "generated_at_utc", generated_at)

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    json_payload = {
        "generated_at_utc": generated_at,
        "summary": summary,
        "claims": results,
    }
    json_bytes = json.dumps(json_payload, indent=2).encode("utf-8")
    return csv_bytes, json_bytes

