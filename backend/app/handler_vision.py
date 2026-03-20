"""Vision and PDF preprocessing utilities extracted from handler.py."""
import asyncio
import logging
import io
import re
import base64

from PIL import Image
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)


# ── Inline image extraction ───────────────────────────────────────────────────

_INLINE_IMAGE_RE = re.compile(
    r'!\[[^\]]*\]\((data:image/([^;]+);base64,([A-Za-z0-9+/=\s]+))\)'
)


def _extract_inline_image(text: str) -> tuple[str, bytes | None, str | None]:
    """Extract the first inline markdown image from text.
    Returns (cleaned_text, image_bytes, image_mime) or (text, None, None)."""
    m = _INLINE_IMAGE_RE.search(text)
    if not m:
        return text, None, None
    try:
        import base64 as b64mod
        mime_subtype = m.group(2)  # e.g. "png", "jpeg"
        raw_b64 = m.group(3).replace("\n", "").replace(" ", "")
        image_bytes = b64mod.b64decode(raw_b64)
        image_mime = f"image/{mime_subtype}"
        cleaned = text[:m.start()].rstrip() + text[m.end():].lstrip()
        return cleaned.strip(), image_bytes, image_mime
    except Exception as e:
        logger.warning("Inline image extraction failed: %s", e)
        return text, None, None


# ── PDF / document preprocessing ──────────────────────────────────────────────

_DOCUMENT_TAG_RE = re.compile(
    r'<document\s+name="([^"]+)"[^>]*>([\s\S]*?)</document>'
)


def _extract_pdf_text(base64_data: str, max_pages: int = 8) -> tuple[str, int]:
    """Extract text from a base64-encoded PDF using PyMuPDF.
    Returns (extracted_text, total_page_count)."""
    try:
        import fitz  # pymupdf
        import base64 as b64mod

        # Strip data-URL prefix if present
        if base64_data.startswith("data:"):
            base64_data = base64_data.split(",", 1)[-1]

        pdf_bytes = b64mod.b64decode(base64_data)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        num_pages = len(doc)
        pages = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                pages.append(f"[...truncated, {num_pages} pages total]")
                break
            pages.append(page.get_text())
        doc.close()
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        if not text:
            return "[PDF contained no extractable text — may be a scanned image]", num_pages
        # Cap extracted text to avoid bloating context
        if len(text) > 12000:
            text = text[:12000] + "\n\n[...text truncated at 12000 chars]"
        return text, num_pages
    except Exception as e:
        logger.warning("PDF extraction failed: %s", e)
        return f"[PDF text extraction failed: {e}]", 0


def _assess_pdf_text_quality(text: str, num_pages: int) -> bool:
    """Return True if extracted PDF text is usable; False if vision fallback should be tried."""
    if not text or text.startswith("["):
        return False
    clean = re.sub(r'\[\.\.\..*?\]', '', text).strip()
    if not clean:
        return False
    # Average characters per page
    if len(clean) / max(num_pages, 1) < 100:
        return False
    # Ratio of alphabetic characters to total non-whitespace
    non_ws = re.sub(r'\s+', '', clean)
    if non_ws:
        alpha_ratio = sum(c.isalpha() for c in non_ws) / len(non_ws)
        if alpha_ratio < 0.35:
            return False
    # Average word length and real-word ratio
    words = clean.split()
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len < 2.0 or avg_word_len > 25.0:
            return False
        real_words = sum(1 for w in words if len(w) >= 3 and any(c.isalpha() for c in w))
        if real_words / len(words) < 0.3:
            return False
    # Sentence density: real documents have lines with 5+ words (sentences).
    # Blueprints/CAD drawings have mostly short labels scattered on the page.
    lines = [ln.strip() for ln in clean.split("\n") if ln.strip()]
    if lines:
        sentence_lines = sum(1 for ln in lines if len(ln.split()) >= 5)
        sentence_ratio = sentence_lines / len(lines)
        if sentence_ratio < 0.10:
            logger.info("PDF quality: sentence_ratio=%.3f (too low, likely blueprint/drawing)", sentence_ratio)
            return False
    return True


def _render_pdf_pages_as_images(
    base64_data: str, max_pages: int = 4, dpi: int = 150,
) -> list[tuple[bytes, str]]:
    """Render PDF pages as JPEG images. Returns list of (jpeg_bytes, page_label)."""
    try:
        import fitz
        import base64 as b64mod

        if base64_data.startswith("data:"):
            base64_data = base64_data.split(",", 1)[-1]

        pdf_bytes = b64mod.b64decode(base64_data)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        results: list[tuple[bytes, str]] = []
        total = len(doc)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pixmap = page.get_pixmap(dpi=dpi)
            png_bytes = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(png_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            max_dim = 1600
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            results.append((buf.getvalue(), f"page {i + 1}/{total}"))
        doc.close()
        return results
    except Exception as e:
        logger.warning("PDF page rendering failed: %s", e)
        return []


# ── Vision preprocessor constants ─────────────────────────────────────────────

_VISION_PREPROCESSOR_PROVIDERS = frozenset({"openrouter"})
# Providers that can handle images natively (no need for vision preprocessor)
_NATIVE_VISION_PROVIDERS = frozenset({"claude", "google", "openai"})
_VISION_PROVIDER_KEY = {
    "openrouter": "openrouter_api_key",
}
_VISION_PROVIDER_ORDER_DEFAULT = ("openrouter",)
_VISION_OPENROUTER_MODEL_DEFAULT = "openrouter/free"
_VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE = (
    "Image received, but the dedicated vision preprocessor is unavailable. "
    "Asta uses free vision models on OpenRouter for image analysis. "
    "Please make sure your OpenRouter API key is set in Settings."
)
_vision_last_working_model: str | None = None  # cached last-success model for fast retry


async def _pdf_vision_fallback(base64_data: str, filename: str) -> str | None:
    """Render PDF pages as images and analyze via vision preprocessor.
    Returns combined analysis text, or None if vision is unavailable."""
    page_images = _render_pdf_pages_as_images(base64_data, max_pages=3, dpi=150)
    if not page_images:
        return None

    # Try first page — if vision fails on page 1, don't waste time on the rest
    first_jpeg, first_label = page_images[0]
    first_result = await _run_vision_preprocessor(
        text=(
            f"Analyze this PDF page ({first_label} of '{filename}'). "
            "Extract ALL visible text, numbers, labels, and describe any diagrams, tables, or visual elements. "
            "For non-English text, include the original text and a brief English summary."
        ),
        image_bytes=first_jpeg, image_mime="image/jpeg",
    )
    if not first_result:
        logger.warning("PDF vision fallback: first page failed, aborting remaining pages")
        return None

    analyses: list[str] = []
    first_text = first_result[0][:2500]
    analyses.append(f"[Page {first_label}]\n{first_text}")
    total_chars = len(first_text)
    max_total_chars = 8000

    # Process remaining pages
    for jpeg_bytes, label in page_images[1:]:
        if total_chars >= max_total_chars:
            break
        result = await _run_vision_preprocessor(
            text=(
                f"Analyze this PDF page ({label} of '{filename}'). "
                "Extract ALL visible text, numbers, labels, and describe any diagrams, tables, or visual elements. "
                "For non-English text, include the original text and a brief English summary."
            ),
            image_bytes=jpeg_bytes, image_mime="image/jpeg",
        )
        if result:
            analysis_text = result[0][:2500]
            analyses.append(f"[Page {label}]\n{analysis_text}")
            total_chars += len(analysis_text)

    combined = "\n\n".join(analyses)
    if len(combined) > max_total_chars:
        combined = combined[:max_total_chars] + "\n\n[...vision analysis truncated]"
    return combined


async def _pdf_vision_with_provider(base64_data: str, filename: str, provider_name: str) -> str | None:
    """Render PDF pages as images and analyze using the active provider's native vision.
    Used when Claude/Google/OpenAI is the active provider — better quality than free preprocessor models."""
    page_images = _render_pdf_pages_as_images(base64_data, max_pages=3, dpi=150)
    if not page_images:
        return None

    provider = get_provider(provider_name)
    if not provider:
        return None

    vision_prompt = (
        f"Analyze this PDF page of '{filename}'. "
        "Extract ALL visible text, numbers, labels, and describe any diagrams, tables, or visual elements. "
        "For non-English text, include the original text and a brief English summary."
    )
    vision_context = (
        "You are analyzing a PDF page rendered as an image. Return concise factual notes.\n"
        "Output plain text only (no code fences). Include:\n"
        "- all visible text (OCR)\n- tables and data\n- diagrams/visual elements\n- layout description"
    )

    analyses: list[str] = []
    max_total_chars = 8000

    for jpeg_bytes, label in page_images:
        if sum(len(a) for a in analyses) >= max_total_chars:
            break
        try:
            resp = await asyncio.wait_for(
                provider.chat(
                    [{"role": "user", "content": f"{vision_prompt} ({label})"}],
                    context=vision_context,
                    image_bytes=jpeg_bytes,
                    image_mime="image/jpeg",
                    thinking_level="off",
                    timeout=45,
                ),
                timeout=50,
            )
        except asyncio.TimeoutError:
            logger.warning("PDF vision via %s timed out on %s", provider_name, label)
            if not analyses:
                return None
            break
        except Exception as e:
            logger.warning("PDF vision via %s failed on %s: %s", provider_name, label, e)
            if not analyses:
                return None
            break
        if resp.error or not (resp.content or "").strip():
            if not analyses:
                return None
            break
        analysis_text = (resp.content or "").strip()[:2500]
        analyses.append(f"[Page {label}]\n{analysis_text}")
        logger.info("PDF page %s analyzed via %s (%d chars)", label, provider_name, len(analysis_text))

    if not analyses:
        return None
    combined = "\n\n".join(analyses)
    if len(combined) > max_total_chars:
        combined = combined[:max_total_chars] + "\n\n[...vision analysis truncated]"
    return combined


async def _preprocess_document_tags_async(text: str, *, provider_name: str = "") -> str:
    """Replace <document> tags with extracted content.
    For PDFs: try text first; if quality is poor, render pages as images
    and run through vision preprocessor (or the active provider if it has native vision)."""
    matches = list(_DOCUMENT_TAG_RE.finditer(text))
    if not matches:
        logger.info("No <document> regex matches found")
        return text

    logger.info("Found %d document tag(s) in text", len(matches))
    result = text
    for m in reversed(matches):
        name = m.group(1)
        content = m.group(2).strip()
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        logger.info("Processing document: name=%s, ext=%s, content_len=%d", name, ext, len(content))

        if ext != "pdf":
            continue

        extracted, num_pages = _extract_pdf_text(content)

        if _assess_pdf_text_quality(extracted, num_pages):
            replacement = f'<document name="{name}" type="pdf-extracted">\n{extracted}\n</document>'
        else:
            logger.info("PDF '%s' text quality is poor (%d pages), trying vision fallback (active_provider=%s)", name, num_pages, provider_name)
            if provider_name in _NATIVE_VISION_PROVIDERS:
                # Active provider has native vision — use it directly for PDF analysis
                vision_text = await _pdf_vision_with_provider(content, name, provider_name)
            else:
                vision_text = await _pdf_vision_fallback(content, name)
            if vision_text:
                replacement = f'<document name="{name}" type="pdf-vision">\n{vision_text}\n</document>'
            else:
                logger.warning("PDF '%s' vision fallback failed, using raw text extraction", name)
                fallback_note = "[Note: This PDF appears to be visual/scanned. Text extraction may be incomplete.]\n\n"
                replacement = f'<document name="{name}" type="pdf-extracted">\n{fallback_note}{extracted}\n</document>'

        result = result[:m.start()] + replacement + result[m.end():]

    return result


def _extract_native_pdf_documents(text: str) -> tuple[str, list[dict]]:
    """Extract raw PDF base64 data from <document> tags for native provider pass-through.
    Returns (text_with_pdfs_replaced, list_of_pdf_dicts).
    Non-PDF documents are left in the text untouched."""
    matches = list(_DOCUMENT_TAG_RE.finditer(text))
    if not matches:
        return text, []
    result = text
    pdfs: list[dict] = []
    for m in reversed(matches):
        name = m.group(1)
        content = m.group(2).strip()
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext != "pdf":
            continue
        # Strip data-URL prefix if present
        b64 = content.split(",", 1)[-1] if content.startswith("data:") else content
        pdfs.insert(0, {"name": name, "base64": b64})
        # Replace the PDF document tag with a short reference
        replacement = f'[Attached PDF: {name}]'
        result = result[:m.start()] + replacement + result[m.end():]
    return result, pdfs


def _preprocess_document_tags(text: str) -> str:
    """Replace <document> tags containing file data with extracted content.
    PDFs get text-extracted; other files are left as-is (already text)."""

    def _replace_doc(m: re.Match) -> str:
        name = m.group(1)
        content = m.group(2).strip()
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

        if ext == "pdf":
            extracted, _ = _extract_pdf_text(content)
            return f'<document name="{name}" type="pdf-extracted">\n{extracted}\n</document>'
        # Non-PDF documents (text, code, etc.) — keep as-is
        return m.group(0)

    return _DOCUMENT_TAG_RE.sub(_replace_doc, text)


async def _run_vision_preprocessor(
    *,
    text: str,
    image_bytes: bytes,
    image_mime: str | None,
) -> tuple[str, str, str | None] | None:
    from app.config import get_settings
    from app.keys import get_api_key

    settings = get_settings()
    if not bool(getattr(settings, "asta_vision_preprocess", True)):
        return None

    raw_order = str(getattr(settings, "asta_vision_provider_order", "") or "").strip().lower()
    provider_order = [
        p.strip()
        for p in raw_order.split(",")
        if p.strip() and p.strip() in _VISION_PREPROCESSOR_PROVIDERS
    ]
    if not provider_order:
        provider_order = list(_VISION_PROVIDER_ORDER_DEFAULT)
    else:
        for fallback_provider in _VISION_PROVIDER_ORDER_DEFAULT:
            if fallback_provider not in provider_order:
                provider_order.append(fallback_provider)

    openrouter_model = (
        str(getattr(settings, "asta_vision_openrouter_model", _VISION_OPENROUTER_MODEL_DEFAULT) or "").strip()
        or _VISION_OPENROUTER_MODEL_DEFAULT
    )
    image_prompt = (text or "").strip() or "Describe this image."
    vision_context = (
        "You are Asta's vision preprocessor. Analyze the image and return concise factual notes.\n"
        "Output plain text only (no code fences). Include:\n"
        "- scene summary\n"
        "- visible text (OCR)\n"
        "- important objects/entities\n"
        "- uncertainty notes if relevant"
    )

    # Build a flat list of (provider_name, model, provider_obj) attempts.
    # For OpenRouter: try each comma-separated model individually (avoids chained timeouts).
    global _vision_last_working_model
    attempts: list[tuple[str, str, object]] = []
    for candidate in provider_order:
        provider = get_provider(candidate)
        if not provider:
            continue
        if candidate == "openrouter":
            key_name = _VISION_PROVIDER_KEY.get(candidate)
            if not key_name:
                continue
            api_key = await get_api_key(key_name)
            if not api_key:
                continue
            models = [m.strip() for m in openrouter_model.split(",") if m.strip()] if openrouter_model else []
            for model in models:
                attempts.append((candidate, model, provider))

    # If we have a cached working model, try it first (skip full retry loop)
    if _vision_last_working_model:
        cached = _vision_last_working_model
        # Move cached model to front of attempts list
        cached_entry = next((a for a in attempts if a[1] == cached), None)
        if cached_entry:
            attempts = [cached_entry] + [a for a in attempts if a[1] != cached]

    for candidate, model, provider in attempts:
        chat_kwargs: dict = {
            "context": vision_context,
            "image_bytes": image_bytes,
            "image_mime": image_mime or "image/jpeg",
            "thinking_level": "off",
            "model": model,
            "timeout": 45,
        }
        if candidate == "openrouter":
            chat_kwargs["skip_model_policy"] = True
        try:
            resp = await asyncio.wait_for(
                provider.chat(
                    [{"role": "user", "content": image_prompt}],
                    **chat_kwargs,
                ),
                timeout=50,
            )
        except asyncio.TimeoutError:
            logger.warning("Vision preprocessor %s/%s timed out after 50s", candidate, model)
            continue
        except Exception as e:
            logger.warning("Vision preprocessor %s/%s failed: %s", candidate, model, e)
            continue
        if resp.error:
            logger.warning("Vision preprocessor %s/%s error: %s", candidate, model, resp.error_message or resp.error)
            continue
        analysis = (resp.content or "").strip()
        if not analysis:
            continue
        # Cache this working model so next image skips straight to it
        if _vision_last_working_model != model:
            _vision_last_working_model = model
            logger.info("Vision preprocessor cached working model: %s", model)
        logger.info("Vision preprocess complete using %s/%s", candidate, model)
        return analysis[:5000], candidate, model

    # All attempts failed — reset cache so next call does a fresh sweep
    if _vision_last_working_model:
        logger.info("Vision preprocessor resetting cached model (all attempts failed)")
        _vision_last_working_model = None
    return None
