"""Tests for cross-provider model fallback."""
import asyncio
import pytest
from app.providers.fallback import classify_error, ErrorKind, is_error_reply


class TestClassifyError:
    def test_not_an_error(self):
        assert classify_error("Hello! How can I help you?") == ErrorKind.NONE
        assert classify_error("") == ErrorKind.NONE
        assert classify_error("Sure, here's the weather.") == ErrorKind.NONE

    def test_auth_errors(self):
        assert classify_error("Error: Groq API key invalid or expired. Check Settings → API keys.") == ErrorKind.AUTH
        assert classify_error("Error: OpenAI API key not set. Add it in Settings.") == ErrorKind.AUTH
        assert classify_error("Error: 401 Unauthorized") == ErrorKind.AUTH

    def test_rate_limit(self):
        assert classify_error("Error: Groq rate limit. Wait a moment and try again.") == ErrorKind.RATE_LIMIT
        assert classify_error("Error: 429 Too Many Requests") == ErrorKind.RATE_LIMIT
        assert classify_error("Error: All models rate-limited.") == ErrorKind.RATE_LIMIT

    def test_model_not_found(self):
        assert classify_error("Error: Groq model 'xyz' not found.") == ErrorKind.MODEL_NOT_FOUND
        assert classify_error("Error: Groq model 'old' has been decommissioned.") == ErrorKind.MODEL_NOT_FOUND
        assert classify_error("Error: 404 model not available") == ErrorKind.MODEL_NOT_FOUND

    def test_timeout(self):
        assert classify_error("Error: Model x timed out after 30s") == ErrorKind.TIMEOUT
        assert classify_error("Error: Request timeout") == ErrorKind.TIMEOUT

    def test_transient(self):
        assert classify_error("Error: OpenAI API — some random failure") == ErrorKind.TRANSIENT
        assert classify_error("Error: something went wrong") == ErrorKind.TRANSIENT


class TestIsErrorReply:
    def test_error(self):
        assert is_error_reply("Error: something failed") is True

    def test_not_error(self):
        assert is_error_reply("Hello there!") is False
        assert is_error_reply("") is False
