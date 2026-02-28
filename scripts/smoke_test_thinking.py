
import asyncio
import os
import sys
import sqlite3

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "../backend/.env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

from app.providers.openrouter import OpenRouterProvider
from app.providers.ollama import OllamaProvider
from app.thinking_capabilities import supports_xhigh_thinking

def get_key_from_db():
    try:
        db_path = os.path.join(os.path.dirname(__file__), "../backend/asta.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM api_keys WHERE key_name='openrouter_api_key'")
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception as e:
        print(f"DB Error: {e}")
    return None

async def run_smoke_test():
    print("--- Starting Smoke Test for Thinking Capabilities ---")

    # 1. OpenRouter Kimi/Trinity
    or_provider = OpenRouterProvider()
    
    # Try getting key from env, then DB
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        api_key = get_key_from_db()
        if api_key:
            print("INFO: Found OpenRouter key in database.")
            # Inject into environment for the provider to pick up if needed, 
            # though usually provider reads from app settings. 
            # OpenRouterProvider in asta might read from os.environ or settings.
            # Let's check config.py... it reads os.environ['OPENROUTER_API_KEY'] usually via BaseSettings.
            os.environ["OPENROUTER_API_KEY"] = api_key
            # Re-instantiate to be sure
            or_provider = OpenRouterProvider()
    
    if not api_key:
        print("SKIPPING OpenRouter: No OPENROUTER_API_KEY found in environment, .env, or database.")
    else:
        # Discover available models
        print("Discovering Kimi/Trinity models on OpenRouter...")
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://openrouter.ai/api/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    all_models = data.get("data", [])
                    # Find candidates
                    kimi_candidates = [m["id"] for m in all_models if "kimi" in m["id"] or "moonshot" in m["id"]]
                    trinity_candidates = [m["id"] for m in all_models if "trinity" in m["id"]]
                    
                    print(f"Found Kimi models: {kimi_candidates}")
                    print(f"Found Trinity models: {trinity_candidates}")
                    
                    models_to_test = []
                    if kimi_candidates:
                        models_to_test.append(kimi_candidates[0])
                    if trinity_candidates:
                        models_to_test.append(trinity_candidates[0])
                    
                    if not models_to_test:
                        print("WARNING: No Kimi/Trinity models found via API. Using defaults.")
                        models_to_test = ["moonshot/moonshot-v1-8k"]
                else:
                    print(f"Failed to list models: {resp.status_code}")
                    models_to_test = ["moonshot/moonshot-v1-8k"]
        except Exception as e:
            print(f"Error listing models: {e}")
            models_to_test = ["moonshot/moonshot-v1-8k"]

        print(f"Testing models: {models_to_test}")

        for model in models_to_test:
            print(f"\nTesting OpenRouter Model: {model}")
            messages = [{"role": "user", "content": "How many r's in strawberry? Think carefully."}]
            try:
                # We expect include_reasoning=True to be sent.
                # Note: Some models return reasoning in 'reasoning' field, others in content.
                resp = await or_provider.chat(messages, model=model, thinking_level="high")
                
                if resp.error:
                    print(f"Response Error: {resp.error_message or resp.error}")
                else:
                    print(f"Response Content (First 200 chars): {resp.content[:200]}...")
                
                # Check directly in content for markers
                if "<think>" in resp.content or "Reasoning" in resp.content or "reasoning_token" in str(resp):
                    print("SUCCESS: Found thinking tokens/markers!")
                else:
                    print("NOTE: No explicit <think> tags found in content. (This is common for some providers that separate reasoning).")

            except Exception as e:
                print(f"FAILED OpenRouter test for {model}: {e}")

            # Test Streaming
            print(f"\nTesting OpenRouter Model ({model}) - STREAMING:")
            try:
                # Mock callback to verify streaming event emission if needed, but return value has full content
                async def noop(delta): pass
                
                resp_stream = await or_provider.chat_stream(
                    messages, 
                    model=model, 
                    thinking_level="high",
                    on_text_delta=noop
                )
                if "<think>" in resp_stream.content:
                    print("SUCCESS: Found <think> tags in stream output!")
                    # print snippet
                    start = resp_stream.content.find("<think>")
                    end = resp_stream.content.find("</think>")
                    print(f"Thinking Snippet: {resp_stream.content[start:end+8][:100]}...")
                else:
                    print("NOTE: No <think> tags in stream output.")
            except Exception as e:
                print(f"Stream Error: {e}")

    # 2. Ollama Kimi (User specified Kimi k2.5)
    print("\n--- Testing Ollama ---")
    ollama_provider = OllamaProvider()
    # User said "kimi k2.5 on ollama"
    model = "kimi-k2.5" 
    # Validating support for this specific model ID tag
    print(f"Capabilities Check (Ollama {model}): {supports_xhigh_thinking('ollama', model)}")
    
    messages = [{"role": "user", "content": "How many r's in strawberry?"}]
    try:
        print(f"Sending prompt to local Ollama (model={model})...")
        resp = await ollama_provider.chat(messages, model=model, thinking_level="high")
        if resp.error:
             print(f"Ollama Error: {resp.error_message}")
             if "not found" in (resp.error_message or "").lower():
                 print("Hint: Ensure you have pulled the model locally: `ollama pull kimi`")
        else:
             print(f"Ollama Response: {resp.content[:200]}...")
             if "<think>" in resp.content or "/think" in resp.content:
                 if "/think" in resp.content and "<think>" not in resp.content:
                     print("WARNING: Model echoed the command. It might not support /think injection.")
                 else:
                     print("SUCCESS: Found <think> tags!")
             else:
                 print("NOTE: No <think> tags found.")
    except Exception as e:
        print(f"FAILED Ollama test: {e}")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
