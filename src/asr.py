import os
import asyncio
import sounddevice as sd
import numpy as np
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def transcribe_mic(on_transcript):
    """
    Opens a live WebSocket connection to Deepgram.
    Uses a queue to safely pass audio from the mic thread to async code.
    Calls on_transcript() when a final sentence is detected.
    """
    deepgram = DeepgramClient(DEEPGRAM_API_KEY)
    connection = deepgram.listen.asynclive.v("1")
    audio_queue = asyncio.Queue()

    async def on_message(self, result, **kwargs):
        try:
            transcript = result.channel.alternatives[0].transcript
            if result.is_final and transcript.strip():
                print(f"[ASR] Final transcript: {transcript}")
                await on_transcript(transcript)
        except Exception as e:
            print(f"[ASR] Message parse error: {e}")

    async def on_error(self, error, **kwargs):
        print(f"[ASR] Error: {error}")

    connection.on(LiveTranscriptionEvents.Transcript, on_message)
    connection.on(LiveTranscriptionEvents.Error, on_error)

    options = LiveOptions(
        model="nova-2",
        language="en-US",
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        interim_results=True,
        endpointing=500
    )

    await connection.start(options)
    print("[ASR] Listening... speak now")

    loop = asyncio.get_event_loop()

    def audio_callback(indata, frames, time, status):
        # Safely put audio data into the queue from the mic thread
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    async def send_audio():
        while True:
            data = await audio_queue.get()
            await connection.send(data)

    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype='int16',
        callback=audio_callback
    ):
        await send_audio()