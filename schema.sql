-- schema.sql
-- Generic gym-membership renewal reminder schema.
-- Mirrors a common production pattern: entity + followup + history tables.

CREATE TABLE IF NOT EXISTS member (
    member_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    phone_number  TEXT NOT NULL,      -- E.164 format, e.g. +91XXXXXXXXXX
    email         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS membership (
    membership_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id       INTEGER NOT NULL REFERENCES member(member_id),
    plan_name       TEXT NOT NULL,
    renewal_due_date TEXT NOT NULL,   -- ISO date, YYYY-MM-DD
    amount_due      NUMERIC NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'  -- active / lapsed / renewed
);

CREATE TABLE IF NOT EXISTS renewal_followup (
    followup_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id       INTEGER NOT NULL UNIQUE REFERENCES membership(membership_id),
    conversation_id     TEXT UNIQUE,
    twiml               TEXT,
    followup_date       TEXT NOT NULL DEFAULT (datetime('now')),
    renewal_decision    TEXT,
    callback_date       TEXT,
    cancellation_reason TEXT,
    modified_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS renewal_followup_history (
    history_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    followup_id              INTEGER NOT NULL REFERENCES renewal_followup(followup_id),
    changed_at               TEXT NOT NULL DEFAULT (datetime('now')),
    old_callback_date        TEXT,
    new_callback_date        TEXT,
    old_cancellation_reason  TEXT,
    new_cancellation_reason  TEXT
);

-- Seed data. All calls should go to YOUR OWN verified number when testing with Twilio trial.
INSERT INTO member (name, phone_number, email) VALUES
    ('Venkatesh', '+919460560152', 'demo@example.com');

INSERT INTO membership (member_id, plan_name, renewal_due_date, amount_due, status) VALUES
    (1, 'Monthly Strength Plan', date('now'), 1499.00, 'active');
