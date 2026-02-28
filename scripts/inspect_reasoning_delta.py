
import asyncio
import os
import sys
import sqlite3
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "../backend/.env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

from openai import AsyncOpenAI

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

async def inspect():
    key = os.getenv("OPENROUTER_API_KEY") or get_key_from_db()
    if not key:
        print("No key found.")
        return

    client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    
    # Trinity or DeepSeek 
    # model = "arcee-ai/trinity-large-preview:free"
    model = "deepseek/deepseek-r1:free"
    
    print(f"Testing {model} with stream=True, include_reasoning=True, reasoning_effort='high'...")
    
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Count to 3 and explain why."}],
            stream=True,
            extra_body={"include_reasoning": True},
            reasoning_effort="high"  # Some models might ignore this but good to try
        )
        
        print("\n--- Stream Deltas ---")
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                # Dump delta to see fields
                d_dict = delta.model_dump()
                
                # Check for reasoning fields
                reasoning = d_dict.get("reasoning")
                content = d_dict.get("content")
                
                if reasoning:
                    print(f"[REASONING]: {reasoning}")
                if content:
                    print(f"[CONTENT]: {content}", end="", flush=True)
                
                # Also check if it's in some other field
                if "reasoning" not in d_dict and "reasoning_details" not in d_dict:
                    # check extra fields
                    pass
                    
        print("\n--- End of Stream ---")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect())
