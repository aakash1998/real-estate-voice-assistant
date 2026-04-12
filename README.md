# 🎙️ Real Estate Voice Assistant

> A production-grade, real-time AI voice agent that answers property questions over a live phone call — built with streaming audio, per-component latency instrumentation, resilience engineering, and a live operations dashboard.

![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat-square&logo=python)
![Status](https://img.shields.io/badge/Status-Active-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## 📺 Demo

> **LinkedIn Post:** [ADD LINKEDIN POST LINK HERE]
>
> **What you will see in the demo:**
> - A real phone call being answered by the AI agent
> - Live dashboard updating in real time with transcripts and latency metrics
> - Natural conversational flow — the agent asks qualifying questions before suggesting properties
> - Per-component latency breakdown: ASR, LLM, TTS, and total response time

---

## 🧠 What This Is

Most AI voice demos are a single API call wrapped in a script. You paste some text, call an LLM, and play audio. That is not engineering — that is glue code.

This project focuses on the real engineering challenges behind a production voice system:

- How do you stream audio continuously without blocking the event loop?
- How do you measure and budget latency across three independent components?
- What happens when Deepgram drops mid-call? When Groq times out? When ElevenLabs fails?
- How do you prevent a voice assistant from listening to and responding to its own voice?
- How do you display all of this in a live operations dashboard that updates in real time?

These are the problems that production AI teams deal with every day. This project addresses all of them.

---

## 🏗️ Architecture

### Local Pipeline
```
Microphone
    │
    ▼ (raw audio chunks via sounddevice)
[Thread-safe asyncio Queue]
    │
    ▼ (streaming WebSocket - linear16, 16000Hz)
[Deepgram nova-2 ASR]
    │
    ▼ (final transcript only)
[Groq llama-3.1-8b-instant]
    │
    ▼ (response text, max 2 sentences)
[ElevenLabs eleven_turbo_v2 TTS]
    │
    ▼ (mp3_44100_128 audio bytes)
Speaker Output
```

### Phone Pipeline
```
Caller Phone
    │
    ▼ (PSTN call)
[Twilio +1 xxx-xxx-xxxx]
    │
    ▼ (WebSocket audio stream - mulaw, 8000Hz)
[ngrok public tunnel]
    │
    ▼
[FastAPI Server - port 8000]
    │
    ▼
[Deepgram nova-2 ASR]
    │
    ▼
[Groq llama-3.1-8b-instant]
    │
    ▼
[ElevenLabs eleven_turbo_v2 TTS - ulaw_8000]
    │
    ▼
[Twilio] ──▶ Caller's Phone
```

### Dashboard Architecture
```
[Pipeline - src/pipeline.py]
    │
    ▼ (broadcast events via websockets)
[Broadcaster - src/broadcaster.py - port 8765]
    │
    ▼ (WebSocket ws://localhost:8765)
[Dashboard - static/dashboard.html]

Events broadcast:              Dashboard panels:
· transcript (user spoke)      · Live Transcript panel
· llm_response (AI replied)    · Latency Monitor panel
· latency_report (numbers)     · Component Status panel
· speaking (TTS started)       · Session Analytics panel
· ready (TTS finished)         · Voice Waveform panel
· interim (partial transcript)
```

---

## 🛠️ Tech Stack

### Core Components

| Component | Tool | Model / Version | Why This Over Alternatives |
|---|---|---|---|
| Speech to Text | Deepgram | nova-2 | Real-time streaming WebSocket API. Whisper is too slow for live conversation — tested and rejected. |
| LLM Inference | Groq | llama-3.1-8b-instant | 3-5x faster than OpenAI for equivalent quality. Critical for sub-2s total latency. Temperature 0.0 for factual consistency. |
| Text to Speech | ElevenLabs | eleven_turbo_v2 | Most natural voice at lowest latency. turbo v2 specifically optimized for real-time streaming. Voice: George (ID: JBFqnCBsd6RMkjVDRZzb). |
| Phone Integration | Twilio | Latest | Industry standard for programmatic phone calls. Real phone number, production-grade call handling. |
| Public Tunnel | ngrok | v3 | Exposes local FastAPI server to Twilio during development. |
| Web Server | FastAPI + uvicorn | Latest | Async-first framework. Native WebSocket support essential for Twilio audio streaming. |
| Audio Capture | sounddevice | 0.5.5 | Low-level mic access with callback pattern. Runs in separate OS thread — requires queue bridge to async code. |
| Concurrency | asyncio | Python stdlib | Single-threaded event loop handles mic, ASR, LLM, TTS simultaneously without threading complexity. |
| Dashboard | Vanilla HTML/CSS/JS | — | No framework overhead. Native WebSocket API. Loads instantly with no build step. |
| Dashboard Transport | websockets | Latest | Lightweight async WebSocket server for broadcasting pipeline events to dashboard. |

### Audio Format Details

| Pipeline | Format | Sample Rate | Encoding | Why |
|---|---|---|---|---|
| Local (mic) | LINEAR16 | 16000 Hz | Raw PCM | Standard for speech recognition. Low overhead. |
| Local (speaker) | MP3 | 44100 Hz | 128kbps | High quality for local playback. |
| Phone (Twilio in) | mulaw | 8000 Hz | G.711 | Twilio's native phone audio format. |
| Phone (Twilio out) | ulaw_8000 | 8000 Hz | G.711 | ElevenLabs format that matches Twilio's expectation. |

### Model Configuration

**Deepgram:**
```
model: nova-2
language: en-US
encoding: linear16
channels: 1
sample_rate: 16000
interim_results: true
endpointing: 1000ms
```

**Groq:**
```
model: llama-3.1-8b-instant
max_tokens: 150
temperature: 0.0
```
Temperature 0.0 means zero creativity — the model sticks strictly to facts in the property data. Any higher and it starts hallucinating property details.

**ElevenLabs:**
```
voice_id: JBFqnCBsd6RMkjVDRZzb  (George - clear, professional)
model_id: eleven_turbo_v2
output_format (local): mp3_44100_128
output_format (phone): ulaw_8000
```

---

## 📁 Project Structure

```
real-estate-voice-assistant/
│
├── src/                        # All application code
│   ├── __init__.py             # Makes src a Python package
│   ├── asr.py                  # Ears — mic streaming → Deepgram → transcript
│   │                           # Also handles: reconnect logic, speaking flag, queue
│   ├── llm.py                  # Brain — transcript → Groq → response
│   │                           # Also handles: timeout, retry, fallback, property data injection
│   ├── tts.py                  # Mouth — response → ElevenLabs → audio
│   │                           # Also handles: timeout, retry, fallback, executor threading
│   ├── pipeline.py             # Local orchestrator — wires ASR + LLM + TTS
│   │                           # Also handles: latency reporting, dashboard broadcasting
│   ├── server.py               # Phone orchestrator — Twilio WebSocket handler
│   │                           # Also handles: mulaw audio format, stream SID management
│   └── broadcaster.py          # Dashboard WebSocket server on port 8765
│                               # Manages connected clients, broadcasts pipeline events
│
├── static/
│   └── dashboard.html          # Live operations dashboard
│                               # Self-contained HTML/CSS/JS, no build step required
│
├── config/
│   └── prompts.yaml            # System prompts versioned separately from code
│                               # Versioned in git so prompt changes are tracked
│
├── data/
│   └── properties.json         # 10 synthetic properties for demo purposes
│                               # NOT real data. See Known Limitations.
│
├── tests/
│   ├── test_asr.py             # Isolated ASR test — mic → Deepgram → print transcript
│   ├── test_llm.py             # Isolated LLM test — hardcoded text → Groq → print response
│   └── test_tts.py             # Isolated TTS test — hardcoded text → ElevenLabs → play audio
│
├── docs/
│   └── architecture.md         # Extended design decisions and known tradeoffs
│
├── .env                        # API keys — never committed to git
├── .gitignore                  # Includes .env, venv/, __pycache__/
├── requirements.txt            # All Python dependencies with versions
└── README.md                   # This file
```

---

## ⚙️ Setup and Installation

### Prerequisites

- **Python 3.13+** — check with `python3 --version`
- **Homebrew** (Mac) — install from brew.sh
- **ffmpeg** — required by ElevenLabs for audio playback

```bash
brew install ffmpeg
```

Why ffmpeg? ElevenLabs `play()` function uses ffmpeg under the hood to decode and play MP3 audio. Without it you get a silent error or crash.

- **ngrok** — only needed for phone pipeline

```bash
brew install ngrok
```

### Important: Virtual Environment and Anaconda

If you have Anaconda installed, it overrides your virtual environment's Python. Always use the full path to the venv Python:

```bash
# Instead of:
python -m src.pipeline        # Uses Anaconda Python — WRONG

# Always use:
venv/bin/python -m src.pipeline   # Uses venv Python — CORRECT
```

Verify you are using the right Python:
```bash
venv/bin/python -c "import deepgram; print('OK')"
```

### Step 1 — Clone and create virtual environment

```bash
git clone <your-repo-url>
cd real-estate-voice-assistant

python3 -m venv venv
source venv/bin/activate
```

### Step 2 — Install dependencies

```bash
venv/bin/pip install -r requirements.txt
```

### Step 3 — Create .env file

```bash
touch .env
```

Add the following:

```
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_number
```

Where to get API keys:
- Deepgram: console.deepgram.com — $200 free credits on signup
- Groq: console.groq.com — generous free tier
- ElevenLabs: elevenlabs.io — 10,000 characters/month free
- Twilio: twilio.com — $15 trial credits on signup

Verify your keys are loading correctly:
```bash
venv/bin/python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DEEPGRAM_API_KEY'))"
```

### Step 4 — Run the local pipeline

```bash
venv/bin/python -m src.pipeline
```

### Step 5 — Open the dashboard

```bash
open static/dashboard.html
```

The dashboard auto-connects to the pipeline broadcaster on `ws://localhost:8765`. If the pipeline is not running, the dashboard shows a "Connection lost. Retrying..." screen and reconnects automatically when the pipeline starts.

### Step 6 — Run the phone pipeline (optional)

Terminal 1 — start ngrok tunnel:
```bash
ngrok http 8000
```

Copy the forwarding URL (e.g. `https://abc123.ngrok-free.dev`)

Terminal 2 — start FastAPI server:
```bash
venv/bin/python -m uvicorn src.server:app --port 8000 --reload
```

In Twilio console → Phone Numbers → your number → Configure → set webhook:
```
https://abc123.ngrok-free.dev/incoming-call
```

Method: HTTP POST. Save. Call your Twilio number.

---

## 🧪 Running Tests

Each module has an isolated test. Run these to verify individual components work before running the full pipeline.

### Test ASR (Deepgram)
```bash
venv/bin/python -m tests.test_asr
```
What it does: Opens mic, streams to Deepgram, prints transcript to terminal.
Pass criteria: Speak a sentence — see it printed accurately within 1-2 seconds.

### Test LLM (Groq)
```bash
venv/bin/python -m tests.test_llm
```
What it does: Sends a hardcoded real estate question to Groq, prints response.
Pass criteria: Receives a relevant, accurate response about the properties in the data.

### Test TTS (ElevenLabs)
```bash
venv/bin/python -m tests.test_tts
```
What it does: Sends hardcoded text to ElevenLabs, plays audio through speaker.
Pass criteria: You hear the text spoken out loud in a natural voice.

Run all three in sequence before your first full pipeline test. If any test fails, fix that module before proceeding.

---

## 🖥️ Dashboard Guide

The live operations dashboard (`static/dashboard.html`) connects to the pipeline via WebSocket on port 8765 and updates in real time as conversations happen.

### Panel Breakdown

**Live Transcript (left panel)**
Shows the full conversation history. User messages appear in cyan, agent responses in amber. Each message shows the speaker role, timestamp, and ASR latency for user messages.

**Latency Monitor (right panel)**
Shows per-component latency bars and values for the most recent exchange. Colors indicate performance:
- Green: excellent performance
- Amber: acceptable performance
- Red: slow, needs attention

**Component Status (right panel)**
Shows real-time state of each component:
- LISTENING — Deepgram is receiving audio
- RECEIVING — Deepgram is processing speech
- PROCESSING — Groq is generating response
- GENERATING — ElevenLabs is creating audio
- SPEAKING — Audio is playing
- IDLE — Component is waiting

**Session Analytics (bottom panel)**
Running statistics for the current session: total exchanges, average LLM latency, average TTS latency, average total response time.

**Voice Waveform (bottom panel)**
Animated waveform that activates when the agent is speaking.

### Dashboard Troubleshooting

If the dashboard shows "Connection lost. Retrying..." it means the pipeline is not running. Start the pipeline first, then the dashboard will auto-connect.

If the dashboard connects but shows no data, check that port 8765 is free:
```bash
lsof -ti:8765 | xargs kill -9
```

Then restart the pipeline.

### Common Port Conflict Fix

If you see `OSError: [Errno 48] address already in use` when starting the pipeline, a previous session was suspended with Ctrl+Z instead of stopped with Ctrl+C.

Always use Ctrl+C to stop the pipeline — never Ctrl+Z.

To fix a stuck port:
```bash
lsof -ti:8765 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

---

## 🔬 How It Works — Deep Dive

### 1. Audio Streaming and The Queue Problem

The mic callback (sounddevice) runs in a separate OS thread. Directly calling async functions from that thread raises:

```
RuntimeError: There is no current event loop in thread 'Dummy-1'
```

The fix is a thread-safe asyncio queue:

```
Mic Thread (OS thread)              Async Event Loop (main thread)
        │                                       │
        │  audio chunk arrives                  │
        ├──── loop.call_soon_threadsafe ───────▶│
        │     (audio_queue.put_nowait)           │
        │                                       │  await audio_queue.get()
        │                                       ├────────────────────────▶ Deepgram.send()
```

This completely decouples the mic thread from async code. No race conditions, no blocking, no thread locks needed.

### 2. Preventing Mic Feedback Loop

When the assistant speaks, the mic picks up the speaker output and Deepgram transcribes it as a new question — creating an infinite response loop.

Naive fix (does not work reliably): ignore transcripts while `is_speaking == True`. The problem is the last few words of a TTS response finish playing just after `is_speaking` becomes False — those words slip through as a new question.

Real fix: stop sending audio chunks to Deepgram entirely while speaking:

```
Audio chunk arrives from mic
    │
    ├── _is_speaking == True?  ──▶ Drop chunk silently. Deepgram never sees it.
    └── _is_speaking == False? ──▶ Send chunk to Deepgram normally.
```

When TTS finishes: `_is_speaking = False`, audio resumes flowing to Deepgram.

### 3. Blocking vs Non-Blocking TTS

ElevenLabs `play()` is a blocking synchronous call. Calling it directly in async code freezes the entire event loop for the duration of audio playback. While frozen:
- Deepgram receives no audio → connection times out
- No new messages can be processed
- Dashboard updates stop

Fix: run `play()` in a thread executor:

```python
loop = asyncio.get_event_loop()
await loop.run_in_executor(None, play, io.BytesIO(audio_bytes))
```

`run_in_executor` runs the blocking call in a background thread while the event loop stays free. Audio plays while everything else continues normally.

### 4. Latency Measurement Methodology

Each component is timed independently using `time.time()`:

```
User stops speaking
        │ t_asr_start = time.time()
        ▼
Deepgram sends is_final=True transcript
        │ asr_latency = (time.time() - t_asr_start) * 1000
        │ t_llm_start = time.time()
        ▼
Groq returns response text
        │ llm_latency = (time.time() - t_llm_start) * 1000
        │ t_tts_start = time.time()
        ▼
ElevenLabs returns complete audio bytes
        │ tts_latency = (time.time() - t_tts_start) * 1000
        ▼
Audio begins playing (NOT measured)

TOTAL = llm_latency + tts_latency
```

ASR latency is measured separately and reported but not included in TOTAL — it represents how long the user was speaking, not a processing bottleneck.

Audio playback time is explicitly excluded from all measurements. It is not a bottleneck we can control and including it inflates the metric misleadingly.

### 5. Deepgram Reconnect Detection

The Deepgram SDK v3 swallows connection errors internally and does not raise them to application code. Detecting disconnection requires listening to WebSocket lifecycle events:

```python
connection.on(LiveTranscriptionEvents.Open, on_open)    # Sets connected flag
connection.on(LiveTranscriptionEvents.Error, on_error)  # Sets failed flag
connection.on(LiveTranscriptionEvents.Close, on_close)  # Sets failed flag
```

After calling `connection.start()`, we wait up to 3 seconds for either the `connected` or `failed` event using `asyncio.wait()`. If `failed` fires or timeout occurs, we increment the reconnect counter and try again.

---

## 📊 Latency Metrics Explained

### What Each Metric Means

| Metric | What It Measures | Typical Range | Primary Drivers |
|---|---|---|---|
| ASR (Deepgram) | How long the user was speaking | 1000-4000ms | Speech length, endpointing setting |
| LLM (Groq) | Time from transcript sent to response received | 400-800ms | Model load, response length, token count |
| TTS (ElevenLabs) | Time from text sent to audio bytes returned | 500-2000ms | Response text length (linear relationship) |
| TOTAL | LLM + TTS combined | 900-2500ms | What the user actually perceives as delay |

### Performance Benchmarks Observed

```
TOTAL < 1000ms ── Excellent. Sub-second feels completely instant.
TOTAL < 1500ms ── Good. Natural conversation speed. Most exchanges.
TOTAL < 2500ms ── Acceptable. Slight delay noticeable but tolerable.
TOTAL > 2500ms ── Poor. Conversation feels broken. Investigate immediately.
```

### Key Insight: TTS Latency Scales With Response Length

This was the single most impactful optimization discovered during development. A response of 3 sentences takes approximately 3x longer to generate audio for than a 1 sentence response. The system prompt enforces a strict maximum of 2 sentences per response specifically for this reason.

Effect: TTS latency reduced from average 1800ms to average 700ms after enforcing response length limits. A 60% improvement with zero infrastructure changes.

### How to Read the Dashboard Latency Bars

Each bar represents the component's latency as a proportion of 3000ms (the maximum expected value). A bar at 50% width means 1500ms. Colors indicate:

- Green fill: under threshold (LLM < 500ms, TTS < 600ms, Total < 1000ms)
- Amber fill: within acceptable range
- Red fill: above threshold, investigate

---

## 🛡️ Resilience

### Groq (LLM) Resilience

| Scenario | Detection | Response |
|---|---|---|
| Response takes > 5 seconds | `asyncio.wait_for(timeout=5.0)` | TimeoutError raised |
| Timeout on attempt 1 | Exception caught | Retry attempt 2 automatically |
| Timeout on attempt 2 | Exception caught | Speak fallback message to user |
| Any other exception | Exception caught | Same retry and fallback flow |
| System after failure | Automatic | Ready for next question immediately |

Fallback message: "I'm having a technical issue right now. Please try again in a moment."

### ElevenLabs (TTS) Resilience

| Scenario | Detection | Response |
|---|---|---|
| Audio generation takes > 10 seconds | `asyncio.wait_for(timeout=10.0)` | TimeoutError raised |
| Timeout on attempt 1 | Exception caught | Retry attempt 2 automatically |
| Both attempts fail | `audio_bytes is None` check | Attempt fallback message generation |
| Fallback also fails | Exception caught | Return empty audio, system continues |

Known limitation: The fallback message itself calls ElevenLabs without a timeout. If ElevenLabs is completely down, the fallback will also fail. Production fix: pre-recorded fallback audio file stored locally.

### Deepgram (ASR) Resilience

| Scenario | Detection | Response |
|---|---|---|
| HTTP 401 (bad API key) | `failed` event fires | Reconnect attempt triggered |
| Connection rejected | `failed` event or 3s timeout | Reconnect attempt triggered |
| Connection dropped mid-call | Send fails with exception | Reconnect attempt triggered |
| Reconnect attempt 1-3 | Counter incremented | 2 second backoff between attempts |
| Max reconnects reached (3) | Counter > max | Graceful shutdown with clear message |
| Successful reconnect | `connected` event fires | Counter reset to 0, continue normally |

---

## ⭐ Honest Project Rating

### Current Rating: 6.5 / 10

This is an honest assessment without inflation.

### What Earns the 6.5

- **Real threading patterns** — Queue between mic thread and async is a genuine production pattern, not a tutorial shortcut
- **Per-component latency instrumentation** — Most projects measure nothing. This measures everything separately and displays it live
- **Three-layer resilience** — Timeout, retry, and fallback on every component. Nothing crashes silently
- **Mic feedback prevention** — Diagnosing and solving the self-listening loop required real debugging, not following instructions
- **Isolated module testing** — Every module tested independently before wiring. Proper engineering discipline
- **Live operations dashboard** — Real-time WebSocket dashboard with latency bars, component status, waveform, and session analytics
- **Conversational prompt engineering** — Agent asks qualifying questions, suggests max 2 properties, flows like a real leasing agent
- **Temperature 0.0 enforcement** — Zero creativity prevents hallucination on factual property data

### What Prevents a Higher Score

- **No RAG pipeline** — Property data is a hardcoded JSON file. A real system uses a vector database with semantic search and citation enforcement
- **No conversation memory** — Every question is treated independently. No multi-turn context within the same call
- **No evaluation framework** — No automated script to test questions and measure answer quality, faithfulness, or hallucination rate
- **Incomplete phone pipeline** — Twilio integration works but lacks the same resilience as the local pipeline
- **No concurrent sessions** — One conversation at a time. Production handles multiple simultaneous callers
- **Static property data** — No real-time availability updates, no pricing sync, no database backend
- **Pre-recorded fallback missing** — TTS fallback depends on ElevenLabs being available

---

## 🗺️ Roadmap to 10 / 10

### Priority 1 — RAG Pipeline (+1.0 → 7.5)

Replace properties.json with a proper vector database.

```
What to build:
· Embed all property data using text-embedding-3-small
· Store embeddings in ChromaDB or Pinecone
· Replace JSON lookup in llm.py with semantic search
· Add citation enforcement (only answer from retrieved chunks)
· Add faithfulness score to latency report

Tools: LangChain, ChromaDB, OpenAI Embeddings
Estimated complexity: 3-5 days
Impact: Eliminates hallucination risk, enables real-time data updates
```

### Priority 2 — Conversation Memory (+0.5 → 8.0)

Maintain conversation history per session.

```
What to build:
· Session ID generated per call
· Rolling message history (last 10 exchanges stored in memory)
· Full history passed to Groq on every request
· Session cleared when call ends or times out

Tools: Python dict, Redis for production scale
Estimated complexity: 1 day
Impact: Agent remembers context within a call ("you mentioned a 2 bedroom earlier")
```

### Priority 3 — Evaluation Framework (+0.5 → 8.5)

Automated quality testing on every change.

```
What to build:
· Golden dataset: 50 test questions with verified expected answers
· Offline eval script measuring faithfulness, accuracy, hallucination rate
· CI integration: eval runs automatically on every git commit
· Quality gate: build fails if score drops below 80%
· Latency regression gate: build fails if average total > 2000ms

Tools: RAGAS, pytest, GitHub Actions
Estimated complexity: 2-3 days
Impact: Prevents regressions, proves quality with data not intuition
```

### Priority 4 — Concurrent Sessions (+0.5 → 9.0)

Handle multiple simultaneous callers.

```
What to build:
· Session manager class with UUID per caller
· Isolated state per session (is_speaking, conversation history, latency history)
· Thread-safe session storage
· Session timeout and cleanup for abandoned calls (> 5 minutes idle)
· Per-session dashboard metrics

Tools: asyncio, UUID, Redis for distributed storage
Estimated complexity: 3-5 days
Impact: Makes the system actually usable in production
```

### Priority 5 — Production Hardening (+0.5 → 9.5)

```
What to build:
· Structured JSON logging with trace IDs per request
· Prometheus metrics endpoint (/metrics)
· Health check endpoint (/health)
· Docker containerization with docker-compose
· Pre-recorded fallback audio file for complete TTS failure
· Environment-based configuration (dev/staging/prod)

Tools: structlog, Prometheus, Docker
Estimated complexity: 2-3 days
Impact: Observable, deployable, genuinely production-ready
```

### Priority 6 — Real Data Backend (+0.5 → 10.0)

```
What to build:
· PostgreSQL or Supabase backend for property data
· Real-time availability sync from property management system
· Admin panel for property managers
· Booking confirmation flow with email notifications
· Webhook integration for CRM updates

Tools: Supabase, FastAPI, SQLAlchemy, SendGrid
Estimated complexity: 1-2 weeks
Impact: Commercially deployable product
```

---

## 🧩 Key Engineering Decisions

### Why separate STT + LLM + TTS instead of an all-in-one tool?

Deepgram offers a Voice Agent product handling all three. Separate tools were chosen for five reasons: per-component latency measurement is only possible with separation; each component can fail and recover independently; any component can be swapped without touching others; debugging is significantly clearer when something fails; and the engineering decisions made along the way demonstrate deeper understanding than calling a single managed API.

### Why Groq instead of OpenAI?

Groq responds in 400-700ms consistently. OpenAI GPT-4o averages 1200-1500ms for equivalent outputs. In a real-time voice system, 800ms of additional latency is immediately perceptible by the caller. The tradeoff is slightly less reasoning capability — acceptable for a leasing agent answering structured questions about a known property dataset. Temperature was set to 0.0 on both to ensure fair comparison.

### Why endpointing=1000ms?

500ms was tested first and rejected. It cut sentences mid-thought when users paused naturally — a common occurrence in conversational speech. 1500ms was tested and made the system feel unresponsive. 1000ms is the sweet spot: generous enough for natural pauses, tight enough to feel responsive.

### Why block audio chunks during TTS rather than just ignoring transcripts?

Ignoring transcripts while `is_speaking == True` was the first approach. It failed because Deepgram streams results slightly after speech ends — the last few words of the TTS response arrive at Deepgram in the window between TTS finishing and `is_speaking` being set to False. Those words trigger a new question. Blocking at the source (never sending audio to Deepgram while speaking) eliminates the race condition entirely.

### Why prompts in YAML instead of hardcoded strings?

A prompt change can affect system behavior as dramatically as a code change. A competitor's name accidentally mentioned, a constraint removed, an instruction reordered — all can break a production system. Versioning prompts in a config file means every prompt change appears in git history with a commit message, is reviewable in pull requests, and is rollback-able in seconds. This is standard practice in production AI teams at companies like Anthropic, OpenAI, and Cohere.

### Why temperature=0.0 for Groq?

The LLM is answering factual questions about specific properties with specific prices, addresses, and amenities. Any temperature above 0.0 introduces stochastic variation — the same question might get a slightly different answer each time, including potential hallucinations of property details that do not exist. Temperature 0.0 makes responses deterministic and factual. The tradeoff is slightly less natural conversational tone — acceptable given the application.

### Why max_tokens=150?

TTS latency scales linearly with response length. A 300-token response takes roughly twice as long to generate audio for as a 150-token response. 150 tokens is sufficient for 2 clear sentences — enough to answer any property question. Combined with the system prompt instruction to keep answers short, this is the primary latency optimization in the system.

---

## ⚠️ Known Limitations

| Limitation | Current Behavior | Production Fix |
|---|---|---|
| Hardcoded property data | Synthetic JSON file with 10 properties | Vector database with RAG, real property management system integration |
| No conversation memory | Each question treated independently | Rolling session history passed to LLM on every request |
| TTS fallback depends on ElevenLabs | If ElevenLabs is fully down, fallback message also fails | Pre-recorded MP3 fallback file stored locally |
| Single tenant | One conversation at a time | Session manager with UUID per caller, concurrent async handlers |
| Endpointing cuts natural pauses | 1000ms silence triggers sentence completion | Utterance-end detection combined with LLM intent classification |
| No evaluation | No automated quality or regression testing | RAGAS eval framework with CI gate |
| Phone pipeline resilience incomplete | server.py has no timeout handling | Apply identical resilience patterns from local pipeline |
| ngrok URL changes on restart | Must update Twilio webhook manually every session | ngrok paid static domain, or deploy to cloud with fixed URL |
| No structured logging | Print statements only | structlog with JSON output, trace IDs, log aggregation |
| No health checks | No way to verify system health programmatically | /health endpoint returning component status JSON |

---

## 💡 What I Learned

**Threading and async do not mix without a queue.** The mic callback runs in a separate OS thread. Directly calling async functions raises RuntimeError. The asyncio Queue is the correct bridge — it is used in production audio systems, game engines, and real-time data pipelines for exactly this reason. Understanding why it is necessary (not just that it is necessary) is what separates copying a solution from understanding it.

**Blocking calls are invisible until they break everything.** ElevenLabs `play()` looked completely harmless. It blocked the entire event loop for the duration of audio playback — preventing Deepgram from receiving audio, triggering WebSocket timeouts, and halting all dashboard updates. The lesson: in async code, any synchronous call that takes wall-clock time is a hidden landmine. Always run them in executors.

**Measuring latency naively gives wrong numbers.** The first latency timer included audio playback time, producing numbers of 8-17 seconds. Playback time is not a bottleneck we control — it is fixed by audio duration. The real metric is generation time. Separating measurement from playback was non-obvious and required clearly defining what was actually being measured and why.

**TTS latency is directly proportional to response length.** The most impactful optimization was not changing models, APIs, or infrastructure. It was constraining the LLM to short responses. Shorter text means less audio to generate. This single change reduced average TTS latency by 40-60%. The lesson: understand where time is actually spent before optimizing infrastructure.

**Prompt engineering is system engineering.** Treating the system prompt as an afterthought produced hallucinations, off-topic responses, and inconsistent behavior. Versioning prompts in config files, iterating on them systematically with clear hypotheses, and being extremely explicit about constraints is the difference between a demo that works sometimes and a system that works reliably.

**The gap between a demo and a production system is enormous.** Silence handling, mic feedback loops, partial transcripts, connection drops, thread safety, and audio format mismatches are completely invisible in tutorials. They are constant in real systems. Every one of these was encountered, diagnosed, and solved in this project — and each one required understanding the underlying system, not just the API.

**Ctrl+Z does not stop a program — it suspends it.** Ports stay occupied. Always use Ctrl+C. Discovered the hard way after getting `OSError: [Errno 48] address already in use` repeatedly.

---

## 🤝 Contributing

Contributions are welcome. Priority areas where help would be most valuable:

- **RAG implementation** — Replace JSON with ChromaDB or Pinecone vector store
- **Conversation memory** — Add rolling session history per call
- **Evaluation framework** — Build golden dataset and RAGAS eval script
- **Concurrent sessions** — Session manager for multiple simultaneous callers
- **Docker setup** — Containerize the full application with docker-compose
- **Pre-recorded fallback** — Record and integrate a local fallback audio file

Please open an issue before submitting a PR to discuss the approach. Include: what problem you are solving, what approach you plan to take, and any tradeoffs you see.

---

## 📄 License

MIT License — see LICENSE file for details.

---

## 👤 Author

Built by Aakash Patel — Data Engineer transitioning into AI Engineering.

- LinkedIn: (https://www.linkedin.com/in/aakashpatel05/)
- Portfolio: https://aakashbuilds.dev/
- Demo Video: [ADD LINKEDIN POST LINK HERE]

---

*This project was built as part of a deliberate effort to understand production AI engineering — not just call APIs, but understand the real systems underneath them. Every bug encountered was treated as a learning opportunity, not an obstacle.*