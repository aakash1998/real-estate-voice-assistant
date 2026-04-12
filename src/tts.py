import os
import asyncio
import io
from elevenlabs import ElevenLabs
from elevenlabs.play import play
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

async def speak(text: str):
    """For local pipeline - plays audio through speaker"""
    print(f"[TTS] Speaking: {text}")
    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2",
        output_format="mp3_44100_128"
    )
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, play, audio)
    print("[TTS] Done speaking")

async def speak_to_buffer(text: str) -> bytes:
    """
    For phone pipeline - returns audio as bytes
    instead of playing through speaker.
    Twilio needs mulaw 8000Hz format.
    """
    print(f"[TTS] Converting to audio: {text}")
    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2",
        output_format="ulaw_8000"  # Twilio's required format
    )
    # Collect all audio chunks into bytes
    audio_bytes = b"".join(chunk for chunk in audio)
    print("[TTS] Audio ready")
    return audio_bytes