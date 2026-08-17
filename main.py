# main.py
# FastAPI wrapper: exposes an endpoint to trigger today's calls, a webhook
# for ElevenLabs to post the call transcript back to, and a simple status
# endpoint that doubles as a live demo view.

import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException, Response
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
