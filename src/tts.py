import os
import asyncio
from elevenlabs import ElevenLabs
from elevenlabs.play import play
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

async def speak(text: str):
    """
    Converts text to speech using ElevenLabs and plays it.
    Runs play() in a thread so it doesn't block the event loop.
    This keeps audio streaming to Deepgram while speaking.
    """
    print(f"[TTS] Speaking: {text}")

    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2",
        output_format="mp3_44100_128"
    )

    # Run play in a thread - keeps event loop free while speaking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, play, audio)
    
    print("[TTS] Done speaking")