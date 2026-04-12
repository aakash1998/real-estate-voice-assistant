# Real Estate Voice Assistant

A production-grade real-time AI voice agent built for Avenue Living — a Canadian real estate company. Callers can ask questions about properties, leases, and rentals by voice and receive instant spoken answers.

This project is not a tutorial follow-along. Every component is built with production engineering principles — real-time streaming, latency instrumentation, resilience, and graceful failure handling.

---

## Why I Built This

Most AI voice demos are single API calls wrapped in a script. This project focuses on the real engineering challenges behind a production voice system:

- How do you stream audio in real time without blocking?
- How do you measure and budget latency across multiple components?
- What happens when Deepgram, Groq, or ElevenLabs goes down mid-call?
- How do you prevent a voice assistant from listening to its own voice?

These are the problems production AI teams deal with every day. This project addresses all of them.

---

## Architecture

```
Local Pipeline:
Microphone → [Deepgram] → text → [Groq LLM] → response → [ElevenLabs] → Speaker

Phone Pipeline:
Caller's Phone → [Twilio] → [ngrok] → [FastAPI] → [Deepgram] → [Groq] → [ElevenLabs] → [Twilio] → Caller's Phone
```

Each component is built and tested in **complete isolation** before being wired together. This makes debugging fast and keeps the codebase clean.

---

## Tech Stack

| Component | Tool | Why |
|---|---|---|
| Speech to Text | Deepgram (nova-2) | Real-time streaming, low latency |
| LLM Inference | Groq (llama-3.1-8b) | Fastest inference available, critical for real-time feel |
| Text to Speech | ElevenLabs (turbo v2) | Natural voice, fast generation |
| Phone Integration | Twilio | Real phone number, production-grade call handling |
| Public Tunnel | ngrok | Exposes local server to Twilio |
| Server | FastAPI + uvicorn | Async WebSocket support |
| Audio Streaming | WebSockets | Persistent connection for continuous audio flow |
| Concurrency | asyncio | Handles mic, Deepgram, LLM, TTS simultaneously |

---

## Project Structure

```
real-estate-voice-assistant/
├── src/
│   ├── asr.py          # Ears — mic streaming → Deepgram → transcript
│   ├── llm.py          # Brain — transcript → Groq → response
│   ├── tts.py          # Mouth — response → ElevenLabs → audio
│   ├── pipeline.py     # Local orchestration — wires all three together
│   └── server.py       # Phone orchestration — Twilio WebSocket handler
├── config/
│   └── prompts.yaml    # System prompts versioned separately from code
├── data/
│   └── properties.json # Avenue Living property data
├── tests/
│   ├── test_asr.py     # Isolated ASR test
│   ├── test_llm.py     # Isolated LLM test
│   └── test_tts.py     # Isolated TTS test
├── docs/
│   └── architecture.md # Design decisions and known tradeoffs
├── .env                # API keys (never committed)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.13+
- Homebrew (Mac)
- ffmpeg: `brew install ffmpeg`
- ngrok: `brew install ngrok`

### Installation

```bash
# Clone the repo
git clone <your-repo-url>
cd real-estate-voice-assistant

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Mac/Linux

# Install dependencies
venv/bin/pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_number
```

---

## Running the Assistant

### Local Pipeline (mic + speaker)

```bash
venv/bin/python -m src.pipeline
```

Speak a question — the assistant transcribes, thinks, and responds out loud.

### Phone Pipeline (real phone call)

Terminal 1 — start ngrok:
```bash
ngrok http 8000
```

Terminal 2 — start server:
```bash
venv/bin/python -m uvicorn src.server:app --port 8000 --reload
```

Set the ngrok URL in Twilio console:
```
https://your-ngrok-url.ngrok-free.dev/incoming-call
```

Call your Twilio number and speak naturally.

---

## Latency Instrumentation

Every component is individually instrumented. After each response, a latency report prints to the terminal:

```
┌─────────────────────────────┐
│      LATENCY REPORT         │
├─────────────────────────────┤
│ ASR (Deepgram):    1500ms   │
│ LLM (Groq):         500ms   │
│ TTS (ElevenLabs):   700ms   │
│ TOTAL:             1200ms   │
└─────────────────────────────┘
```

**What each number means:**
- **ASR** — how long you were speaking until Deepgram confirmed the full sentence
- **LLM** — how long Groq took to generate the response
- **TTS** — how long ElevenLabs took to generate the audio (not play it)
- **TOTAL** — LLM + TTS combined. This is what the user feels as "response time"

**Typical numbers observed:**
- LLM (Groq): 400–700ms
- TTS (ElevenLabs): 500–900ms
- Total response: consistently under 1.7 seconds

**Key insight:** TTS latency scales with response length. Constraining the LLM to 1–2 sentence answers keeps TTS consistently under 900ms.

---

## Resilience

Each component has independent failure handling:

### Groq (LLM)
- 5 second timeout per attempt
- 1 automatic retry on failure
- Graceful fallback message if both attempts fail
- Uses `asyncio.wait_for()` with `run_in_executor()` for non-blocking timeout

### ElevenLabs (TTS)
- 10 second timeout per attempt
- 1 automatic retry on failure
- Graceful fallback message spoken if both attempts fail
- Known limitation: fallback still depends on ElevenLabs. Production version would use a pre-recorded audio file

### Deepgram (ASR)
- Connection failure detected via Open/Close/Error event listeners
- 3 automatic reconnection attempts
- 2 second backoff between each attempt
- Graceful shutdown after max reconnects reached

---

## Key Engineering Decisions

### Why separate STT, LLM, and TTS instead of an all-in-one tool?
Deepgram offers a Voice Agent product that handles all three. We chose separate tools for control, debuggability, and the ability to swap any component independently. This also makes latency measurement per-component possible.

### Why Groq instead of OpenAI?
Groq's inference speed is significantly faster than OpenAI for equivalent models. In a real-time voice system, every 100ms matters. Groq consistently responds in under 700ms vs OpenAI's 1500ms+ for similar quality.

### Why block audio chunks during TTS playback?
If the mic stays open while the assistant speaks, Deepgram transcribes the assistant's own voice and sends it as a new question — creating an infinite loop. We solve this by pausing audio transmission to Deepgram during playback, not just ignoring transcripts.

### Why use a queue between the mic thread and async code?
The sounddevice mic callback runs in a separate OS thread. Directly calling async functions from that thread causes a `RuntimeError: no event loop`. A thread-safe queue bridges the two worlds cleanly.

### Why endpointing=1000ms?
Deepgram uses silence duration to detect end of speech. 500ms was too aggressive and cut sentences mid-thought. 1000ms gives natural pauses without feeling slow.

---

## Known Limitations & Production Gaps

| Limitation | Current Behavior | Production Fix |
|---|---|---|
| TTS fallback depends on ElevenLabs | If ElevenLabs is fully down, fallback also fails | Pre-recorded audio file stored locally |
| No conversation memory | Each question treated independently | Maintain conversation history per session |
| Endpointing cuts long pauses | 1000ms pause = sentence complete | Utterance-end detection + LLM intent check |
| Property data is static JSON | Hardcoded for development | Vector database with RAG pipeline |
| Single tenant | One conversation at a time | Session management per caller |

---

## Phase Progress

- [x] Phase 1 — Core Voice Pipeline (mic → Deepgram → Groq → ElevenLabs)
- [x] Phase 2 — Latency Tracking (per-component instrumentation)
- [x] Phase 3 — Resilience (timeouts, retries, graceful fallbacks)
- [ ] Phase 4 — Apply resilience to phone pipeline
- [ ] Phase 5 — Live dashboard visualization
- [ ] Phase 6 — Demo prep and polish

---

## What I Learned

1. **Threading and async don't mix without a queue.** The mic callback runs in a thread. Async code runs in an event loop. Without a queue between them, nothing works.

2. **Blocking calls kill real-time systems.** `play()` from ElevenLabs blocks the event loop. Running it in an executor keeps audio flowing while the response plays.

3. **Measuring latency is harder than it looks.** Naive total timers include audio playback time, which inflates the number. Separating generation time from playback time gives the real engineering metric.

4. **The gap between a demo and a production system is enormous.** Silence handling, mic feedback loops, connection drops, and partial transcripts are invisible in tutorials but constant in real systems.