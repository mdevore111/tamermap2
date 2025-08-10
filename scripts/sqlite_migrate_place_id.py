"""
SQLite migration helper: add place_id-centric tracking tables/columns and indexes.

Safe to run multiple times. Designed for local/prod reuse.

What it does:
 1) Ensure PinInteraction has a nullable place_id column (ignored if exists)
 2) Create PinPopularity table if not exists
 3) Create recommended indexes:
    - UNIQUE(retaillers.place_id)
    - UNIQUE(pin_popularity.place_id)

Usage:
  python -m tamermap.scripts.sqlite_migrate_place_id
"""

import os
import sqlite3

from contextlib import closing


def run_migration(db_path: str):
    print(f"Using SQLite DB: {db_path}")
    if not os.path.exists(db_path):
        raise SystemExit(f"Database not found: {db_path}")

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        cur = conn.cursor()

        # 1) Add place_id column to pin_interactions if missing
        cur.execute("PRAGMA table_info(pin_interactions);")
        cols = {row[1] for row in cur.fetchall()}
        if "place_id" not in cols:
            print("Adding column pin_interactions.place_id ...")
            cur.execute("ALTER TABLE pin_interactions ADD COLUMN place_id TEXT;")
        else:
            print("Column pin_interactions.place_id already exists")

        # 2) Create pin_popularity table if not exists
        print("Ensuring pin_popularity table exists ...")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pin_popularity (
                place_id TEXT PRIMARY KEY,
                total_clicks INTEGER NOT NULL DEFAULT 0,
                last_clicked_at TEXT,
                last_lat REAL,
                last_lng REAL
            );
            """
        )

        # 3) Indexes
        print("Creating/ensuring indexes ...")
        # Attempt UNIQUE index on retailers(place_id); fallback to non-unique if duplicates exist
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_retailers_place_id ON retailers(place_id);"
            )
        except sqlite3.IntegrityError:
            print("UNIQUE idx_retailers_place_id failed due to existing duplicates. Creating non-unique index instead.")
            # Create non-unique index for performance
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_retailers_place_id_nonuniq ON retailers(place_id);"
            )
            # Report a few duplicates to console for follow-up
            try:
                cur.execute(
                    """
                    SELECT place_id, COUNT(*) as c
                    FROM retailers
                    WHERE place_id IS NOT NULL AND place_id NOT IN ('not_found','api_error')
                    GROUP BY place_id HAVING c > 1
                    ORDER BY c DESC LIMIT 10
                    """
                )
                dups = cur.fetchall()
                if dups:
                    print("Sample duplicate place_id rows (place_id, count):")
                    for row in dups:
                        print("  ", row)
                else:
                    print("No duplicates found among valid place_id values.")
            except Exception as e:
                print("Could not query duplicates:", e)
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pin_pop_place ON pin_popularity(place_id);"
        )

        conn.commit()
        print("Migration complete.")


if __name__ == "__main__":
    # Derive DB path from app config layout
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db_path = os.path.join(base_dir, "instance", "tamermap_data.db")
    run_migration(db_path)


