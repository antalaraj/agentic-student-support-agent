"""Database seeder for Assignment 2.
Idempotently initializes students, fees, scholarships, user accounts,
pre-seeded approval requests, and initial audit trail.
"""
import argparse
import json
import uuid
from datetime import datetime, timezone

from auth.security import hash_password
from config import settings
from database.db import connection, init_db
from database.models import DROP_ALL


def seed_database() -> dict[str, int]:
    """Idempotently seed student data, accounts, and demo credentials."""
    init_db()
    students_data = json.loads(settings.students_json_path().read_text(encoding="utf-8"))
    counts = {"students": 0, "users": 0, "approvals": 0}

    with connection() as conn:
        # 1. Seed students, fees, scholarships
        for s in students_data["students"]:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO students (
                    student_id, name, email, programme, semester, cgpa,
                    attendance_pct, advisor, batch, is_demo_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    s["student_id"],
                    s["name"],
                    s["email"],
                    s["programme"],
                    s["semester"],
                    s["cgpa"],
                    s["attendance_pct"],
                    s["advisor"],
                    s["batch"],
                ),
            )
            if cur.rowcount > 0:
                counts["students"] += 1
                f, sch = s["fee"], s["scholarship"]
                conn.execute(
                    "INSERT OR IGNORE INTO fees VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        s["student_id"],
                        f["total"],
                        f["paid"],
                        f["total"] - f["paid"],
                        f["status"],
                        f["due_date"],
                        f["last_payment_date"],
                    ),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO scholarships VALUES (?, ?, ?, ?, ?)",
                    (s["student_id"], sch["name"], sch["status"], sch["amount"], sch["remarks"]),
                )

        # 2. Seed student user accounts (Default Password: Student@123)
        student_pwd_hash = hash_password("Student@123")
        now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

        for s in students_data["students"]:
            # Username is first name lower (e.g., aarav, diya) or student_id lower
            first_name = s["name"].split()[0].lower()
            u_cur = conn.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id, username, password_hash, role, student_id,
                    full_name, email, created_at, is_active
                ) VALUES (?, ?, ?, 'student', ?, ?, ?, ?, 1)
                """,
                (
                    f"USR-{s['student_id']}",
                    first_name,
                    student_pwd_hash,
                    s["student_id"],
                    s["name"],
                    s["email"],
                    now_ts,
                ),
            )
            if u_cur.rowcount > 0:
                counts["users"] += 1

            # Also allow login via student_id as username (e.g., mim25001)
            conn.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id, username, password_hash, role, student_id,
                    full_name, email, created_at, is_active
                ) VALUES (?, ?, ?, 'student', ?, ?, ?, ?, 1)
                """,
                (
                    f"USR-{s['student_id']}-ALT",
                    s["student_id"].lower(),
                    student_pwd_hash,
                    s["student_id"],
                    s["name"],
                    s["email"],
                    now_ts,
                ),
            )

        # 3. Seed Administrator Account (Default Password: Admin@12345)
        admin_pwd_hash = hash_password("Admin@12345")
        admin_cur = conn.execute(
            """
            INSERT OR IGNORE INTO users (
                user_id, username, password_hash, role, student_id,
                full_name, email, created_at, is_active
            ) VALUES (?, 'admin', ?, 'admin', NULL, 'System Administrator', 'admin@meridian-demo.example', ?, 1)
            """,
            ("USR-ADMIN-01", admin_pwd_hash, now_ts),
        )
        if admin_cur.rowcount > 0:
            counts["users"] += 1

        # 4. Seed illustrative demo pending approval request (Diya Nair - MIM25002)
        demo_payload = {
            "requested_due_date": "2026-12-31",
            "reason": "Family financial medical emergency; awaiting educational loan release from bank.",
            "current_due_date": "2026-11-30",
            "outstanding_amount": 150000,
            "total_fee": 450000,
            "paid_amount": 300000,
        }
        req_cur = conn.execute(
            """
            INSERT OR IGNORE INTO approval_requests (
                request_id, student_id, action_type, payload_json, status,
                requested_at, reviewed_by, reviewed_at, decision_reason, executed_at, execution_result
            ) VALUES ('REQ-DEMO-001', 'MIM25002', 'fee_extension_request', ?, 'PENDING', ?, NULL, NULL, NULL, NULL, NULL)
            """,
            (json.dumps(demo_payload), now_ts),
        )
        if req_cur.rowcount > 0:
            counts["approvals"] += 1

        # 5. Seed initial audit log event
        conn.execute(
            """
            INSERT OR IGNORE INTO security_audit_logs (
                audit_id, timestamp, requester_id, requester_role, action, resource,
                requested_resource_id, authorization_decision, approval_required,
                approver_id, approval_status, execution_status, details_json, failure_reason, session_id
            ) VALUES ('AUD-INIT-001', ?, 'system', 'system', 'system_database_seed', 'database',
                      'student_support_secure.db', 'ALLOWED', 0, NULL, 'N/A', 'SUCCESS',
                      '{"event": "System initialized and demo accounts seeded"}', NULL, 'seed-session')
            """,
            (now_ts,),
        )

        conn.execute("INSERT OR REPLACE INTO seed_meta VALUES ('demo_data_seeded', 'true')")

    return counts


def reset_database() -> dict[str, int]:
    """DEVELOPMENT ONLY: wipe database and re-seed."""
    with connection() as conn:
        conn.executescript(DROP_ALL)
    return seed_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or reset Assignment 2 secure database")
    parser.add_argument("--reset", action="store_true", help="DROP ALL TABLES and re-seed")
    parser.add_argument("--confirm", action="store_true", help="Confirm destruction")
    args = parser.parse_args()

    if args.reset:
        if not args.confirm:
            raise SystemExit("Refusing to reset without --confirm")
        res = reset_database()
        print(f"Database reset and seeded: {res}")
    else:
        res = seed_database()
        print(f"Database seeded: {res}")
