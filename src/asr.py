import os
import time
import asyncio
import sounddevice as sd
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

_is_speaking = False

def set_speaking(state: bool):
    global _is_speaking
    _is_speaking = state

# Update send_audio function
async def send_audio():
    while True:
        data = await audio_queue.get()
        if not _is_speaking:
            await connection.send(data)

async def transcribe_mic(on_transcript):
    """
    Streams mic audio to Deepgram.
    Tracks ASR latency and passes it to callback.
    """
    deepgram = DeepgramClient(DEEPGRAM_API_KEY)
    connection = deepgram.listen.asynclive.v("1")
    audio_queue = asyncio.Queue()
    speech_start_time = None

    async def on_message(self, result, **kwargs):
        nonlocal speech_start_time
        try:
            transcript = result.channel.alternatives[0].transcript

            if transcript.strip() and speech_start_time is None:
                # First word detected - start ASR stopwatch
                speech_start_time = time.time()

            if result.is_final and transcript.strip():
                # Calculate ASR latency
                asr_latency = (time.time() - speech_start_time) * 1000
                speech_start_time = None  # Reset for next question

                asyncio.create_task(on_transcript(transcript, asr_latency))

        except Exception as e:
            print(f"[ASR] Error: {e}")

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
        endpointing=1000
    )

    await connection.start(options)
    print("[ASR] Listening... speak now")

    loop = asyncio.get_event_loop()

    def audio_callback(indata, frames, time, status):
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    async def send_audio():
        blocked_count = 0
        while True:
            data = await audio_queue.get()
            if not _is_speaking:
                if blocked_count > 0:
                    print(f"[ASR] Resuming - blocked {blocked_count} chunks while speaking")
                    blocked_count = 0
                await connection.send(data)
            else:
                blocked_count += 1

    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype='int16',
        callback=audio_callback
    ):
        await send_audio()
