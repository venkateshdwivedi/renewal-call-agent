# main.py
# FastAPI wrapper: exposes an endpoint to trigger today's calls, a webhook
# for ElevenLabs to post the call transcript back to, and a simple status
# endpoint that doubles as a live demo view.

import logging
import os
import requests
from datetime import date
from fastapi import FastAPI, BackgroundTasks, HTTPException, Response, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict

from db import init_db, get_db_connection
from orchestrator import run as run_orchestrator
from update_agent import update_followup_and_history

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(
    title="Renewal Reminder Calling Agent",
    description="Demo: DB -> outbound AI voice call -> ElevenLabs data extraction -> DB update.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")
@app.on_event("startup")
def startup():
    init_db()


@app.post("/trigger-calls")
def trigger_calls(background_tasks: BackgroundTasks):
    """Kicks off today's renewal call run in the background."""
    background_tasks.add_task(run_orchestrator)
    return {"status": "started", "message": "Call run triggered in the background."}


@app.post("/webhook/call-outcome")
def call_outcome_webhook(payload: Dict):
    """
    Receives the post_call_transcription webhook from ElevenLabs
    after a call ends, extracting structured outcome natively.
    """
    try:
        outcome = update_followup_and_history(payload)
        return {"status": "success", "outcome": outcome}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.api_route("/exotel-voicebot", methods=["GET", "POST"])
async def exotel_voicebot(request: Request):
    """Exotel hits this URL when the call connects."""
    # Exotel might send this as a GET request (query params) or POST (form data)
    membership_id = request.query_params.get("CustomField")
    
    if not membership_id and request.method == "POST":
        form_data = await request.form()
        membership_id = form_data.get("CustomField")
        
    if not membership_id:
        logging.error("Exotel webhook missing CustomField")
        return Response(content="Missing CustomField", media_type="text/plain", status_code=400)
    
    # Fetch membership details from DB
    conn = get_db_connection()
    try:
        task = conn.execute(
            """
            SELECT p.name as member_name, p.phone_number, m.plan_name, m.amount_due, m.renewal_due_date, m.membership_id
            FROM membership m
            JOIN member p ON m.member_id = p.member_id
            WHERE m.membership_id = ?
            """, (membership_id,)
        ).fetchone()
    finally:
        conn.close()

    if not task:
        logging.error("Membership %s not found", membership_id)
        return Response(content="Membership not found", media_type="text/plain", status_code=404)

    # Call ElevenLabs Register Call
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
    EXOTEL_CALLER_ID = os.getenv("EXOTEL_CALLER_ID")
    ELEVENLABS_REGISTER_URL = "https://api.elevenlabs.io/v1/convai/twilio/register-call"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "agent_id": AGENT_ID,
        "to_number": task["phone_number"],
        "from_number": EXOTEL_CALLER_ID,
        "direction": "outbound",
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "member_name": str(task["member_name"]),
                "plan_name": str(task["plan_name"]),
                "amount_due": str(task["amount_due"]),
                "renewal_due_date": str(task["renewal_due_date"]),
                "todays_date": str(date.today()),
            }
        },
    }

    try:
        resp = requests.post(ELEVENLABS_REGISTER_URL, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        
        try:
            resp_data = resp.json()
            conversation_id = resp_data.get("conversation_id")
        except ValueError:
            # ElevenLabs returned raw XML, extract from headers instead
            conversation_id = resp.headers.get("x-conversation-id")
            
        if not conversation_id:
            conversation_id = resp.headers.get("x-conversation-id")
            
        logging.info("Generated new Conversation ID on the fly: %s", conversation_id)
    except Exception as e:
        logging.error("Failed to register ElevenLabs call: %s", e)
        if 'resp' in locals():
            logging.error("ElevenLabs response: %s", resp.text)
        return Response(content="Error registering call", media_type="text/plain", status_code=500)

    # Save mapping for the webhook
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
            (membership_id, conversation_id, "exotel-dynamic")
        )
        conn.commit()
    except Exception as e:
        logging.error("Failed to save Exotel conversation_id mapping: %s", e)
        conn.rollback()
    finally:
        conn.close()

    # Return plain text WebSocket URL to Exotel
    ws_url = f"wss://api.elevenlabs.io/v1/convai/conversation?conversation_id={conversation_id}"
    return Response(content=ws_url, media_type="text/plain")

@app.api_route("/twiml/{conversation_id}", methods=["GET", "POST"])
def get_twiml(conversation_id: str):
    """Twilio hits this URL when the call connects to get the TwiML instructions."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT twiml FROM renewal_followup WHERE conversation_id = ?", (conversation_id,)).fetchone()
        if row and row["twiml"]:
            return Response(content=row["twiml"], media_type="text/xml")
        return Response(content="<Response><Reject/></Response>", media_type="text/xml")
    finally:
        conn.close()


@app.get("/renewals")
def list_renewals():
    """Simple status view — good for a live demo screen recording."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.name, p.phone_number, m.plan_name, m.renewal_due_date, m.amount_due,
                   f.renewal_decision, f.callback_date, f.cancellation_reason
            FROM membership m
            JOIN member p ON m.member_id = p.member_id
            LEFT JOIN renewal_followup f ON m.membership_id = f.membership_id
            ORDER BY m.renewal_due_date
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
