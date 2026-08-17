# orchestrator.py
# Ties extractor + caller together: pulls today's due renewals and places
# a call for each, with a short delay to avoid hammering the API.

import logging
import time

from extractor import extract_todays_renewals
from caller import initiate_call

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CALL_DELAY_SECONDS = 5


def run():
    logging.info("Starting renewal reminder run...")
    tasks = extract_todays_renewals()

    if not tasks:
        logging.info("No renewals due today. Nothing to do.")
        return

    for task in tasks:
        try:
            logging.info(
                "Calling %s (%s) for membership_id=%s",
                task["member_name"], task["phone_number"], task["membership_id"],
            )
            initiate_call(task)
            time.sleep(CALL_DELAY_SECONDS)
        except Exception:
            logging.exception("Failed to process membership_id=%s", task.get("membership_id"))
            continue

    logging.info("Run complete.")


if __name__ == "__main__":
    run()
