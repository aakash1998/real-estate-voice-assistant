import os
import json
import time
import asyncio
import yaml
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

with open("data/properties.json", "r") as f:
    PROPERTIES = json.load(f)

with open("config/prompts.yaml", "r") as f:
    config = yaml.safe_load(f)
    SYSTEM_PROMPT = config["system_prompt"]

client = Groq(api_key=GROQ_API_KEY)

# Fallback message if Groq fails completely
FALLBACK_RESPONSE = "I'm having a technical issue right now. Please try again in a moment."

async def call_groq(transcript: str) -> str:
    """
    Single attempt to call Groq.
    Runs in executor so we can apply asyncio timeout to it.
    """
    properties_context = f"""
REAL AVENUE LIVING PROPERTIES - USE ONLY THESE, NOTHING ELSE:
{json.dumps(PROPERTIES, indent=2)}

User question: {transcript}

Answer ONLY using the properties above. If the answer is not in the data, say: 
"I don't have that information, but I've noted your question and someone from our team will follow up shortly."
"""
    def _call():
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": properties_context}
            ],
            max_tokens=150,
            temperature=0.0
        )
        return response.choices[0].message.content

    # Run blocking Groq call in executor
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)

async def get_llm_response(transcript: str) -> tuple[str, float]:
    """
    Calls Groq with:
    - 5 second timeout
    - 1 automatic retry if first attempt fails
    - Graceful fallback message if both attempts fail
    """
    print(f"[LLM] Sending to Groq: {transcript}")

    start = time.time()

    for attempt in range(2):  # Try max 2 times
        try:
            if attempt > 0:
                print(f"[LLM] Retrying... attempt {attempt + 1}")

            # Apply 5 second timeout
            answer = await asyncio.wait_for(
                call_groq(transcript),
                timeout=5.0
            )

            llm_latency = (time.time() - start) * 1000
            print(f"[LLM] {llm_latency:.0f}ms → {answer}")
            return answer, llm_latency

        except asyncio.TimeoutError:
            print(f"[LLM] Timeout on attempt {attempt + 1} - Groq took over 5 seconds")

        except Exception as e:
            print(f"[LLM] Error on attempt {attempt + 1}: {e}")

    # Both attempts failed - use fallback
    llm_latency = (time.time() - start) * 1000
    print(f"[LLM] Both attempts failed - using fallback response")
    return FALLBACK_RESPONSE, llm_latency