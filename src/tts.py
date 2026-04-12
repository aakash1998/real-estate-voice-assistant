import os
from elevenlabs import ElevenLabs
from elevenlabs.play import play
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

async def speak(text: str):
    """
    Converts text to speech using ElevenLabs and plays it.
    Uses a natural sounding voice suitable for real estate assistant.
    """
    print(f"[TTS] Speaking: {text}")

    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",  # George - clear professional voice
        model_id="eleven_turbo_v2",         # Fastest model - important for real time
        output_format="mp3_44100_128"
    )

    play(audio)
    print("[TTS] Done speaking")