# AI Renewal Call Agent

A fully functional, end-to-end AI voice-calling pipeline: a backend queries a database for tasks due today, initiates an outbound AI voice call for each via Exotel, and writes the call outcome back into the database — closing the loop completely autonomously.

## Architecture

```text
Database (renewals due today)
        |
        v
FastAPI trigger endpoint  ->  queries DB, kicks off calls
        |
        v
ElevenLabs triggers an outbound call through Exotel
        |
        v
Call happens; Exotel streams audio to ElevenLabs WebSocket
        |
        v
AI collects structured data (renewal decision, rationale, member name) during the call
        |
        v
ElevenLabs posts the final extracted outcome to a webhook
        |
        v
Database is updated with the decision ("renewed", "cancelled", etc.)
```

## Why ElevenLabs & Exotel?

- **Voice Latency**: Prototyping with lower-level real-time models often results in noticeable conversational latency, ruining the illusion of a live phone call. ElevenLabs' Conversational AI handles turn-taking, interruption, and response generation with sub-second latency, making it feel like a real human interaction.
- **Data Collection**: ElevenLabs natively supports structured data extraction (JSON schema) during the call, eliminating the need to pass a raw transcript through a secondary LLM (like OpenAI) after the fact.
- **Exotel Integration**: Twilio's trial accounts block WebSocket streaming, which breaks AI voice architectures. Pivoting to Exotel's Voicebot infrastructure combined with ElevenLabs' native telephony integration provides a robust, production-ready pipeline.

## Stack

- **FastAPI** — trigger endpoint + webhook receiver
- **SQLite** — zero-setup persistence (swap for Postgres/MySQL trivially — the queries are already parameterized)
- **Exotel** — SIP trunking and outbound dialing
- **ElevenLabs Conversational AI** — live voice agent + built-in data collection

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your own keys — never commit this file
python main.py
```

### Required Configuration
You must configure the following in your `.env`:
- `ELEVENLABS_API_KEY`: Your API key
- `ELEVENLABS_AGENT_ID`: The ID of your configured agent
- `ELEVENLABS_PHONE_NUMBER_ID`: The ID of your Exotel phone number linked inside the ElevenLabs dashboard

Then:
- `POST /trigger-calls` — kicks off today's due renewals as outbound calls
- `POST /webhook/call-outcome` — receives the structured outcome from ElevenLabs and updates the DB
- `GET /renewals` — live status view of every renewal and its latest call outcome

## Notes

- All SQL is parameterized — no string-interpolated queries.
- No secrets are hardcoded anywhere; everything comes from environment variables via `.env` (which is gitignored).
