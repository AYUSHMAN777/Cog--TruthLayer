from io import BytesIO
from typing import Dict, List

import fitz


def extract_text_by_page(pdf_bytes: bytes, max_pages: int = 40) -> List[Dict]:
    """
    Extract text page-by-page using PyMuPDF.
    Returns a list with page number and text content.
    """
    pages: List[Dict] = []

    with fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf") as doc:
        if doc.page_count == 0:
            return pages

        page_limit = min(doc.page_count, max_pages)
        for i in range(page_limit):
            page = doc.load_page(i)
            text = page.get_text("text").strip()
            pages.append(
                {
                    "page_number": i + 1,
                    "text": text,
                }
            )

    return pages

