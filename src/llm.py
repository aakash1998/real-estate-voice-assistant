import os
import json
import yaml
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Load real property data
with open("data/properties.json", "r") as f:
    PROPERTIES = json.load(f)

with open("config/prompts.yaml", "r") as f:
    config = yaml.safe_load(f)
    SYSTEM_PROMPT = config["system_prompt"]

client = Groq(api_key=GROQ_API_KEY)

async def get_llm_response(transcript: str) -> str:
    """
    Sends transcript to Groq with real property data injected.
    Properties are loaded from JSON - not just the prompt.
    """
    print(f"[LLM] Sending to Groq: {transcript}")

    # Inject real property data into every single request
    properties_context = f"""
REAL AVENUE LIVING PROPERTIES - USE ONLY THESE, NOTHING ELSE:
{json.dumps(PROPERTIES, indent=2)}

User question: {transcript}

Answer ONLY using the properties above. If the answer is not in the data, say: 
"I don't have that information, but I've noted your question and someone from our team will follow up shortly."
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": properties_context}
        ],
        max_tokens=150,
        temperature=0.0  # Zero temperature = no creativity, stick to facts
    )

    answer = response.choices[0].message.content
    print(f"[LLM] Response: {answer}")
    return answer