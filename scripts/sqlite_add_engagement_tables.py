import os
import sqlite3
from datetime import datetime


DDL = {
    'legend_clicks': '''
        CREATE TABLE IF NOT EXISTS legend_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME,
            session_id VARCHAR(100) NOT NULL,
            user_id INTEGER,
            is_pro BOOLEAN DEFAULT 0,
            control_id VARCHAR(100) NOT NULL,
            path VARCHAR(500),
            zoom INTEGER,
            center_lat REAL,
            center_lng REAL
        );
    ''',
    'route_events': '''
        CREATE TABLE IF NOT EXISTS route_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME,
            session_id VARCHAR(100) NOT NULL,
            user_id INTEGER,
            is_pro BOOLEAN DEFAULT 0,
            event VARCHAR(20) NOT NULL,
            max_distance INTEGER,
            max_stops INTEGER,
            options_json TEXT
        );
    ''',
    'outbound_messages': '''
        CREATE TABLE IF NOT EXISTS outbound_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_message_id INTEGER,
            to_email VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            sent_by_user_id INTEGER NOT NULL,
            sent_at DATETIME
        );
    ''',
    'bulk_email_jobs': '''
        CREATE TABLE IF NOT EXISTS bulk_email_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            created_by_user_id INTEGER NOT NULL,
            created_at DATETIME,
            total_recipients INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0
        );
    ''',
    'bulk_email_recipients': '''
        CREATE TABLE IF NOT EXISTS bulk_email_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            email VARCHAR(255) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            error TEXT,
            sent_at DATETIME
        );
    '''
}

INDEXES = [
    ("idx_legend_clicks_created", "legend_clicks(created_at)"),
    ("idx_legend_clicks_session", "legend_clicks(session_id)"),
    ("idx_legend_clicks_control", "legend_clicks(control_id)"),
    ("idx_route_events_created", "route_events(created_at)"),
    ("idx_route_events_session", "route_events(session_id)"),
    ("idx_route_events_event", "route_events(event)"),
    ("idx_bulk_recip_job", "bulk_email_recipients(job_id)"),
]


def ensure_tables(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Performance pragmas
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    # Create tables
    for name, ddl in DDL.items():
        print(f"Ensuring table: {name}")
        cur.execute(ddl)

    # Indexes
    for idx_name, idx_def in INDEXES:
        print(f"Ensuring index: {idx_name}")
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")

    conn.commit()
    conn.close()
    print("Engagement tables ready.")


if __name__ == '__main__':
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    db_path = os.path.join(project_root, 'instance', 'tamermap_data.db')
    print(f"Using DB: {db_path}")
    ensure_tables(db_path)


