import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from facebook_pages import publish_page_post

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "posting.db"))


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def process_queue():
    published = manual = failed = 0
    now = datetime.now(timezone.utc)
    with connect() as con:
        rows = con.execute("""
            SELECT pt.id AS target_row_id, pt.status AS target_status,
                   p.id AS post_id, p.message, p.scheduled_at,
                   d.kind, d.name AS destination_name, d.target_id
            FROM post_targets pt
            JOIN posts p ON p.id=pt.post_id
            JOIN destinations d ON d.id=pt.destination_id
            WHERE pt.status='pending' AND d.enabled=1
            ORDER BY p.id, d.name
        """).fetchall()

        for row in rows:
            if row["scheduled_at"]:
                # HTML datetime-local values are local wall-clock time. To avoid timezone
                # mistakes, this prototype only runs scheduled items after the user has
                # supplied an ISO timestamp with an explicit timezone offset.
                try:
                    scheduled = datetime.fromisoformat(row["scheduled_at"])
                    if scheduled.tzinfo is None:
                        continue
                    if scheduled.astimezone(timezone.utc) > now:
                        continue
                except ValueError:
                    continue

            if row["kind"] == "group":
                con.execute(
                    "UPDATE post_targets SET status='manual_required', result=?, updated_at=? WHERE id=?",
                    ("No supported Groups publishing API; open Manual Queue and publish through Facebook yourself.",
                     now.isoformat(), row["target_row_id"])
                )
                manual += 1
                continue

            try:
                result = publish_page_post(row["target_id"], row["message"])
                con.execute(
                    "UPDATE post_targets SET status='published', result=?, updated_at=? WHERE id=?",
                    (str(result), now.isoformat(), row["target_row_id"])
                )
                published += 1
            except Exception as exc:
                con.execute(
                    "UPDATE post_targets SET status='failed', result=?, updated_at=? WHERE id=?",
                    (str(exc)[:1000], now.isoformat(), row["target_row_id"])
                )
                failed += 1
    return {"published": published, "manual": manual, "failed": failed}


if __name__ == "__main__":
    print(process_queue())
