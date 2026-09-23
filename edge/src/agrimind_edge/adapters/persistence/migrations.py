"""Versioned SQLite migrations for local edge persistence."""

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE edge_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL CHECK (
            event_type IN ('telemetry', 'command_acknowledgement')
        ),
        farm_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        payload TEXT NOT NULL CHECK (json_valid(payload)),
        created_at TEXT NOT NULL
    );

    CREATE TABLE outbox (
        event_id TEXT PRIMARY KEY REFERENCES edge_events(event_id) ON DELETE CASCADE,
        topic TEXT NOT NULL,
        payload TEXT NOT NULL CHECK (json_valid(payload)),
        qos INTEGER NOT NULL CHECK (qos IN (0, 1, 2)),
        retain INTEGER NOT NULL CHECK (retain IN (0, 1)),
        state TEXT NOT NULL CHECK (state IN ('pending', 'delivered')),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
        last_attempt_at TEXT,
        delivered_at TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE processed_commands (
        command_id TEXT PRIMARY KEY,
        command_fingerprint TEXT NOT NULL,
        acknowledgement_payload TEXT NOT NULL CHECK (json_valid(acknowledgement_payload)),
        processed_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );

    CREATE INDEX idx_edge_events_age
        ON edge_events(occurred_at, event_id);
    CREATE INDEX idx_edge_events_identity_age
        ON edge_events(farm_id, device_id, occurred_at, event_id);
    CREATE INDEX idx_outbox_pending_order
        ON outbox(state, created_at, event_id);
    CREATE INDEX idx_processed_commands_expiry
        ON processed_commands(expires_at, command_id);
    """,
)
