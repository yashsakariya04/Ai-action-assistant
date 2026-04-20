"""
summarizer_service.py — Multi-source summarization service.

Supports:
  1. Uploaded files  — PDF, DOCX, XLSX
  2. URLs            — any webpage or online document
  3. Raw text        — inline pasted content

Uses existing get_llm_response() from llm_service — no new API key needed.
Content is capped at 8000 characters to stay within LLM context limits.

Install dependencies:
  pip install pypdf python-docx pandas openpyxl beautifulsoup4 requests
"""

import logging
import re
from typing import Dict

log = logging.getLogger(__name__)

MAX_CHARS = 8000


# ─────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────

def summarize(
    content:   str = "",
    url:       str = "",
    file_path: str = "",
) -> str:
    """
    Summarize content from a file, URL, or raw text.

    Priority: file_path > url > content

    Returns a clean string summary or a friendly error message.
    """
    try:
        text = ""

        # ── Source 1: Uploaded file ───────────────────────────
        if file_path and file_path.strip():
            result = _extract_from_file(file_path.strip())
            if not result["success"]:
                return result["message"]
            text = result["text"]

        # ── Source 2: URL ─────────────────────────────────────
        elif url and url.strip():
            result = _extract_from_url(url.strip())
            if not result["success"]:
                return result["message"]
            text = result["text"]

        # ── Source 3: Raw text ────────────────────────────────
        elif content and content.strip():
            text = content.strip()

        else:
            return "Please provide a file, URL, or text to summarize."

        # ── Validate extracted content ────────────────────────
        text = _clean_text(text)
        if not text or len(text.strip()) < 50:
            return "I couldn't extract enough content to summarize. The source may be empty or protected."

        # ── Trim to LLM context limit ─────────────────────────
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
            log.info("Content trimmed to %d characters for summarization.", MAX_CHARS)

        # ── Summarize via LLM ─────────────────────────────────
        return _llm_summarize(text)

    except Exception as exc:
        log.exception("Summarizer unexpected error")
        return f"Something went wrong while summarizing: {exc}"


# ─────────────────────────────────────────────────────────────
# FILE EXTRACTORS
# ─────────────────────────────────────────────────────────────

def _extract_from_file(file_path: str) -> Dict:
    """Extract text from PDF, DOCX, or XLSX file."""
    file_lower = file_path.lower()

    try:
        if file_lower.endswith(".pdf"):
            return _extract_pdf(file_path)

        elif file_lower.endswith(".docx"):
            return _extract_docx(file_path)

        elif file_lower.endswith((".xlsx", ".xls")):
            return _extract_excel(file_path)

        elif file_lower.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return {"success": True, "text": text}

        else:
            ext = file_path.rsplit(".", 1)[-1].upper() if "." in file_path else "unknown"
            return {
                "success": False,
                "message": (
                    f"File type .{ext} is not supported. "
                    "Please upload a PDF, DOCX, XLSX, or TXT file."
                ),
            }

    except FileNotFoundError:
        return {
            "success": False,
            "message": "The uploaded file could not be found. Please try uploading again.",
        }
    except Exception as exc:
        log.error("File extraction error for %s: %s", file_path, exc)
        return {
            "success": False,
            "message": f"Could not read the file: {exc}",
        }


def _extract_pdf(path: str) -> Dict:
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        pages  = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text.strip())
        text = "\n\n".join(pages)
        if not text.strip():
            return {"success": False, "message": "The PDF appears to be empty or contains only images (scanned PDF). Text extraction is not possible."}
        return {"success": True, "text": text}
    except ImportError:
        return {"success": False, "message": "pypdf is not installed. Run: pip install pypdf"}
    except Exception as exc:
        return {"success": False, "message": f"Failed to read PDF: {exc}"}


def _extract_docx(path: str) -> Dict:
    try:
        from docx import Document
        doc        = Document(path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text       = "\n\n".join(paragraphs)
        if not text.strip():
            return {"success": False, "message": "The Word document appears to be empty."}
        return {"success": True, "text": text}
    except ImportError:
        return {"success": False, "message": "python-docx is not installed. Run: pip install python-docx"}
    except Exception as exc:
        return {"success": False, "message": f"Failed to read DOCX: {exc}"}


def _extract_excel(path: str) -> Dict:
    try:
        import pandas as pd
        # Read all sheets
        xl   = pd.ExcelFile(path)
        all_text = []
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            df = df.dropna(how="all").fillna("")
            all_text.append(f"[Sheet: {sheet_name}]\n{df.to_string(index=False)}")
        text = "\n\n".join(all_text)
        if not text.strip():
            return {"success": False, "message": "The Excel file appears to be empty."}
        return {"success": True, "text": text}
    except ImportError:
        return {"success": False, "message": "pandas/openpyxl not installed. Run: pip install pandas openpyxl"}
    except Exception as exc:
        return {"success": False, "message": f"Failed to read Excel file: {exc}"}


# ─────────────────────────────────────────────────────────────
# URL EXTRACTOR
# ─────────────────────────────────────────────────────────────

def _extract_from_url(url: str) -> Dict:
    """Fetch and extract clean text from any URL."""
    if not url.startswith(("http://", "https://")):
        return {
            "success": False,
            "message": f"'{url}' doesn't look like a valid URL. Please start with http:// or https://",
        }

    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise tags
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "advertisement", "iframe", "noscript"]):
            tag.decompose()

        # Try to get main article content first
        main_content = (
            soup.find("article") or
            soup.find("main") or
            soup.find(id=re.compile(r"content|main|article", re.I)) or
            soup.find(class_=re.compile(r"content|main|article|post", re.I))
        )

        if main_content:
            text = main_content.get_text(separator="\n")
        else:
            text = soup.get_text(separator="\n")

        text = text.strip()
        if not text or len(text) < 100:
            return {
                "success": False,
                "message": f"Couldn't extract readable content from {url}. The page may be behind a login or use JavaScript rendering.",
            }

        return {"success": True, "text": text}

    except ImportError:
        return {"success": False, "message": "requests/beautifulsoup4 not installed. Run: pip install requests beautifulsoup4"}
    except requests.exceptions.Timeout:
        return {"success": False, "message": f"Request timed out while fetching {url}. Please try again."}
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": f"Could not access {url}: HTTP {exc.response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": f"Could not connect to {url}. Please check the URL and your internet connection."}
    except Exception as exc:
        log.error("URL extraction error for %s: %s", url, exc)
        return {"success": False, "message": f"Failed to fetch URL: {exc}"}


# ─────────────────────────────────────────────────────────────
# TEXT CLEANER
# ─────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Remove excessive whitespace and blank lines."""
    # Collapse multiple newlines to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Remove lines that are just whitespace
    lines = [line for line in text.split("\n") if line.strip()]
    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────
# LLM SUMMARIZER
# ─────────────────────────────────────────────────────────────

def _llm_summarize(text: str) -> str:
    """Use existing Groq LLM to summarize the extracted text."""
    try:
        from core.llm_service import get_llm_response

        prompt = (
            "You are summarizing content for a user. "
            "Provide a clear, well-structured summary.\n\n"
            "RULES:\n"
            "- Start with a 1-2 sentence overview of what this content is about\n"
            "- Then cover the key points using bullet points\n"
            "- End with a 1 sentence conclusion if applicable\n"
            "- Be concise but complete — capture all important information\n"
            "- Use plain language — no jargon unless it's in the original\n"
            "- Do NOT say 'Here is a summary' or similar filler phrases\n\n"
            f"Content to summarize:\n\n{text}"
        )

        return get_llm_response(prompt)

    except Exception as exc:
        log.error("LLM summarization failed: %s", exc)
        return f"Content was extracted successfully but summarization failed: {exc}"