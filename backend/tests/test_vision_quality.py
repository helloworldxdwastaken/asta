"""Test PDF text quality assessment for vision fallback decisions."""

from app.handler_vision import _assess_pdf_text_quality


def test_good_pdf_text():
    """Well-formatted document text should pass quality check."""
    good_text = "This is a well-formatted document with several paragraphs of text. " * 20
    assert _assess_pdf_text_quality(good_text, 2) is True


def test_bad_pdf_garbled():
    """Garbled/non-alphabetic text should fail quality check."""
    bad_text = "x3#@! 7z!! <<>> %%% &&& $$"
    assert _assess_pdf_text_quality(bad_text, 1) is False


def test_empty_pdf():
    """Empty text should fail quality check."""
    assert _assess_pdf_text_quality("", 1) is False


def test_bracket_only():
    """Text starting with [ (extraction failure marker) should fail."""
    assert _assess_pdf_text_quality("[no text found]", 1) is False
    assert _assess_pdf_text_quality("[PDF contained no extractable text]", 1) is False


def test_too_few_chars_per_page():
    """Very sparse text (< 100 chars per page) should fail."""
    sparse = "Hello world."
    assert _assess_pdf_text_quality(sparse, 5) is False


def test_low_alpha_ratio():
    """Text that is mostly numeric/symbolic should fail."""
    numeric = "123 456 789 012 345 678 901 234 567 890 " * 10
    assert _assess_pdf_text_quality(numeric, 1) is False


def test_blueprint_short_labels():
    """Blueprint-style text with short labels and no sentences should fail."""
    # Many short lines, no lines with 5+ words
    blueprint_lines = "\n".join([f"Label{i}" for i in range(50)])
    assert _assess_pdf_text_quality(blueprint_lines, 1) is False


def test_reasonable_document():
    """A normal multi-paragraph document should pass."""
    doc = (
        "Introduction to Machine Learning\n\n"
        "Machine learning is a subset of artificial intelligence that focuses on building systems "
        "that learn from data. These systems improve their performance on a specific task over time "
        "without being explicitly programmed.\n\n"
        "There are three main types of machine learning: supervised learning, unsupervised learning, "
        "and reinforcement learning. Each type has different applications and use cases.\n\n"
        "In supervised learning, the algorithm learns from labeled training data. The model makes "
        "predictions based on the input features and compares them to the known labels."
    )
    assert _assess_pdf_text_quality(doc, 1) is True


def test_none_text():
    """None or falsy text should fail."""
    assert _assess_pdf_text_quality(None, 1) is False


def test_truncation_marker_only():
    """Text that is just a truncation marker should fail."""
    assert _assess_pdf_text_quality("[...truncated, 10 pages total]", 1) is False
