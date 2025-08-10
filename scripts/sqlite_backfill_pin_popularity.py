import argparse
import math
import os
import sqlite3
from datetime import datetime


def deg_from_meters(meters: float) -> float:
    # Rough conversion at mid-latitudes; good enough for small radii lookups
    return float(meters) / 111_320.0


def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    print("[schema] Enabling WAL (if available) and setting pragmatic defaults …")
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    cur.execute("PRAGMA synchronous=NORMAL;")

    print("[schema] Ensuring pin_interactions.place_id column exists …")
    cur.execute("PRAGMA table_info(pin_interactions);")
    cols = [row[1] for row in cur.fetchall()]
    if "place_id" not in cols:
        cur.execute("ALTER TABLE pin_interactions ADD COLUMN place_id TEXT;")

    print("[schema] Ensuring pin_popularity table and indexes exist …")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pin_popularity (
            place_id TEXT PRIMARY KEY,
            total_clicks INTEGER NOT NULL DEFAULT 0,
            last_clicked_at DATETIME,
            last_lat REAL,
            last_lng REAL
        );
        """
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pin_pop_place ON pin_popularity(place_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_pin_interactions_place_id ON pin_interactions(place_id);"
    )
    # Helpful spatial indexes for the backfill
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_pi_lat_lng ON pin_interactions(lat,lng);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_retailers_lat_lng ON retailers(latitude,longitude);"
    )
    conn.commit()


def backfill_place_ids(conn: sqlite3.Connection, threshold_deg: float) -> int:
    """Populate pin_interactions.place_id by nearest retailer within threshold.

    Returns number of pin_interactions rows updated.
    """
    cur = conn.cursor()
    print(f"[place_id] Building candidate matches within ±{threshold_deg:.6f}° …")

    # Use temp tables to avoid correlated update quirks across sqlite builds
    cur.execute("DROP TABLE IF EXISTS tmp_pi_candidates;")
    cur.execute(
        f"""
        CREATE TEMP TABLE tmp_pi_candidates AS
        SELECT
          pi.id AS pi_id,
          r.place_id AS place_id,
          (ABS(r.latitude - pi.lat) + ABS(r.longitude - pi.lng)) AS d
        FROM pin_interactions pi
        JOIN retailers r
          ON r.place_id IS NOT NULL AND r.place_id != ''
         AND r.latitude IS NOT NULL AND r.longitude IS NOT NULL
         AND ABS(r.latitude - pi.lat) < {threshold_deg}
         AND ABS(r.longitude - pi.lng) < {threshold_deg}
        WHERE (pi.place_id IS NULL OR pi.place_id = '')
          AND pi.lat IS NOT NULL AND pi.lng IS NOT NULL;
        """
    )

    cur.execute("DROP TABLE IF EXISTS tmp_pi_best;")
    cur.execute(
        """
        CREATE TEMP TABLE tmp_pi_best AS
        SELECT c.pi_id, c.place_id
        FROM tmp_pi_candidates c
        JOIN (
          SELECT pi_id, MIN(d) AS md
          FROM tmp_pi_candidates
          GROUP BY pi_id
        ) m ON m.pi_id = c.pi_id AND m.md = c.d;
        """
    )

    print("[place_id] Applying nearest matches to pin_interactions …")
    cur.execute(
        """
        UPDATE pin_interactions
        SET place_id = (
          SELECT b.place_id FROM tmp_pi_best b
          WHERE b.pi_id = pin_interactions.id LIMIT 1
        )
        WHERE (place_id IS NULL OR place_id = '')
          AND id IN (SELECT pi_id FROM tmp_pi_best);
        """
    )
    updated = conn.total_changes

    # Clean temporary tables
    cur.execute("DROP TABLE IF EXISTS tmp_pi_best;")
    cur.execute("DROP TABLE IF EXISTS tmp_pi_candidates;")
    conn.commit()

    print(f"[place_id] Updated rows: {updated}")
    return updated


def backfill_popularity(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    print("[popularity] Aggregating clicks by place_id into pin_popularity …")
    cur.execute(
        """
        INSERT OR REPLACE INTO pin_popularity(place_id,total_clicks,last_clicked_at,last_lat,last_lng)
        SELECT i.place_id,
               COUNT(*),
               MAX(timestamp),
               (
                 SELECT lat FROM pin_interactions x
                 WHERE x.place_id = i.place_id
                 ORDER BY timestamp DESC, id DESC LIMIT 1
               ),
               (
                 SELECT lng FROM pin_interactions x
                 WHERE x.place_id = i.place_id
                 ORDER BY timestamp DESC, id DESC LIMIT 1
               )
        FROM pin_interactions i
        WHERE i.place_id IS NOT NULL AND i.place_id != ''
        GROUP BY i.place_id;
        """
    )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM pin_popularity;")
    count = cur.fetchone()[0]
    print(f"[popularity] pin_popularity rows: {count}")
    return int(count)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill pin_interactions.place_id and aggregate pin_popularity"
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite DB (defaults to project/instance/tamermap_data.db)",
    )
    parser.add_argument(
        "--threshold-m",
        type=float,
        default=90.0,
        help="Nearest-neighbor threshold in meters (default: 90m)",
    )
    parser.add_argument(
        "--prep-only",
        action="store_true",
        help="Only ensure schema (columns/tables/indexes); do not backfill",
    )
    parser.add_argument(
        "--backfill-only",
        action="store_true",
        help="Only run backfill steps; do not modify schema",
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    db_path = args.db or os.path.join(project_root, "instance", "tamermap_data.db")
    threshold_deg = deg_from_meters(args.threshold_m)

    print(f"Using DB: {db_path}")
    print(f"Threshold: {args.threshold_m} m (~{threshold_deg:.6f}°)")

    conn = sqlite3.connect(db_path)
    try:
        if not args.backfill_only:
            ensure_schema(conn)
        if not args.prep_only:
            updated = backfill_place_ids(conn, threshold_deg)
            rows = backfill_popularity(conn)
            print(
                f"Done. Updated interactions: {updated} · pin_popularity rows: {rows}"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()


