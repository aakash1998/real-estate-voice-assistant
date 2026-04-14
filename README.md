# 🎙️ Real Estate Voice Assistant

> A production-grade, real-time AI voice agent that answers property questions over a live phone call — built with streaming audio, RAG pipeline, hybrid conversation memory, per-component latency instrumentation, resilience engineering, and a live operations dashboard.

![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat-square&logo=python)
![Status](https://img.shields.io/badge/Status-Active-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)
![Eval Score](https://img.shields.io/badge/Eval%20Score-83%25-brightgreen?style=flat-square)

---

## 📺 Demo

> **Demo Video + LinkedIn Post:** [https://www.linkedin.com/feed/update/urn:li:activity:7449486634061836288/](https://www.linkedin.com/feed/update/urn:li:activity:7449486634061836288/)
>
> **What you will see in the demo:**
> - A real phone call being answered by the AI agent
> - Live dashboard updating in real time with transcripts and latency metrics
> - Natural conversational flow — the agent asks qualifying questions before suggesting properties
> - Per-component latency breakdown: ASR, LLM, TTS, and total response time

---

## 🧠 What This Is

Most AI voice demos are a single API call wrapped in a script. This project focuses on the real engineering challenges behind a production voice system:

- How do you stream audio continuously without blocking the event loop?
- How do you measure and budget latency across three independent components?
- What happens when Deepgram drops mid-call? When Groq times out? When ElevenLabs fails?
- How do you prevent a voice assistant from listening to and responding to its own voice?
- How do you build a RAG pipeline that retrieves relevant properties semantically?
- How do you maintain conversation context across a full leasing conversation?
- How do you measure system quality with real evaluation metrics?

These are the problems production AI teams deal with every day. This project addresses all of them.

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
    ▼ (final transcript)
[ChromaDB Vector Search + VoyageAI Reranker]
    │
    ▼ (top 3 relevant properties)
[Hybrid Memory - summary + window]
    │
    ▼
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
Caller Phone → [Twilio] → [ngrok tunnel] → [FastAPI Server]
                                                  │
                                                  ▼
                                    [Deepgram ASR - mulaw 8000Hz]
                                                  │
                                                  ▼
                                    [ChromaDB + VoyageAI Reranker]
                                                  │
                                                  ▼
                                         [Groq LLM]
                                                  │
                                                  ▼
                                    [ElevenLabs TTS - ulaw_8000]
                                                  │
                                                  ▼
                                    [Twilio] → Caller's Phone
```

### RAG Pipeline
```
Query: "pet friendly under $1,500"
    │
    ▼ (VoyageAI voyage-4 embedding)
[ChromaDB Vector Search - top 10 candidates]
    │
    ▼ (VoyageAI rerank-2)
[Reranker - scores and reorders top 10]
    │
    ▼ (top 3 most relevant)
[Groq LLM - answers from context only]
```

### Dashboard Architecture
```
[Pipeline] → WebSocket (port 8765) → [Browser Dashboard]

Events:                    Panels:
· transcript               · Live Transcript
· llm_response             · Latency Monitor
· latency_report           · Component Status
· speaking                 · Session Analytics
· ready                    · Voice Waveform
```

---

## 🛠️ Tech Stack

### Core Components

| Component | Tool | Model / Config | Why |
|---|---|---|---|
| Speech to Text | Deepgram | nova-2, linear16, 16kHz | Real-time streaming WebSocket. Whisper too slow. |
| LLM Inference | Groq | llama-3.1-8b-instant, temp=0.0, max_tokens=150 | 3-5x faster than OpenAI. Critical for sub-2s latency. |
| Text to Speech | ElevenLabs | eleven_turbo_v2, George voice | Most natural voice at lowest latency. |
| Embeddings | VoyageAI | voyage-4 | High quality embeddings, 200M free tokens. |
| Reranking | VoyageAI | rerank-2 | Cross-encoder reranker dramatically improves retrieval precision. |
| Vector Database | ChromaDB | Persistent, cosine similarity | Local vector store, no infrastructure needed. |
| Phone Integration | Twilio | mulaw, 8000Hz | Real phone number, production-grade call handling. |
| Public Tunnel | ngrok | v3 | Exposes local server to Twilio. |
| Web Server | FastAPI + uvicorn | — | Async-first, native WebSocket support. |
| Audio Capture | sounddevice | 16kHz, mono, int16 | Low-level mic access with callback pattern. |
| Concurrency | asyncio | — | Single event loop handles all components simultaneously. |
| Dashboard | Vanilla HTML/CSS/JS | — | No framework, WebSocket native, instant load. |
| Dashboard Transport | websockets | port 8765 | Lightweight async WebSocket server. |

### Audio Formats

| Pipeline | Format | Sample Rate | Why |
|---|---|---|---|
| Local mic input | LINEAR16 | 16000 Hz | Standard for speech recognition |
| Local speaker output | MP3 | 44100 Hz | High quality local playback |
| Phone input (Twilio) | mulaw | 8000 Hz | Twilio's native phone format |
| Phone output (Twilio) | ulaw_8000 | 8000 Hz | ElevenLabs format matching Twilio |

---

## 📁 Project Structure

```
real-estate-voice-assistant/
│
├── src/
│   ├── __init__.py
│   ├── asr.py                  # Ears — mic streaming → Deepgram → transcript
│   ├── llm.py                  # Brain — RAG search → Groq → response
│   ├── tts.py                  # Mouth — ElevenLabs → audio
│   ├── memory.py               # Hybrid memory — window + summary
│   ├── pipeline.py             # Local orchestrator
│   ├── server.py               # Phone orchestrator (Twilio)
│   ├── broadcaster.py          # Dashboard WebSocket server
│   ├── embed_properties.py     # One-time embedding script
│   └── evaluator.py            # Evaluation framework
│
├── static/
│   └── dashboard.html          # Live operations dashboard
│
├── config/
│   └── prompts.yaml            # System prompts (versioned)
│
├── data/
│   ├── properties.json         # 36 synthetic Calgary properties
│   ├── eval_questions.json     # 30 hand-crafted eval questions
│   └── eval_results.json       # Latest eval run results
│
├── tests/
│   ├── test_asr.py             # Isolated ASR test
│   ├── test_llm.py             # Isolated LLM + RAG test
│   ├── test_tts.py             # Isolated TTS test
│   ├── test_memory.py          # Conversation memory test
│   └── run_eval.py             # Full evaluation runner
│
├── docs/
│   └── architecture.md
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup and Installation

### Prerequisites

- Python 3.13+
- ffmpeg: `brew install ffmpeg` (required by ElevenLabs for audio playback)
- ngrok: `brew install ngrok` (only for phone pipeline)

### Step 1 — Clone and create virtual environment

```bash
git clone https://github.com/aakash1998/real-estate-voice-assistant
cd real-estate-voice-assistant

python3 -m venv venv
source venv/bin/activate
```

### Step 2 — Install dependencies

```bash
venv/bin/pip install -r requirements.txt
```

### Step 3 — Environment variables

```bash
touch .env
```

```
DEEPGRAM_API_KEY=your_key
GROQ_API_KEY=your_key
ELEVENLABS_API_KEY=your_key
VOYAGE_API_KEY=your_key
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=your_number
```

Where to get keys:
- Deepgram: console.deepgram.com — $200 free credits
- Groq: console.groq.com — free tier
- ElevenLabs: elevenlabs.io — 10,000 chars/month free
- VoyageAI: voyageai.com — 200M free tokens
- Twilio: twilio.com — $15 trial credits

### Step 4 — Embed properties (one time setup)

```bash
venv/bin/python -m src.embed_properties
```

This reads `data/properties.json`, generates embeddings using VoyageAI, and stores them in ChromaDB. Only needs to run again when property data changes.

### Step 5 — Run local pipeline

```bash
venv/bin/python -m src.pipeline
```

### Step 6 — Open dashboard

```bash
open static/dashboard.html
```

Dashboard auto-connects to pipeline on `ws://localhost:8765`.

### Step 7 — Phone pipeline (optional)

Terminal 1:
```bash
ngrok http 8000
```

Terminal 2:
```bash
venv/bin/python -m uvicorn src.server:app --port 8000 --reload
```

Set Twilio webhook to: `https://your-ngrok-url.ngrok-free.dev/incoming-call`

### Important: Anaconda conflict

If you have Anaconda installed, always use the full venv path:
```bash
venv/bin/python -m src.pipeline   # correct
python -m src.pipeline            # wrong — uses Anaconda
```

### Port conflict fix

Always use Ctrl+C to stop — never Ctrl+Z. If you see port already in use:
```bash
lsof -ti:8765 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

---

## 🧪 Running Tests

```bash
# Test each module in isolation
venv/bin/python -m tests.test_asr
venv/bin/python -m tests.test_llm
venv/bin/python -m tests.test_tts

# Test conversation memory
venv/bin/python -m tests.test_memory

# Run full evaluation
venv/bin/python -m tests.run_eval
```

---

## 🔍 RAG Pipeline — How It Works

### Why RAG Over Injecting All Properties

Before RAG, every question sent all 36 properties to Groq:
```
Question → inject all 36 properties (thousands of tokens) → Groq
```

With RAG:
```
Question → find top 3 relevant properties → Groq
```

Result: 10x fewer tokens per request, faster responses, more accurate answers, scales to any number of properties.

### Two-Step Retrieval

**Step 1 — Vector search (broad net)**
ChromaDB converts the question to a vector and finds the 10 most semantically similar property documents. Fast and cheap.

**Step 2 — Reranking (precision)**
VoyageAI rerank-2 re-scores all 10 candidates against the original query using a cross-encoder model. Returns top 3. Significantly more accurate than vector search alone.

### Incremental Indexing

When you update `properties.json` and re-run `embed_properties.py`:
- New properties get embedded and added
- Changed properties get re-embedded (detected via content hash)
- Unchanged properties get skipped

```bash
[ADD]    Riverside Lofts — new property, embedding
[SKIP]   Belmont House — no changes detected
[UPDATE] Forest Hills — content changed, re-embedding
```

---

## 🧠 Conversation Memory — How It Works

### Hybrid Memory (Window + Summary)

Each conversation uses a two-layer memory system:

**Layer 1 — Window (last 4 messages in full)**
The most recent exchanges are kept verbatim. This preserves exact detail for the current discussion.

**Layer 2 — Summary (older context compressed)**
When messages exceed the threshold, older exchanges get summarized by Groq into a concise paragraph capturing key facts: budget, pet requirements, preferred area, properties discussed.

```
Turn 1-8: accumulate in window
Turn 9 arrives → Turns 1-4 get summarized
               → Turns 5-8 stay in full
               → Turn 9 added to window

Sent to Groq:
[Summary: "User wants pet friendly 1 bed under $1,500 near Kensington"]
[Turns 5-8 in full]
[Turn 9 question]
```

### Why Not Just Window Memory?

Pure window memory drops old context entirely. If the user stated their budget in turn 1 and you're on turn 15, the budget is gone.

The summary preserves it in compressed form — keeping the user profile alive throughout the entire conversation.

---

## 📊 Latency Metrics

### What Each Metric Means

| Metric | What It Measures | Typical Range |
|---|---|---|
| ASR (Deepgram) | How long you were speaking | 1000-4000ms |
| LLM (Groq) | Time from transcript to response | 400-800ms |
| TTS (ElevenLabs) | Time to generate audio bytes | 500-900ms |
| TOTAL | LLM + TTS combined | 900-1700ms |

### Performance Benchmarks

```
TOTAL < 1000ms ── Excellent
TOTAL < 1500ms ── Good — natural conversation speed
TOTAL < 2500ms ── Acceptable
TOTAL > 2500ms ── Poor
```

### Key Insight

TTS latency scales linearly with response length. Constraining the LLM to 2 sentences reduced average TTS from ~1800ms to ~900ms — a 50% improvement with no infrastructure changes.

---

## 🛡️ Resilience

### Groq (LLM)

| Scenario | Response |
|---|---|
| Response > 10 seconds | Timeout triggered |
| Timeout on attempt 1 | Automatic retry |
| Both attempts fail | Graceful fallback message spoken |

### ElevenLabs (TTS)

| Scenario | Response |
|---|---|
| Generation > 10 seconds | Timeout triggered |
| Both attempts fail | Fallback message attempted |

### Deepgram (ASR)

| Scenario | Response |
|---|---|
| Connection rejected | Failure detected via event listener |
| Connection dropped | Auto reconnect triggered |
| Max reconnects (3) reached | Graceful shutdown |

---

## 📈 Evaluation Framework

### Overview

30 hand-crafted questions across 11 categories measured across three layers:

**Layer 1 — Retrieval Metrics (Precision@K + MRR)**
Industry standard information retrieval metrics. Measures whether ChromaDB + reranker returns the right property and how high it ranks.

**Layer 2 — LLM-as-Judge**
A second LLM scores each answer on faithfulness (no hallucinations), relevance (answers the question), and completeness (includes key details).

**Layer 3 — Regression Gate**
Hard threshold at 80%. Flags failing questions automatically when score drops.

### Latest Results

```
EVALUATION REPORT — April 14, 2026
════════════════════════════════════════════
Total questions:       30

RETRIEVAL METRICS
  Precision@1:         86.7%
  Precision@3:         90.0%
  MRR:                 0.890

QUALITY METRICS (LLM-as-Judge)
  Faithfulness:        80.8%
  Relevance:           96.7%
  Completeness:        55.0%

OVERALL SCORE:         83.0% ✅ PASSED

BY CATEGORY:
  specific_property    100.0%
  pet                   93.8%
  neighborhood          93.4%
  utilities             83.3%
  budget                83.4%
  luxury                83.4%
  amenity               88.3%
  parking               87.5%
  unit_type             69.1%
  fallback              66.7%
  availability          41.7%
════════════════════════════════════════════
```

### Known Weaknesses and Root Causes

**Availability (41.7%)** — "available now" appears once per document. Not enough semantic signal for the embedding to strongly connect availability queries to the right properties. Fix: expand availability description in property text before re-embedding.

**Unit type (69.1%)** — "bachelor" and "3 bedroom" are buried in a list. Fix: make unit types more prominent in document structure.

**Completeness (55%)** — The judge penalizes short answers. But this is a voice assistant — short answers are intentional. Nobody wants a full property spec read to them over the phone. This is a known mismatch between judge behavior and voice application requirements.

### Running Evaluation

```bash
venv/bin/python -m tests.run_eval
```

---

## ⭐ Honest Project Rating

### Current Rating: 8.5 / 10

### What Earns the 8.5

- Real threading patterns — queue between mic thread and async code
- Per-component latency instrumentation with live dashboard
- Three-layer resilience on every component
- RAG pipeline with vector search + reranking
- Hybrid conversation memory with automatic summarization
- Production-grade evaluation framework with Precision@K, MRR, and LLM-as-Judge
- Regression gate preventing quality degradation
- Mic feedback loop prevention
- Isolated module testing before wiring

### What Prevents a Higher Score

- No concurrent sessions — one conversation at a time
- Static property data — JSON file, not a real database
- TTS fallback depends on ElevenLabs being available
- No streaming TTS — full audio generated before playback starts
- Phone pipeline resilience incomplete

---

## 🗺️ Roadmap to 10 / 10

**Concurrent sessions (+0.5)**
Session manager with UUID per caller. Isolated state per session.

**Streaming TTS (+0.5)**
Stream audio chunks as they arrive instead of waiting for full generation. Reduces perceived latency by 40-60%.

**Production hardening (+0.5)**
Structured JSON logging, Prometheus metrics, health check endpoint, Docker containerization, pre-recorded fallback audio.

**Real data backend (+0.5)**
PostgreSQL or Supabase backend. Real-time availability sync. Admin panel.

---

## 🧩 Key Engineering Decisions

**Why separate STT + LLM + TTS instead of an all-in-one tool?**
Per-component latency measurement, independent resilience, ability to swap any component, clearer debugging.

**Why Groq instead of OpenAI?**
400-700ms vs 1200ms+ for similar quality. In real-time voice every 100ms is perceptible.

**Why reranking on top of vector search?**
Vector search finds candidates by approximate similarity. The cross-encoder reranker scores each candidate against the query as a pair — significantly more precise. Availability queries went from returning wrong properties to correct ones after adding reranking.

**Why hybrid memory over pure window memory?**
Window memory drops old context entirely. Hybrid summarizes old context so user preferences stated early in the call persist throughout the entire conversation.

**Why LLM-as-Judge over keyword matching?**
Keyword matching checks if a word appears. LLM-as-Judge understands meaning, detects hallucinations, and gives human-readable reasoning for each score.

**Why temperature=0.0 for Groq?**
The LLM answers factual questions about specific properties. Any temperature above 0.0 introduces stochastic variation — the same question might get different answers including hallucinated property details.

---

## ⚠️ Known Limitations

| Limitation | Production Fix |
|---|---|
| Static property data (JSON) | Vector DB synced from PostgreSQL via CDC pipeline |
| No concurrent sessions | Session manager with UUID per caller |
| TTS fallback depends on ElevenLabs | Pre-recorded fallback audio stored locally |
| Completeness judge unfair to voice | Voice-aware judge prompt or separate eval config |
| Availability queries weak (41.7%) | Expand availability text in property documents |
| Unit type queries weak (69.1%) | Make unit types more prominent in document structure |
| No streaming TTS | Stream audio chunks, don't wait for full generation |

---

## 💡 What I Learned

**Threading and async don't mix without a queue.** The mic callback runs in a separate OS thread. Directly calling async functions raises RuntimeError. The queue bridges the two worlds cleanly.

**Blocking calls are invisible until they break everything.** ElevenLabs play() froze the entire event loop during playback — causing Deepgram timeouts. Running it in an executor fixed this.

**Measuring latency naively gives wrong numbers.** Including audio playback time inflated numbers to 8-17 seconds. Only generation time counts toward the latency budget.

**TTS latency scales with response length.** Constraining to 2 sentences cut TTS latency by 50%. The biggest optimization wasn't infrastructure — it was prompt engineering.

**Bad evaluation data gives you fake low scores.** First eval run: 74.6%. After fixing wrong expected answers in the golden dataset: 83.0%. No system changes. The eval was measuring the wrong thing.

**An eval score is a smoke alarm, not a guarantee.** It tells you when something breaks and which questions failed. The goal isn't a perfect score — it's knowing exactly where the system is weak and why.

**Ctrl+Z does not stop a program.** It suspends it. Ports stay occupied. Always use Ctrl+C.

---

## 🤝 Contributing

Priority areas:
- Streaming TTS implementation
- Concurrent session manager
- Expanded eval dataset (50+ questions)
- Docker containerization
- Availability and unit type retrieval improvements

Open an issue before submitting a PR.

---

## 📄 License

MIT License — see LICENSE file for details.

---

## 👤 Author

Built by Aakash Patel — Data Engineer transitioning into AI Engineering.

- LinkedIn: [linkedin.com/in/aakashpatel05](https://www.linkedin.com/in/aakashpatel05/)
- GitHub: [github.com/aakash1998](https://github.com/aakash1998)
- Website: [[ADD WEBSITE LINK HERE](https://aakashbuilds.dev/)]
- Demo: [linkedin.com/feed/update/urn:li:activity:7449486634061836288](https://www.linkedin.com/feed/update/urn:li:activity:7449486634061836288/)

---