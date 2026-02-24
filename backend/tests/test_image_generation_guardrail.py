from __future__ import annotations

import json

import app.handler as handler


def test_image_generation_intent_detection_basic():
    assert handler._looks_like_image_generation_request("can you make a picture of a red sports car")
    assert handler._looks_like_image_generation_request("draw an ad banner for a mobile app")
    assert not handler._looks_like_image_generation_request("what model is best for image generation")
    assert not handler._looks_like_image_generation_request("do you have access to image generation tools?")


def test_reply_claims_image_tool_unavailable_detection():
    reply = (
        "I can't generate images yet — I don't have access to an image generation tool "
        "in this environment. The image_gen tool isn't available."
    )
    assert handler._reply_claims_image_tool_unavailable(reply) is True
    assert handler._reply_claims_image_tool_unavailable("I can do that now.") is False


def test_extract_image_markdown_from_tool_output():
    ok_payload = json.dumps(
        {
            "ok": True,
            "image_markdown": "![test](data:image/png;base64,AAA)",
        }
    )
    md, err = handler._extract_image_markdown_from_tool_output(ok_payload)
    assert md == "![test](data:image/png;base64,AAA)"
    assert err is None

    err_payload = json.dumps({"error": "Hugging Face credits exhausted (402)."})
    md2, err2 = handler._extract_image_markdown_from_tool_output(err_payload)
    assert md2 is None
    assert "credits exhausted" in (err2 or "").lower()
