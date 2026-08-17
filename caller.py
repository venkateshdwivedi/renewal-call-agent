# caller.py
# Places an outbound call via Twilio, using ElevenLabs to generate the TwiML.

import os
import logging
import requests
from datetime import date
from dotenv import load_dotenv
from twilio.rest import Client

from db import get_db_connection

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

ELEVENLABS_REGISTER_URL = "https://api.elevenlabs.io/v1/convai/twilio/register-call"


def initiate_call(task: dict) -> str | None:
    """
    Triggers an outbound call for a single renewal task using Register Call flow.
    """
    if not all([ELEVENLABS_API_KEY, AGENT_ID, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER]):
        logging.error("Missing ElevenLabs or Twilio config — check your .env file.")
        return None

    # --- Step A: Register the call with ElevenLabs to get TwiML and Conversation ID ---
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "agent_id": AGENT_ID,
        "to_number": task["phone_number"],
        "from_number": TWILIO_FROM_NUMBER,
        "direction": "outbound",
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "member_name": str(task.get("member_name")),
                "plan_name": str(task.get("plan_name")),
                "amount_due": str(task.get("amount_due")),
                "renewal_due_date": str(task.get("renewal_due_date")),
                "todays_date": str(date.today()),
            }
        },
    }

    print("\n" + "="*50)
    print("CLAUDE DIAGNOSTIC - ELEVENLABS REQUEST PAYLOAD:")
    import json
    print(json.dumps(payload, indent=2))
    print("="*50 + "\n")

    try:
        response = requests.post(ELEVENLABS_REGISTER_URL, headers=headers, json=payload, timeout=30)
        
        # Log the raw text in case it fails so we can see what went wrong
        if not response.ok:
            logging.error("ElevenLabs HTTP %s: %s", response.status_code, response.text)
            response.raise_for_status()

        logging.info("ElevenLabs Raw Response Headers: %s", dict(response.headers))
        
        try:
            resp_data = response.json()
            conversation_id = resp_data.get("conversation_id")
            twiml_str = resp_data.get("twiml")
        except Exception:
            # If it's not JSON, it might just be the raw TwiML string!
            twiml_str = response.text
            # Let's check headers for the conversation ID (it is x-conversation-id, not xi-)
            conversation_id = response.headers.get("x-conversation-id")
            if not conversation_id:
                logging.error("Response was not JSON and x-conversation-id header is missing! Raw text: %s", twiml_str)
                return None
        
        print("\n" + "="*50)
        print("CLAUDE DIAGNOSTIC - RAW ELEVENLABS TwiML STRING:")
        print(repr(twiml_str))
        print("="*50 + "\n")
        
        logging.info("Registered call. Conversation ID=%s", conversation_id)
    except Exception as e:
        logging.error("Failed to register call with ElevenLabs: %s", e)
        return None

    if not conversation_id or not twiml_str:
        logging.error("ElevenLabs response missing conversation_id or twiml")
        return None

    # --- Save Mapping: conversation_id -> membership_id and TwiML ---
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO renewal_followup (membership_id, conversation_id, twiml)
            VALUES (?, ?, ?)
            ON CONFLICT(membership_id) DO UPDATE SET 
                conversation_id = excluded.conversation_id,
                twiml = excluded.twiml
            """,
            (task["membership_id"], conversation_id, twiml_str)
        )
        conn.commit()
    except Exception as e:
        logging.error("Failed to save conversation_id mapping: %s", e)
        conn.rollback()
        return None
    finally:
        conn.close()

    # --- Step B: Place the Call via Twilio ---
    BASE_URL = os.getenv("BASE_URL")
    if not BASE_URL:
        logging.error("Missing BASE_URL in .env (add your Ngrok URL, e.g. BASE_URL=https://c411200d03e4a2.lhr.life)")
        return None

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        call = client.calls.create(
            to=task["phone_number"],
            from_=TWILIO_FROM_NUMBER,
            url=f"{BASE_URL}/twiml/{conversation_id}"
        )
        logging.info("Twilio Call initiated. SID=%s", call.sid)
        return call.sid
    except Exception as e:
        logging.error("Failed to initiate Twilio call: %s", e)
        return None
