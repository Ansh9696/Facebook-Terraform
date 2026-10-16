import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from facebook_pages import publish_page_post

load_dotenv()
APP_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DATABASE_PATH", str(APP_DIR / "posting.db"))
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-local-dev-key")


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('page','group')),
            target_id TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            scheduled_at TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            last_error TEXT
        );
        CREATE TABLE IF NOT EXISTS post_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            destination_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            updated_at TEXT,
            UNIQUE(post_id, destination_id),
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(destination_id) REFERENCES destinations(id)
        );
        """)


@app.get("/")
def index():
    with connect() as con:
        posts = con.execute("SELECT * FROM posts ORDER BY id DESC LIMIT 50").fetchall()
        destinations = con.execute("SELECT * FROM destinations ORDER BY kind, name").fetchall()
        counts = {
            "destinations": con.execute("SELECT COUNT(*) FROM destinations").fetchone()[0],
            "pending": con.execute("SELECT COUNT(*) FROM post_targets WHERE status IN ('pending','manual_required')").fetchone()[0],
        }
    return render_template("index.html", posts=posts, destinations=destinations, counts=counts)


@app.post("/destinations")
def add_destination():
    name = request.form.get("name", "").strip()
    kind = request.form.get("kind", "group")
    target_id = request.form.get("target_id", "").strip()
    if not name or kind not in ("page", "group"):
        flash("Enter a destination name and valid type.", "error")
        return redirect(url_for("index"))
    if kind == "page" and not target_id:
        flash("For a Page destination, enter the Facebook Page ID.", "error")
        return redirect(url_for("index"))
    with connect() as con:
        con.execute("INSERT INTO destinations(name, kind, target_id) VALUES(?,?,?)", (name, kind, target_id))
    flash("Destination saved.", "success")
    return redirect(url_for("index"))


@app.post("/posts")
def create_post():
    message = request.form.get("message", "").strip()
    scheduled_at = request.form.get("scheduled_at", "").strip() or None
    selected = request.form.getlist("destination_ids")
    if not message or not selected:
        flash("Add post text and select at least one destination.", "error")
        return redirect(url_for("index"))
    created = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur = con.execute(
            "INSERT INTO posts(message, scheduled_at, status, created_at) VALUES(?,?,?,?)",
            (message, scheduled_at, "queued", created)
        )
        post_id = cur.lastrowid
        for dest_id in selected:
            con.execute(
                "INSERT OR IGNORE INTO post_targets(post_id, destination_id, status) VALUES(?,?,?)",
                (post_id, int(dest_id), "pending")
            )
    flash(f"Post #{post_id} queued. Page destinations can be published by the worker; Groups are queued for manual posting.", "success")
    return redirect(url_for("index"))


@app.post("/run-worker")
def run_worker_route():
    # Useful for local testing. Production scheduling should call worker.py via Task Scheduler/cron.
    from worker import process_queue
    result = process_queue()
    flash(f"Worker finished: {result['published']} Page post(s) published, {result['manual']} Group item(s) marked for manual action, {result['failed']} failure(s).", "success")
    return redirect(url_for("index"))


@app.get("/manual-queue")
def manual_queue():
    with connect() as con:
        rows = con.execute("""
            SELECT pt.id AS target_row_id, pt.status AS target_status, pt.result,
                   p.id AS post_id, p.message, d.name AS destination_name
            FROM post_targets pt
            JOIN posts p ON p.id=pt.post_id
            JOIN destinations d ON d.id=pt.destination_id
            WHERE d.kind='group'
            ORDER BY p.id DESC, d.name
        """).fetchall()
    return render_template("manual_queue.html", rows=rows)


@app.post("/manual-queue/<int:target_row_id>/done")
def mark_manual_done(target_row_id):
    with connect() as con:
        con.execute(
            "UPDATE post_targets SET status='manually_marked_done', updated_at=?, result=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), "Marked done by user; app does not verify Facebook publication.", target_row_id)
        )
    flash("Marked as done. This is a user-entered status, not Facebook-verified.", "success")
    return redirect(url_for("manual_queue"))


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
