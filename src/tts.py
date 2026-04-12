import os
import io
import time
import asyncio
from elevenlabs import ElevenLabs
from elevenlabs.play import play
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Fallback if ElevenLabs fails
FALLBACK_MESSAGE = "I'm having trouble with my voice right now. Please try again."

async def _generate_audio(text: str, output_format: str) -> bytes:
    """
    Single attempt to generate audio from ElevenLabs.
    Runs in executor so timeout can be applied.
    """
    def _call():
        audio = client.text_to_speech.convert(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_turbo_v2",
            output_format=output_format
        )
        return b"".join(chunk for chunk in audio)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)

async def speak(text: str) -> tuple[float, asyncio.Task]:
    """
    For local pipeline - generates audio and plays it.
    - 10 second timeout
    - 1 automatic retry
    - Fallback to simple message if both fail
    """
    print(f"[TTS] Converting to audio...")

    start = time.time()
    audio_bytes = None

    for attempt in range(2):
        try:
            if attempt > 0:
                print(f"[TTS] Retrying... attempt {attempt + 1}")

            audio_bytes = await asyncio.wait_for(
                _generate_audio(text, "mp3_44100_128"),
                timeout=10.0
            )
            break  # Success - exit retry loop

        except asyncio.TimeoutError:
            print(f"[TTS] Timeout on attempt {attempt + 1}")
        except Exception as e:
            print(f"[TTS] Error on attempt {attempt + 1}: {e}")

    # If both attempts failed use fallback
    if audio_bytes is None:
        print("[TTS] Both attempts failed - using fallback")
        try:
            audio_bytes = await _generate_audio(
                FALLBACK_MESSAGE, "mp3_44100_128"
            )
        except Exception as e:
            print(f"[TTS] Fallback also failed: {e}")
            # Return empty task if everything fails
            tts_latency = (time.time() - start) * 1000
            return tts_latency, asyncio.create_task(asyncio.sleep(0))

    tts_latency = (time.time() - start) * 1000
    print(f"[TTS] {tts_latency:.0f}ms")

    async def play_audio():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, play, io.BytesIO(audio_bytes))

    play_task = asyncio.create_task(play_audio())
    return tts_latency, play_task

async def speak_to_buffer(text: str) -> tuple[bytes, float]:
    """
    For phone pipeline - returns audio bytes and latency.
    Same resilience pattern as speak().
    """
    print(f"[TTS] Converting to audio...")

    start = time.time()
    audio_bytes = None

    for attempt in range(2):
        try:
            print(f"[TTS] Attempting with timeout 0.001")  # add this
            audio_bytes = await asyncio.wait_for(
                _generate_audio(text, "mp3_44100_128"),
                timeout=10.0
            )
            break

        except asyncio.TimeoutError:
            print(f"[TTS] Timeout on attempt {attempt + 1}")
        except Exception as e:
            print(f"[TTS] Error on attempt {attempt + 1}: {e}")

    if audio_bytes is None:
        print("[TTS] Both attempts failed - using fallback")
        try:
            audio_bytes = await _generate_audio(
                FALLBACK_MESSAGE, "ulaw_8000"
            )
        except Exception as e:
            print(f"[TTS] Fallback also failed: {e}")
            audio_bytes = b""

    tts_latency = (time.time() - start) * 1000
    print(f"[TTS] {tts_latency:.0f}ms")
    return audio_bytes, tts_latency