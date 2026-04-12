import asyncio
from .asr import transcribe_mic
from .llm import get_llm_response
from .tts import speak

is_speaking = False

async def handle_transcript(transcript: str):
    """
    Called every time ASR detects a final transcript.
    Sends to LLM then speaks the response.
    Ignores input while assistant is speaking.
    """
    global is_speaking

    if is_speaking:
        print("[PIPELINE] Ignoring transcript - assistant is speaking")
        return

    print(f"[PIPELINE] Transcript received: {transcript}")

    response = await get_llm_response(transcript)

    is_speaking = True
    await speak(response)
    # Wait 1 second after speaking so mic doesn't pick up leftover audio
    await asyncio.sleep(1)
    is_speaking = False

    print("[PIPELINE] Ready for next question...")

async def main():
    print("=== Real Estate Voice Assistant ===")
    print("Ask me anything about properties, leases, or rent.")
    print("Press Ctrl+C to stop.\n")

    await transcribe_mic(handle_transcript)

if __name__ == "__main__":
    asyncio.run(main())