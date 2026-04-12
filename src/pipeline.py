import asyncio
import time
from .asr import transcribe_mic, set_speaking
from .llm import get_llm_response
from .tts import speak

is_speaking = False

async def handle_transcript(transcript: str, asr_latency: float):
    global is_speaking

    if is_speaking:
        print("[PIPELINE] Ignoring - assistant is speaking")
        return

    print(f"\n[ASR] {asr_latency:.0f}ms → {transcript}")

    total_start = time.time()

    response, llm_latency = await get_llm_response(transcript)

    is_speaking = True
    set_speaking(True)  # Stop sending mic audio to Deepgram
    
    tts_latency, play_task = await speak(response)

    total_latency = (time.time() - total_start) * 1000

    print(f"""
┌─────────────────────────────┐
│      LATENCY REPORT         │
├─────────────────────────────┤
│ ASR (Deepgram):  {asr_latency:>6.0f}ms   │
│ LLM (Groq):      {llm_latency:>6.0f}ms   │
│ TTS (ElevenLabs):{tts_latency:>6.0f}ms   │
│ TOTAL:           {total_latency:>6.0f}ms   │
└─────────────────────────────┘
""")

    # Wait for audio to finish playing
    await play_task
    await asyncio.sleep(0.5)
    
    is_speaking = False
    set_speaking(False)  # Resume sending mic audio to Deepgram
    print("[PIPELINE] Ready for next question...")

async def main():
    print("=== Real Estate Voice Assistant ===")
    print("Ask me anything about properties, leases, or rent.")
    print("Press Ctrl+C to stop.\n")

    await transcribe_mic(handle_transcript)

if __name__ == "__main__":
    asyncio.run(main())