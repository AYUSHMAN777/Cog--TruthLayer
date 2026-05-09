import os

import streamlit as st

from utils.claim_extractor import extract_claims
from utils.helpers import setup_environment
from utils.pdf_parser import extract_text_by_page
from utils.report_generator import build_download_files, generate_summary, results_to_dataframe
from utils.verifier import verify_claims

setup_environment()

st.set_page_config(
    page_title="TruthLayer - AI Fact Checker",
    page_icon=":mag:",
    layout="wide",
)

STATUS_COLORS = {
    "VERIFIED": "#22c55e",
    "INACCURATE": "#f59e0b",
    "FALSE": "#ef4444",
    "NOT ENOUGH DATA": "#6c757d",
}


def inject_custom_styles() -> None:
    st.markdown(
        """
        <style>
            .hero-wrap {
                border: 1px solid #1f2937;
                border-radius: 14px;
                padding: 0.95rem 1rem;
                margin-bottom: 0.8rem;
                background: #0f172a;
            }
            .hero-title {
                font-size: 1.7rem;
                font-weight: 700;
                color: #f8fafc;
                margin: 0;
            }
            .hero-sub {
                color: #94a3b8;
                margin-top: 0.2rem;
                margin-bottom: 0;
            }
            .upload-wrap {
                border: 1px solid #1f2937;
                border-radius: 12px;
                padding: 0.6rem 0.9rem 0.15rem 0.9rem;
                margin-bottom: 1rem;
                background: #111827;
            }
            .metric-card {
                border: 1px solid #1f2937;
                border-radius: 10px;
                padding: 0.65rem 0.8rem;
                background: #111827;
                box-shadow: 0 1px 5px rgba(0,0,0,0.18);
            }
            .metric-topbar {
                height: 4px;
                border-radius: 8px;
                margin-bottom: 0.55rem;
            }
            .metric-label {
                font-size: 0.85rem;
                color: #94a3b8;
                margin-bottom: 0.1rem;
            }
            .metric-value {
                font-size: 1.4rem;
                font-weight: 700;
                color: #f8fafc;
            }
            .result-row {
                border: 1px solid #1f2937;
                border-radius: 10px;
                padding: 0.65rem 0.8rem;
                background: #0f172a;
                margin-bottom: 0.6rem;
            }
            .result-meta {
                font-size: 0.85rem;
                color: #94a3b8;
            }
            .section-divider {
                margin-top: 0.75rem;
                margin-bottom: 0.75rem;
                border-top: 1px solid #1f2937;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#6c757d")
    return (
        f"<span style='background:{color}2b;color:{color};font-weight:700;"
        f"padding:0.2rem 0.5rem;border-radius:999px;font-size:0.85rem;'>{status}</span>"
    )


def show_sidebar(gemini_key: str, tavily_key: str) -> None:
    st.sidebar.markdown("## TruthLayer")
    st.sidebar.markdown("### API Status")
    st.sidebar.write(f"Gemini: {'Connected' if gemini_key else 'Missing'}")
    st.sidebar.write(f"Tavily: {'Connected' if tavily_key else 'Missing'}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### How to use")
    st.sidebar.markdown(
        "- Upload a PDF with factual claims\n"
        "- Click **Start Fact Check**\n"
        "- Review each claim result\n"
        "- Download CSV/JSON report"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Supported claim types")
    st.sidebar.markdown(
        "- Statistics and percentages\n"
        "- Revenue and market size\n"
        "- Technical specifications\n"
        "- Dates and growth claims\n"
        "- AI and company performance claims"
    )


def render_summary_cards(summary: dict) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        ("Total Claims", summary["total_claims"], "#64748b"),
        ("Verified", summary["verified_claims"], "#22c55e"),
        ("False", summary["false_claims"], "#ef4444"),
        ("Inaccurate", summary["inaccurate_claims"], "#f59e0b"),
        ("Accuracy %", f'{summary["accuracy_percentage"]}%', "#3b82f6"),
    ]
    for col, (label, value, color) in zip([c1, c2, c3, c4, c5], cards):
        col.markdown(
            (
                "<div class='metric-card'>"
                f"<div class='metric-topbar' style='background:{color};'></div>"
                f"<div class='metric-label'>{label}</div>"
                f"<div class='metric-value'>{value}</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def main() -> None:
    inject_custom_styles()

    st.markdown(
        """
        <div class='hero-wrap'>
            <h1 class='hero-title'>🛡️ TruthLayer - AI Fact Checker</h1>
            <p class='hero-sub'>Fact-check PDF claims using Gemini reasoning and live Tavily web evidence.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    show_sidebar(gemini_api_key, tavily_api_key)

    st.markdown("<div class='upload-wrap'>", unsafe_allow_html=True)
    left, right = st.columns([3, 1])
    with left:
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
        if uploaded_file:
            size_kb = uploaded_file.size / 1024
            st.caption(f"Selected file: {uploaded_file.name} ({size_kb:.1f} KB)")
    with right:
        st.write("")
        st.write("")
        start_check = st.button("Start Fact Check", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if start_check:
        if not gemini_api_key or not tavily_api_key:
            st.error("API keys are missing. Please set GEMINI_API_KEY and TAVILY_API_KEY.")
            return

        if not uploaded_file:
            st.warning("Please upload a PDF before starting.")
            return

        pdf_bytes = uploaded_file.read()
        if not pdf_bytes:
            st.error("Uploaded file is empty. Please upload a valid PDF.")
            return

        try:
            with st.spinner("Reading PDF and extracting text..."):
                pages = extract_text_by_page(pdf_bytes, max_pages=40)
        except Exception as e:
            st.error(f"Could not read PDF. Please upload a valid PDF file. ({e})")
            return

        if not pages:
            st.warning("No readable pages found in this PDF.")
            return

        page_count = len(pages)
        if page_count == 40:
            st.info("Large PDF detected. Processing first 40 pages for faster results.")

        progress = st.progress(0, text="Starting...")

        try:
            progress.progress(20, text="Extracting factual claims with Gemini...")
            claims = extract_claims(pages, gemini_api_key=gemini_api_key)
        except Exception as e:
            st.error(f"Claim extraction failed. Please try again. ({e})")
            return

        if not claims:
            progress.empty()
            st.warning(
                "No verifiable factual claims found in this PDF. "
                "Try a text-based PDF with numbers/dates, or retry after a short wait if API quota is hit."
            )
            return

        try:
            progress.progress(55, text="Verifying claims with Tavily + Gemini...")
            results = verify_claims(
                claims=claims,
                gemini_api_key=gemini_api_key,
                tavily_api_key=tavily_api_key,
            )
        except Exception as e:
            st.error(
                "Verification failed. This can happen due to API limits or temporary errors. "
                f"Details: {e}"
            )
            return

        progress.progress(90, text="Preparing dashboard and reports...")
        summary = generate_summary(results)
        df = results_to_dataframe(results)
        csv_bytes, json_bytes = build_download_files(results)
        progress.progress(100, text="Done.")

        st.subheader("Results Dashboard")
        render_summary_cards(summary)

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.subheader("Claim Results")

        show_df = df.copy()
        if show_df.empty:
            st.info("No claim rows to show.")
        else:
            for _, row in show_df.iterrows():
                status = row.get("status", "NOT ENOUGH DATA")
                st.markdown(
                    (
                        "<div class='result-row'>"
                        f"<div style='display:flex;justify-content:space-between;gap:1rem;'>"
                        f"<div><strong>{row.get('claim_text', '')}</strong></div>"
                        f"<div>{get_status_badge(status)}</div>"
                        "</div>"
                        "<div class='result-meta'>"
                        f"Type: {row.get('claim_type', 'general')} | "
                        f"Page: {row.get('page_number', '-')} | "
                        f"Confidence: {float(row.get('confidence_score', 0.0)):.2f}"
                        "</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.subheader("Detailed Claim Cards")
        for item in results:
            title = f"Page {item['page_number']} - {item['claim_type']}"
            with st.expander(title):
                st.markdown("**Original Claim**")
                st.write(item["claim_text"])
                st.markdown("---")
                st.markdown("**Verification Status**")
                st.markdown(f"**Status:** {get_status_badge(item['status'])}", unsafe_allow_html=True)
                st.markdown("**Confidence Score**")
                st.write(f"{item['confidence_score']:.2f}")
                st.markdown("---")
                st.markdown("**Correct Information**")
                st.markdown(f"**Correct Information:** {item['correct_information']}")
                st.markdown("**Evidence Summary**")
                st.write(item["evidence_summary"])

                urls = item.get("source_urls", [])
                if urls:
                    st.markdown("---")
                    st.markdown("**Top Sources**")
                    for url in urls[:3]:
                        domain = url.split("/")[2] if "://" in url else url
                        st.markdown(f"- [{domain}]({url})")
                else:
                    st.markdown("**Sources:** No source URLs available.")

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.subheader("Download Reports")
        d1, d2 = st.columns(2)
        d1.download_button(
            label="Download CSV report",
            data=csv_bytes,
            file_name="truthlayer_fact_check_report.csv",
            mime="text/csv",
        )
        d2.download_button(
            label="Download JSON report",
            data=json_bytes,
            file_name="truthlayer_fact_check_report.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()

