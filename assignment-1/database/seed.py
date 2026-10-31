"""Idempotent seeding of FICTIONAL demonstration data.

* Safe to run on every start-up: rows are inserted with INSERT OR IGNORE keyed by student_id,
  so existing (possibly manually edited) records are never overwritten or duplicated.
* `python -m database.seed --reset --confirm` wipes everything. DEVELOPMENT ONLY.
"""
import argparse
import json

from config import settings
from database.db import connection, init_db
from database.models import DROP_ALL


def seed_students() -> int:
    """Insert sample students that are not yet present. Returns the number of NEW students."""
    init_db()
    data = json.loads(settings.students_json_path().read_text(encoding="utf-8"))
    inserted = 0
    with connection() as conn:
        for s in data["students"]:
            cur = conn.execute(
                "INSERT OR IGNORE INTO students (student_id,name,email,programme,semester,cgpa,"
                "attendance_pct,advisor,batch,is_demo_data) VALUES (?,?,?,?,?,?,?,?,?,1)",
                (s["student_id"], s["name"], s["email"], s["programme"], s["semester"], s["cgpa"],
                 s["attendance_pct"], s["advisor"], s["batch"]),
            )
            if cur.rowcount == 0:
                continue  # student already exists -> leave all related rows untouched
            inserted += 1
            f, sch = s["fee"], s["scholarship"]
            conn.execute(
                "INSERT OR IGNORE INTO fees VALUES (?,?,?,?,?,?,?)",
                (s["student_id"], f["total"], f["paid"], f["total"] - f["paid"], f["status"],
                 f["due_date"], f["last_payment_date"]),
            )
            conn.execute(
                "INSERT OR IGNORE INTO scholarships VALUES (?,?,?,?,?)",
                (s["student_id"], sch["name"], sch["status"], sch["amount"], sch["remarks"]),
            )
        conn.execute("INSERT OR REPLACE INTO seed_meta VALUES ('demo_data_seeded', 'true')")
    return inserted


def reset_database() -> int:
    """DEVELOPMENT ONLY: drop all tables and re-seed."""
    with connection() as conn:
        conn.executescript(DROP_ALL)
    return seed_students()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed (or reset) the demo database")
    parser.add_argument("--reset", action="store_true", help="DROP ALL DATA and re-seed (dev only)")
    parser.add_argument("--confirm", action="store_true", help="required together with --reset")
    args = parser.parse_args()
    if args.reset:
        if not args.confirm:
            raise SystemExit("Refusing to reset without --confirm (this deletes all data).")
        print(f"Database reset. Students inserted: {reset_database()}")
    else:
        print(f"Students newly inserted: {seed_students()} (0 means already seeded)")
