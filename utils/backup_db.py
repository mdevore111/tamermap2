#!/usr/bin/env python3
"""
backup_db.py

Create a timestamped copy of tamermap_data.db **in the same directory** as
the original (project/instance/).

Usage
-----
    python backup_db.py            # uses default locations
    python backup_db.py /path/to/custom.db   # backup a different file
"""
from __future__ import annotations

import datetime as _dt
import os as _os
import shutil as _shutil
import sys as _sys


def backup_database(db_path: str | None = None) -> str | None:
    """
    Copy *db_path* → tamermap_data_backup_<timestamp>.db in the **same**
    folder.  If *db_path* is omitted, defaults to
    ``../instance/tamermap_data.db`` relative to this script.

    Returns the full path to the backup file, or ``None`` if the source
    database does not exist.
    """
    # Resolve default path if none provided
    if db_path is None:
        base = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
        db_path = _os.path.join(base, "instance", "tamermap_data.db")

    if not _os.path.exists(db_path):
        print(f"Database file '{_os.path.abspath(db_path)}' does not exist!", file=_sys.stderr)
        return None

    # Backup goes into the **same directory** as the original
    dst_dir = _os.path.dirname(db_path)
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"tamermap_data_backup_{timestamp}.db"
    backup_path = _os.path.join(dst_dir, backup_name)

    _shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


if __name__ == "__main__":
    # Allow optional custom path via CLI
    backup_database(_sys.argv[1] if len(_sys.argv) > 1 else None)
