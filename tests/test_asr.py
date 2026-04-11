import asyncio
from src.asr import transcribe_mic

async def handle_transcript(text):
    print(f"[TEST] Got transcript: {text}")

asyncio.run(transcribe_mic(handle_transcript))