import asyncio
import os
import sys
import requests
from dotenv import load_dotenv, find_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(find_dotenv(usecwd=True))

MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME") or os.getenv("MONGODB_DB_NAME", "aanandi_sales")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def get_query_embedding(query: str):
    if OPENROUTER_API_KEY:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/text-embedding-3-small",
                    "input": query
                },
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
        except Exception as e:
            print(f"[Embedding Error via OpenRouter] {e}")

    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-dummy"):
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            res = await client.embeddings.create(model="text-embedding-3-small", input=query)
            return res.data[0].embedding
        except Exception as e:
            print(f"[Embedding Error via OpenAI] {e}")

    return None

async def test_search(query: str = "What live projects and apps has Aanandi built?"):
    if not MONGODB_URI:
        print("Error: MONGODB_URI or MONGODB_URL is not configured in .env")
        sys.exit(1)

    print(f"Connecting to MongoDB database '{DATABASE_NAME}'...")
    print(f"Executing search for: \"{query}\"\n")

    mongo = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = mongo[DATABASE_NAME]

    # 1. Try vector search
    q_vec = await get_query_embedding(query)
    results = []
    if q_vec:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": q_vec,
                    "numCandidates": 50,
                    "limit": 3
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "title": 1,
                    "content": 1,
                    "category": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        try:
            results = await db.knowledge_chunks.aggregate(pipeline).to_list(length=3)
            print("=== [Atlas Vector Search Results] ===")
        except Exception as e:
            print(f"Atlas Vector Search bypassed ({e}). Falling back to database search...")

    # 2. Database Text / Regex search if vector search gave nothing
    if not results:
        try:
            cursor = db.knowledge_chunks.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}, "title": 1, "content": 1, "category": 1}
            ).sort([("score", {"$meta": "textScore"})]).limit(3)
            results = await cursor.to_list(length=3)
            if results:
                print("=== [MongoDB Text Search Results] ===")
        except Exception:
            pass

    if not results:
        # Regex search
        import re
        words = [re.escape(w) for w in query.split() if len(w) > 3]
        if words:
            pattern = "|".join(words)
            cursor = db.knowledge_chunks.find({
                "$or": [
                    {"title": {"$regex": pattern, "$options": "i"}},
                    {"content": {"$regex": pattern, "$options": "i"}},
                    {"category": {"$regex": pattern, "$options": "i"}}
                ]
            }).limit(3)
            results = await cursor.to_list(length=3)
            if results:
                print("=== [MongoDB Regex Match Results] ===")

    if not results:
        print("No matching knowledge chunks found in database.")
    else:
        for r in results:
            title = r.get("title", "Untitled")
            content = r.get("content", "")
            category = r.get("category", "general")
            print(f"--- [Category: {category}] ---")
            print(f"Title: {title}")
            print(f"Content:\n{content[:250]}...\n")

    mongo.close()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "What live projects and apps has Aanandi built?"
    asyncio.run(test_search(q))
