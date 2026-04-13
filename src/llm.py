import os
import json
import time
import asyncio
import yaml
from groq import Groq
from dotenv import load_dotenv
from .embed_properties import search_properties

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

with open("config/prompts.yaml", "r") as f:
    config = yaml.safe_load(f)
    SYSTEM_PROMPT = config["system_prompt"]

client = Groq(api_key=GROQ_API_KEY)

FALLBACK_RESPONSE = "I'm having a technical issue right now. Please try again in a moment."

async def call_groq(transcript: str, relevant_properties: list) -> str:
    """
    Single attempt to call Groq.
    Only receives relevant properties from RAG — not all 36.
    """
    # Format only the relevant properties
    properties_text = "\n\n".join([
        f"Property {i+1}:\n{r['document']}"
        for i, r in enumerate(relevant_properties)
    ])

    user_message = f"""
RELEVANT PROPERTIES FOR THIS QUERY:
{properties_text}

User question: {transcript}

Answer ONLY using the properties above.
If the answer is not in the data say:
"I don't have that information, but I've noted your question and someone from our team will follow up shortly."
"""

    def _call():
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.0
        )
        return response.choices[0].message.content

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)

async def get_llm_response(transcript: str) -> tuple[str, float]:
    """
    Full RAG pipeline:
    1. Search ChromaDB for relevant properties
    2. Re-rank results
    3. Send only relevant properties to Groq
    """
    print(f"[LLM] Searching ChromaDB for: {transcript}")

    # Step 1 — RAG search (sync, run in executor)
    loop = asyncio.get_event_loop()
    relevant_properties = await loop.run_in_executor(
        None, search_properties, transcript, 3
    )

    print(f"[LLM] Retrieved {len(relevant_properties)} relevant properties:")
    for r in relevant_properties:
        print(f"      → {r['name']} (score: {r['relevance_score']:.3f})")

    start = time.time()

    for attempt in range(2):
        try:
            if attempt > 0:
                print(f"[LLM] Retrying... attempt {attempt + 1}")

            answer = await asyncio.wait_for(
                call_groq(transcript, relevant_properties),
                timeout=10.0
            )

            llm_latency = (time.time() - start) * 1000
            print(f"[LLM] {llm_latency:.0f}ms → {answer}")
            return answer, llm_latency

        except asyncio.TimeoutError:
            print(f"[LLM] Timeout on attempt {attempt + 1}")
        except Exception as e:
            print(f"[LLM] Error on attempt {attempt + 1}: {e}")

    llm_latency = (time.time() - start) * 1000
    print(f"[LLM] Both attempts failed - using fallback")
    return FALLBACK_RESPONSE, llm_latency