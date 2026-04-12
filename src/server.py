import os
import asyncio
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from dotenv import load_dotenv
from .llm import get_llm_response
from .tts import speak

load_dotenv()

app = FastAPI()

@app.post("/incoming-call")
async def incoming_call(request: Request):
    """
    Twilio calls this when someone dials our number.
    We respond with TwiML instructions telling Twilio
    to stream audio to our /audio-stream websocket.
    """
    host = request.headers.get("host")
    
    response = VoiceResponse()
    response.say(
        "Hello! Welcome to Avenue Living. I'm your AI leasing assistant. How can I help you today?",
        voice="Polly.Joanna"
    )
    
    # Tell Twilio to stream audio to our websocket
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
    Twilio streams caller audio here in real time.
    We pipe it through Deepgram → Groq → ElevenLabs
    and send the response back to the caller.
    """
    await websocket.accept()
    print("[SERVER] Call connected - audio streaming started")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[SERVER] Received audio data")
    except Exception as e:
        print(f"[SERVER] Call ended: {e}")
    finally:
        print("[SERVER] Call disconnected")