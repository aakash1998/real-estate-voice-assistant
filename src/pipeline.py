import asyncio
import time
from .asr import transcribe_mic, set_speaking
from .llm import get_llm_response
from .tts import speak
from .broadcaster import broadcast, start_broadcaster

is_speaking = False

async def handle_transcript(transcript: str, asr_latency: float):
    global is_speaking

    if is_speaking:
        return

    print(f"\n[ASR] {asr_latency:.0f}ms → {transcript}")

    # Tell dashboard user spoke
    await broadcast({
        "type": "transcript",
        "text": transcript,
        "asr_latency": asr_latency
    })

    total_start = time.time()

    # Get LLM response
    response, llm_latency = await get_llm_response(transcript)

    # Tell dashboard LLM responded
    await broadcast({
        "type": "llm_response",
        "text": response,
        "llm_latency": llm_latency
    })

    is_speaking = True
    set_speaking(True)

    # Tell dashboard TTS is generating
    tts_latency, play_task = await speak(response)

    total_latency = (time.time() - total_start) * 1000

    # Tell dashboard full latency report
    await broadcast({
        "type": "latency_report",
        "asr": asr_latency,
        "llm": llm_latency,
        "tts": tts_latency,
        "total": total_latency
    })

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

    # Tell dashboard speaking started
    await broadcast({"type": "speaking"})

    # Wait for audio to finish
    await play_task
    await asyncio.sleep(0.5)

    is_speaking = False
    set_speaking(False)

    # Tell dashboard ready for next question
    await broadcast({"type": "ready"})
    print("[PIPELINE] Ready for next question...")

async def main():
    print("=== Real Estate Voice Assistant ===")
    print("Ask me anything about properties, leases, or rent.")
    print("Press Ctrl+C to stop.\n")

    # Start dashboard broadcaster
    await start_broadcaster()

    # Start voice pipeline
    await transcribe_mic(handle_transcript)

if __name__ == "__main__":
    asyncio.run(main())