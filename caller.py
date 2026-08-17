# caller.py
# Places an outbound call via ElevenLabs' native Exotel integration.

import os
import logging
import requests
from datetime import date
from dotenv import load_dotenv

from db import get_db_connection

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
PHONE_NUMBER_ID = os.getenv("ELEVENLABS_PHONE_NUMBER_ID")

ELEVENLABS_EXOTEL_URL = "https://api.elevenlabs.io/v1/convai/exotel/outbound-call"


def initiate_call(task: dict) -> str | None:
    """
    Triggers an outbound call via ElevenLabs' native Exotel integration.
    ElevenLabs handles dialing the customer via Exotel directly.
    """
    if not all([ELEVENLABS_API_KEY, AGENT_ID, PHONE_NUMBER_ID]):
        logging.error("Missing ElevenLabs config — check ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID in .env")
        return None

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "agent_id": AGENT_ID,
        "agent_phone_number_id": PHONE_NUMBER_ID,
        "to_number": task["phone_number"],
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

    try:
        response = requests.post(ELEVENLABS_EXOTEL_URL, headers=headers, json=payload, timeout=30)
        if not response.ok:
            logging.error("ElevenLabs Exotel API HTTP %s: %s", response.status_code, response.text)
            return None

        resp_data = response.json()
        conversation_id = resp_data.get("conversation_id")
        logging.info("ElevenLabs Exotel call initiated. Conversation ID=%s", conversation_id)

        # Save conversation_id -> membership_id mapping so the post-call webhook can update the DB
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO renewal_followup (membership_id, conversation_id, twiml)
                VALUES (?, ?, ?)
                ON CONFLICT(membership_id) DO UPDATE SET 
                    conversation_id = excluded.conversation_id
                """,
                (task["membership_id"], conversation_id, "elevenlabs-exotel")
            )
            conn.commit()
            logging.info("Saved conversation_id mapping to DB for membership_id=%s", task["membership_id"])
        except Exception as db_err:
            logging.error("Failed to save conversation_id to DB: %s", db_err)
            conn.rollback()
        finally:
            conn.close()

        return conversation_id
    except Exception as e:
        logging.error("Failed to initiate ElevenLabs Exotel call: %s", e)
        return None
