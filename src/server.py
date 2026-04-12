import os
import json
import base64
import asyncio
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Connect
from deepgram import DeepgramClient, LiveOptions
from dotenv import load_dotenv
from .llm import get_llm_response
from .tts import speak_to_buffer

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

app = FastAPI()

@app.post("/incoming-call")
async def incoming_call(request: Request):
    """
    Twilio calls this when someone dials our number.
    We respond with TwiML telling Twilio to stream 
    audio to our websocket.
    """
    host = request.headers.get("host")

    response = VoiceResponse()
    response.say(
        "Hello! Welcome to Avenue Living. I am your AI leasing assistant. How can I help you today?",
        voice="Polly.Joanna"
    )

    connect = Connect()
    connect.stream(url=f"wss://{host}/audio-stream")
    response.append(connect)

    return Response(
        content=str(response),
        media_type="application/xml"
    )

@app.websocket("/audio-stream")
async def audio_stream(websocket: WebSocket):
    """
    Handles real time audio streaming from Twilio.
    Pipes audio through Deepgram → Groq → ElevenLabs
    and sends response back to caller.
    """
    await websocket.accept()
    print("[SERVER] Call connected")

    # Initialize Deepgram
    deepgram = DeepgramClient(DEEPGRAM_API_KEY)
    dg_connection = deepgram.listen.asynclive.v("1")
    audio_queue = asyncio.Queue()
    is_speaking = False
    stream_sid = None

    async def on_transcript(self, result, **kwargs):
        nonlocal is_speaking
        try:
            transcript = result.channel.alternatives[0].transcript
            if result.is_final and transcript.strip():
                print(f"[ASR] Transcript: {transcript}")

                if is_speaking:
                    print("[SERVER] Ignoring - assistant is speaking")
                    return

                # Get LLM response
                response_text = await get_llm_response(transcript)

                # Convert to audio bytes
                is_speaking = True
                audio_bytes = await speak_to_buffer(response_text)

                # Send audio back to Twilio
                if audio_bytes and stream_sid:
                    payload = base64.b64encode(audio_bytes).decode("utf-8")
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": payload}
                    })

                await asyncio.sleep(0.5)
                is_speaking = False

        except Exception as e:
            print(f"[SERVER] Transcript error: {e}")

    dg_connection.on("Results", on_transcript)

    options = LiveOptions(
        model="nova-2",
        language="en-US",
        encoding="mulaw",    # Twilio uses mulaw format
        channels=1,
        sample_rate=8000,    # Twilio uses 8000Hz (phone quality)
        interim_results=True,
        endpointing=500
    )

    await dg_connection.start(options)

    async def send_audio():
        while True:
            data = await audio_queue.get()
            await dg_connection.send(data)

    asyncio.create_task(send_audio())

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data["event"] == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"[SERVER] Stream started: {stream_sid}")

            elif data["event"] == "media":
                # Decode base64 audio from Twilio and queue it
                audio = base64.b64decode(data["media"]["payload"])
                audio_queue.put_nowait(audio)

            elif data["event"] == "stop":
                print("[SERVER] Stream stopped")
                break

    except Exception as e:
        print(f"[SERVER] Error: {e}")
    finally:
        await dg_connection.finish()
        print("[SERVER] Call disconnected")