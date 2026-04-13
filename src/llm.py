import os
import json
import time
import asyncio
import yaml
from groq import Groq
from dotenv import load_dotenv
from .embed_properties import search_properties
from .memory import HybridMemory

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

with open("config/prompts.yaml", "r") as f:
    config = yaml.safe_load(f)
    SYSTEM_PROMPT = config["system_prompt"]

client = Groq(api_key=GROQ_API_KEY)

FALLBACK_RESPONSE = "I'm having a technical issue right now. Please try again in a moment."

# One memory instance per session
# In production this would be per-caller session
memory = HybridMemory(window_size=4, summary_threshold=10)

async def call_groq(
    transcript: str,
    relevant_properties: list,
    conversation_history: list
) -> str:
    """
    Single attempt to call Groq with:
    - Relevant properties from RAG
    - Full conversation history from memory
    """
    properties_text = "\n\n".join([
        f"Property {i+1}:\n{r['document']}"
        for i, r in enumerate(relevant_properties)
    ])

    # Build messages array
    # 1. System prompt
    # 2. Conversation history (summary + recent)
    # 3. Current question with relevant properties
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # Add conversation history
    messages.extend(conversation_history)

    # Add current question with RAG context
    messages.append({
        "role": "user",
        "content": f"""
RELEVANT PROPERTIES FOR THIS QUERY:
{properties_text}

User question: {transcript}

Answer ONLY using the properties above.
If the answer is not in the data say:
"I don't have that information, but I've noted your question and someone from our team will follow up shortly."
"""
    })

    def _call():
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=150,
            temperature=0.0
        )
        return response.choices[0].message.content

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)

async def get_llm_response(transcript: str) -> tuple[str, float]:
    """
    Full pipeline:
    1. Search ChromaDB for relevant properties
    2. Get conversation history from memory
    3. Send to Groq with full context
    4. Update memory with new exchange
    5. Summarize if needed
    """
    print(f"[LLM] Searching ChromaDB for: {transcript}")

    # Step 1 — RAG search
    loop = asyncio.get_event_loop()
    relevant_properties = await loop.run_in_executor(
        None, search_properties, transcript, 3
    )

    print(f"[LLM] Retrieved {len(relevant_properties)} relevant properties:")
    for r in relevant_properties:
        print(f"      → {r['name']} (score: {r['relevance_score']:.3f})")

    # Step 2 — Get conversation history
    conversation_history = memory.get_context()

    start = time.time()

    for attempt in range(2):
        try:
            if attempt > 0:
                print(f"[LLM] Retrying... attempt {attempt + 1}")

            answer = await asyncio.wait_for(
                call_groq(transcript, relevant_properties, conversation_history),
                timeout=10.0
            )

            llm_latency = (time.time() - start) * 1000

            # Step 3 — Update memory with this exchange
            memory.add_message("user", transcript)
            memory.add_message("assistant", answer)

            # Step 4 — Summarize if needed (runs in background)
            asyncio.create_task(memory.maybe_summarize())

            # Print memory status every exchange
            memory.status()

            print(f"[LLM] {llm_latency:.0f}ms → {answer}")
            return answer, llm_latency

        except asyncio.TimeoutError:
            print(f"[LLM] Timeout on attempt {attempt + 1}")
        except Exception as e:
            print(f"[LLM] Error on attempt {attempt + 1}: {e}")

    llm_latency = (time.time() - start) * 1000
    print(f"[LLM] Both attempts failed - using fallback")
    return FALLBACK_RESPONSE, llm_latency

def reset_memory():
    """Call this when a conversation ends."""
    memory.clear()