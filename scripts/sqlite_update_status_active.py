import sqlite3
import os


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print(f"Using DB: {db_path}")

    # Ensure retailers table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='retailers'")
    if not cur.fetchone():
        print("retailers table not found. Exiting.")
        conn.close()
        return

    # Update NULL or empty status to 'Active'
    print("Setting status='Active' for rows with NULL/empty status ...")
    cur.execute("UPDATE retailers SET status = 'Active' WHERE status IS NULL OR TRIM(status) = ''")
    print(f"Rows updated: {conn.total_changes}")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == '__main__':
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    db_path = os.path.join(project_root, 'instance', 'tamermap_data.db')
    run(db_path)


