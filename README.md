# Renewal Reminder Calling Agent

A small demo of an AI voice-calling pipeline: a backend queries a database for
tasks due today, places an outbound AI voice call for each, and writes the
call outcome back into the database — closing the loop end to end.

## Architecture

```
Database (renewals due today)
        |
        v
FastAPI trigger endpoint  ->  queries DB, kicks off calls
        |
        v
Twilio call routed to an ElevenLabs conversational agent
        |
        v
Call happens; ElevenLabs posts the transcript to a webhook
        |
        v
LLM extracts a structured outcome (intent, promise date, notes)
        |
        v
Database updated with the outcome + an audit history row
```

## Why ElevenLabs for the voice layer

I originally prototyped this with a lower-level real-time model for the voice
turn-taking, but observed noticeably higher conversational latency —
noticeable enough to feel unnatural on a live call. Switching the voice layer
to ElevenLabs' conversational agent brought that latency down to something
that felt like a real phone conversation. That kind of trade-off — picking
the right tool once you've actually measured the failure mode, not just the
one that looks best on paper — is the same judgment call I'd bring to a
client project.

## Stack

- **FastAPI** — trigger endpoint + webhook receiver
- **SQLite** — zero-setup persistence (swap for Postgres/MySQL trivially — the
  queries are already parameterized and vendor-neutral)
- **Twilio + ElevenLabs Conversational AI** — outbound call + live voice agent
- **OpenAI (or swap for Gemini)** — structured extraction from the call transcript

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your own keys — never commit this file
python main.py
```

Then:
- `POST /trigger-calls` — kicks off today's due renewals as outbound calls
- `POST /webhook/call-outcome` — receives `{membership_id, transcript}` and updates the DB
- `GET /renewals` — live status view of every renewal and its latest call outcome

## Notes

- All calls in this demo go to a Twilio-trial-verified number only.
- All SQL is parameterized — no string-interpolated queries.
- No secrets are hardcoded anywhere; everything comes from environment
  variables via `.env` (which is gitignored).
