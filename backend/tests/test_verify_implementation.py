
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.thinking_capabilities import supports_xhigh_thinking
from app.providers.ollama import OllamaProvider
from app.providers.openrouter import OpenRouterProvider
from app.providers.base import Message

class TestThinkingImplementation(unittest.TestCase):
    def test_thinking_capabilities_kimi_trinity(self):
        # Test OpenRouter
        self.assertTrue(supports_xhigh_thinking("openrouter", "moonshot/moonshot-v1-8k"))
        self.assertTrue(supports_xhigh_thinking("openrouter", "kimi"))
        self.assertTrue(supports_xhigh_thinking("openrouter", "trinity"))
        self.assertTrue(supports_xhigh_thinking("openrouter", "deepseek/deepseek-r1"))
        self.assertFalse(supports_xhigh_thinking("openrouter", "gpt-3.5-turbo"))

        # Test Ollama
        self.assertTrue(supports_xhigh_thinking("ollama", "deepseek-r1:8b"))
        self.assertTrue(supports_xhigh_thinking("ollama", "kimi"))
        self.assertFalse(supports_xhigh_thinking("ollama", "llama3"))

    def test_ollama_thinking_injection(self):
        async def run_test():
            provider = OllamaProvider()
            
            # Mock network calls to avoid actual requests
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"message": {"content": "ok"}}
                
                # Test with thinking level
                messages: list[Message] = [{"role": "user", "content": "hello"}]
                await provider.chat(messages, model="kimi", thinking_level="high")
                
                # Verify call args
                call_args = mock_post.call_args
                self.assertIsNotNone(call_args)
                kwargs = call_args[1]
                json_body = kwargs["json"]
                
                # Check if the user message in payload has the injection
                sent_messages = json_body["messages"]
                last_msg = sent_messages[-1]
                self.assertEqual(last_msg["role"], "user")
                self.assertTrue(last_msg["content"].startswith("/think high\n\nhello"))

        asyncio.run(run_test())

    def test_ollama_thinking_injection_off(self):
        async def run_test():
            provider = OllamaProvider()
            
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"message": {"content": "ok"}}
                
                # Test with thinking off
                messages: list[Message] = [{"role": "user", "content": "hello"}]
                await provider.chat(messages, model="kimi", thinking_level="off")
                
                call_args = mock_post.call_args
                json_body = call_args[1]["json"]
                last_msg = json_body["messages"][-1]
                
                self.assertEqual(last_msg["content"], "hello")
                self.assertNotIn("/think", last_msg["content"])

        asyncio.run(run_test())

    def test_openrouter_include_reasoning(self):
        async def run_test():
            provider = OpenRouterProvider()
            
            # Mock openai client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="ok", tool_calls=None))],
                id="test-id",
                model="kimi",
                usage=None
            )
            
            with patch("app.providers.openrouter.AsyncOpenAI", return_value=mock_client):
                messages: list[Message] = [{"role": "user", "content": "hello"}]
                
                # Test with thinking high
                await provider.chat(messages, model="kimi", thinking_level="high")
                
                # Verify kwargs sent to create
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                
                # Check reasoning_effort (might be mapped to high)
                self.assertEqual(call_kwargs.get("reasoning_effort"), "high")
                
                # Check include_reasoning in extra_body
                extra_body = call_kwargs.get("extra_body", {})
                self.assertTrue(extra_body.get("include_reasoning"))

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
