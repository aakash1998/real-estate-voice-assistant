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

async def transcribe_mic(on_transcript):
    deepgram = DeepgramClient(DEEPGRAM_API_KEY)
    audio_queue = asyncio.Queue()

    options = LiveOptions(
        model="nova-2",
        language="en-US",
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        interim_results=True,
        endpointing=1000
    )

    loop = asyncio.get_event_loop()

    def audio_callback(indata, frames, time, status):
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    max_reconnects = 3
    reconnect_count = 0

    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype='int16',
        callback=audio_callback
    ):
        while reconnect_count <= max_reconnects:
            # Flag to detect if connection succeeded
            connected = asyncio.Event()
            failed = asyncio.Event()

            connection = deepgram.listen.asynclive.v("1")

            async def on_open(self, open, **kwargs):
                print("[ASR] Connected to Deepgram")
                connected.set()

            async def on_message(self, result, **kwargs):
                try:
                    transcript = result.channel.alternatives[0].transcript
                    if transcript.strip() and not hasattr(on_message, '_speech_start'):
                        on_message._speech_start = time.time()

                    if result.is_final and transcript.strip():
                        speech_start = getattr(on_message, '_speech_start', None)
                        if speech_start is None:
                            speech_start = time.time()
                        asr_latency = (time.time() - speech_start) * 1000
                        on_message._speech_start = None
                        asyncio.create_task(on_transcript(transcript, asr_latency))

                except Exception as e:
                    print(f"[ASR] Message error: {e}")

            async def on_error(self, error, **kwargs):
                print(f"[ASR] Error: {error}")
                failed.set()

            async def on_close(self, close, **kwargs):
                print("[ASR] Connection closed")
                failed.set()

            connection.on(LiveTranscriptionEvents.Open, on_open)
            connection.on(LiveTranscriptionEvents.Transcript, on_message)
            connection.on(LiveTranscriptionEvents.Error, on_error)
            connection.on(LiveTranscriptionEvents.Close, on_close)

            await connection.start(options)

            # Wait up to 3 seconds to see if connection succeeds or fails
            try:
                done, _ = await asyncio.wait(
                    [
                        asyncio.create_task(connected.wait()),
                        asyncio.create_task(failed.wait())
                    ],
                    timeout=3.0,
                    return_when=asyncio.FIRST_COMPLETED
                )

                if not done or failed.is_set():
                    raise Exception("Connection failed or timed out")

            except Exception as e:
                reconnect_count += 1
                print(f"[ASR] Connection failed: {e}")

                if reconnect_count > max_reconnects:
                    print(f"[ASR] Max reconnects ({max_reconnects}) reached - shutting down")
                    break

                print(f"[ASR] Will retry in 2 seconds...")
                await asyncio.sleep(2)
                continue

            if reconnect_count == 0:
                print("[ASR] Listening... speak now")
            else:
                print("[ASR] Reconnected successfully")

            reconnect_count = 0

            # Send audio loop
            blocked_count = 0
            try:
                while True:
                    data = await audio_queue.get()
                    if not _is_speaking:
                        if blocked_count > 0:
                            print(f"[ASR] Resuming - blocked {blocked_count} chunks while speaking")
                            blocked_count = 0
                        await connection.send(data)
                    else:
                        blocked_count += 1
            except Exception as e:
                reconnect_count += 1
                print(f"[ASR] Connection lost during streaming: {e}")
                if reconnect_count > max_reconnects:
                    print(f"[ASR] Max reconnects ({max_reconnects}) reached - shutting down")
                    break
                print(f"[ASR] Will retry in 2 seconds...")
                await asyncio.sleep(2)

    print("[ASR] Mic stream ended")