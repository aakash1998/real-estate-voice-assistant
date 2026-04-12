import os
import asyncio
import time
from elevenlabs import ElevenLabs
from elevenlabs.play import play
from dotenv import load_dotenv
import io

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

async def speak(text: str) -> tuple[float, asyncio.Task]:
    print(f"[TTS] Converting to audio...")

    start = time.time()

    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2",
        output_format="mp3_44100_128"
    )

    audio_bytes = b"".join(chunk for chunk in audio)
    tts_latency = (time.time() - start) * 1000
    print(f"[TTS] {tts_latency:.0f}ms")

    async def play_audio():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, play, io.BytesIO(audio_bytes))

    # Return the task so pipeline can wait for it
    play_task = asyncio.create_task(play_audio())

    return tts_latency, play_task

async def speak_to_buffer(text: str) -> tuple[bytes, float]:
    """For phone pipeline - returns audio bytes and latency"""
    print(f"[TTS] Converting to audio...")

    start = time.time()

    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2",
        output_format="ulaw_8000"
    )

    audio_bytes = b"".join(chunk for chunk in audio)
    tts_latency = (time.time() - start) * 1000

    print(f"[TTS] {tts_latency:.0f}ms")

    return audio_bytes, tts_latency