# TruthLayer – AI Fact Checker

TruthLayer is an AI-powered PDF fact-checking web app built for assignment-style real-world use.  
It lets users upload a PDF, extracts factual claims from the document, verifies them using live web evidence, and returns a structured report.

The app is designed to be practical, clean, and easy to explain in interviews.

## Project Overview

Many reports and presentations include outdated numbers, incorrect dates, or unsupported claims.  
TruthLayer helps review those documents quickly by combining:

- claim extraction from PDF text
- web evidence lookup
- AI-based verification reasoning
- clear verdicts with confidence and sources

Each claim is classified into one of:

- `VERIFIED`
- `INACCURATE`
- `FALSE`
- `NOT ENOUGH DATA`

## Features

- PDF Upload with simple drag-and-drop flow
- AI Claim Extraction from document text
- Live Web Verification using Tavily search results
- Confidence Scoring based on evidence quality
- Claim Classification (`VERIFIED`, `INACCURATE`, `FALSE`, `NOT ENOUGH DATA`)
- Dashboard Metrics for quick summary
- CSV/JSON Export for reporting
- Dark Theme UI with clean, minimal styling

## How It Works

1. Upload a PDF
2. Extract text page-by-page with PyMuPDF
3. Detect factual claims with Gemini
4. Search live web evidence with Tavily
5. Compare evidence with claims (numbers, dates, context)
6. Generate verification report with status, confidence, corrections, and sources

## Tech Stack

- Streamlit
- Python
- Google Gemini API
- Tavily API
- PyMuPDF
- Pandas

## Project Structure

```bash
truthlayer/
│
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── utils/
│   ├── pdf_parser.py
│   ├── claim_extractor.py
│   ├── verifier.py
│   ├── prompts.py
│   ├── report_generator.py
│   └── helpers.py
│
├── assets/
└── sample_outputs/
```

## Installation

```bash
git clone <repo-url>
cd truthlayer
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

## Running Locally

```bash
streamlit run app.py
```

Once started, open the local URL shown in the terminal.

## Deployment on Streamlit Cloud

1. Push this project to GitHub.
2. Open [Streamlit Cloud](https://streamlit.io/cloud).
3. Create a new app and select your repository.
4. Add secrets in Streamlit:
   - `GEMINI_API_KEY`
   - `TAVILY_API_KEY`
5. Deploy.

## Example Workflow

- Upload a PDF market report.
- App extracts claims like:
  - "The global AI market reached 900 billion USD in 2024."
  - "OpenAI revenue was 10 billion USD in 2023."
- App fetches recent web evidence.
- Claims are labeled with status and confidence.
- User downloads CSV/JSON report for submission or review.

## Future Improvements

- OCR support for scanned/image PDFs
- Multi-language claim detection and verification
- Better source ranking with reliability scoring
- More advanced claim reasoning for complex statements
- Faster verification pipeline using async/batched requests

## Author

Ayush  
Built as an AI internship assignment project using Streamlit + Gemini + Tavily.

