
import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Setup paths to import app
current = Path(__file__).resolve().parent
sys.path.append(str(current / "backend"))

# Load environment variables
env_path = current / "backend" / ".env"
load_dotenv(env_path)

async def query_rag(text):
    print(f"Querying RAG for: '{text}'")
    try:
        from app.rag.service import get_rag
        
        rag = get_rag()
        
        # 1. List topics to verify what's there
        topics = rag.list_topics()
        print("\n--- Learned Topics ---")
        for t in topics:
            print(f"- {t['topic']} ({t['chunks_count']} chunks)")
            
        # 2. Query
        summary = await rag.query(text, k=3)
        print(f"\n--- Query Result for '{text}' ---")
        if summary:
            print(summary)
        else:
            print("No relevant content found.")
            
        # 3. Dump topic content
        print("\n--- Topic Content for 'esimo' ---")
        content = rag.get_topic_content("esimo")
        with open("esimo_dump.txt", "w") as f:
            f.write(content)
        print(f"Dumped {len(content)} chars to esimo_dump.txt")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(query_rag(sys.argv[1]))
    else:
        print("Usage: python query_rag.py <query>")
