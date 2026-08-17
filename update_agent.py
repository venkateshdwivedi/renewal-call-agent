# update_agent.py
# Takes the parsed webhook payload from ElevenLabs (which natively includes data extraction)
# and updates the renewal_followup + renewal_followup_history tables.

import logging
from db import get_db_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def update_followup_and_history(payload: dict):
    """
    1. Parse the ElevenLabs webhook payload.
    2. Look up the membership_id using conversation_id.
    3. Update renewal_followup with the extracted data fields.
    4. Insert an audit row into renewal_followup_history.
    """
    data = payload.get("data", {})
    conversation_id = data.get("conversation_id")
    
    if not conversation_id:
        logging.error("Webhook payload missing conversation_id.")
        return None

    results = data.get("analysis", {}).get("data_collection_results", {})
    
    # Safely extract the new nested fields
    renewal_decision = results.get("renewal_decision", {}).get("value")
    callback_date = results.get("callback_date", {}).get("value")
    cancellation_reason = results.get("cancellation_reason", {}).get("value")

    logging.info("Extracted outcome for conversation_id=%s: %s", conversation_id, results)

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Step 1: Find the membership_id mapped to this conversation_id
        cur.execute(
            "SELECT membership_id, followup_id, callback_date, cancellation_reason FROM renewal_followup WHERE conversation_id = ?",
            (conversation_id,)
        )
        row = cur.fetchone()
        
        if not row:
            logging.error("No database record found for conversation_id=%s", conversation_id)
            return None

        membership_id = row["membership_id"]
        followup_id = row["followup_id"]
        old_callback_date = row["callback_date"]
        old_cancellation_reason = row["cancellation_reason"]

        # Step 2: Update the follow-up record
        cur.execute(
            """
            UPDATE renewal_followup 
            SET renewal_decision = ?,
                callback_date = ?,
                cancellation_reason = ?,
                modified_at = datetime('now')
            WHERE conversation_id = ?
            """,
            (
                renewal_decision,
                callback_date,
                cancellation_reason,
                conversation_id
            )
        )

        # Step 3: Insert into history table
        cur.execute(
            """
            INSERT INTO renewal_followup_history
                (followup_id, old_callback_date, new_callback_date, old_cancellation_reason, new_cancellation_reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                followup_id,
                old_callback_date,
                callback_date,
                old_cancellation_reason,
                cancellation_reason
            )
        )

        conn.commit()
        logging.info("Follow-up for membership_id=%s updated successfully.", membership_id)
        return {
            "membership_id": membership_id,
            "renewal_decision": renewal_decision,
            "callback_date": callback_date,
            "cancellation_reason": cancellation_reason
        }
    except Exception:
        conn.rollback()
        logging.exception("Error updating follow-up for conversation_id=%s", conversation_id)
        raise
    finally:
        conn.close()
