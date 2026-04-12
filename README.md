# Real Estate Voice Assistant

A real-time voice assistant for real estate built with production-grade 
engineering principles. Ask questions about properties, leases, or rentals 
by voice and get instant spoken answers back.

## Why I Built This

Most AI voice demos are just API wrappers. This project focuses on the 
engineering behind a real production voice system — streaming audio, 
latency budgeting, resilience, and observability.

## Architecture
Microphone → [Deepgram] → text → [Groq LLM] → response → [ElevenLabs] → Speaker

Each component is built and tested in isolation before being wired together.

## Tech Stack

- **Deepgram** — Speech to text (real-time streaming)
- **Groq** — LLM inference (fast response generation)
- **ElevenLabs** — Text to speech (natural voice output)
- **WebSockets** — Keeps audio streaming connection open
- **asyncio** — Handles multiple things happening at once

## How to Run

1. Clone the repo
2. Create virtual environment:
```bash
   python3 -m venv venv
   source venv/bin/activate
```
3. Install dependencies:
```bash
   venv/bin/pip install -r requirements.txt
```
4. Add your API keys to `.env`:
DEEPGRAM_API_KEY=your_key
GROQ_API_KEY=your_key
ELEVENLABS_API_KEY=your_key
5. Run:
```bash
   venv/bin/python src/pipeline.py
```

## Project Structure
voice-assistant/
├── src/
│   ├── asr.py        # Mic → Deepgram → text (the ears)
│   ├── llm.py        # Text → Groq → response (the brain)
│   ├── tts.py        # Text → ElevenLabs → audio (the mouth)
│   └── pipeline.py   # Wires everything together
├── config/
│   └── prompts.yaml  # System prompts (versioned separately)
├── tests/            # Each module tested in isolation
└── docs/
└── architecture.md

## Known Tradeoffs

| Tradeoff | Decision | Reason |
|---|---|---|
| Endpointing at 500ms | May cut long sentences | Balance between responsiveness and accuracy |
| Separate STT/LLM/TTS | More complex than all-in-one | Better control, easier to debug each piece |
| Groq over OpenAI | Slightly less capable | Much faster inference for real-time feel |

## Phase Progress

- [x] Phase 1 — Core Pipeline (in progress)
- [ ] Phase 2 — Latency Tracking
- [ ] Phase 3 — Resilience