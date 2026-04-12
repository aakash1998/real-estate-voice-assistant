import os
import yaml
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Load system prompt from config file
with open("config/prompts.yaml", "r") as f:
    config = yaml.safe_load(f)
    SYSTEM_PROMPT = config["system_prompt"]

# Initialize Groq client once (not every request)
client = Groq(api_key=GROQ_API_KEY)

async def get_llm_response(transcript: str) -> str:
    """
    Sends transcript to Groq and returns response text.
    System prompt loaded from prompts.yaml — not hardcoded.
    Answers kept short because they will be spoken out loud.
    """
    print(f"[LLM] Sending to Groq: {transcript}")

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # Fast Groq model
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript}
        ],
        max_tokens=150,  # Keep responses short for voice
        temperature=0.7
    )

    answer = response.choices[0].message.content
    print(f"[LLM] Response: {answer}")
    return answer