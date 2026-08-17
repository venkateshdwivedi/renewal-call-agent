# extractor.py
# Queries memberships whose renewal is due today and returns the fields
# the calling agent needs. All queries are parameterized (no string-built SQL).

import logging
from datetime import date
from db import get_db_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def extract_todays_renewals():
    """
    Returns a list of dicts, one per membership due for renewal today,
    joined with the member's contact details.
    """
    target_date = date.today().isoformat()

    sql = """
    SELECT
        m.membership_id,
        m.plan_name,
        m.renewal_due_date,
        m.amount_due,
        p.member_id,
        p.name AS member_name,
        p.phone_number
    FROM membership m
    JOIN member p ON m.member_id = p.member_id
    WHERE m.renewal_due_date = ?
      AND m.status = 'active'
    """

    conn = get_db_connection()
    try:
        cur = conn.execute(sql, (target_date,))
        rows = [dict(r) for r in cur.fetchall()]
        logging.info("Found %d renewal(s) due today", len(rows))
        return rows
    finally:
        conn.close()


if __name__ == "__main__":
    for task in extract_todays_renewals():
        print(task)
