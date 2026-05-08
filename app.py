from training_app import main

if __name__ == "__main__":
    main()

'''

from __future__ import annotations

import datetime as dt
import os
import re
import secrets
import shlex
import sqlite3
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request
from markupsafe import escape


BASE_DIR = Path(__file__).resolve().parent
*** End Patch
@app.route("/api/db/comments")
def api_comments_raw() -> Any:
    conn = get_connection()
    comments = conn.execute(
        "SELECT id, author, content, created_at, is_flagged FROM comments ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify(_rows_to_dicts(comments))


@app.route("/api/sqli/unsafe-login", methods=["POST"])
def api_sqli_unsafe_login() -> Any:
    data = request.get_json(force=True)
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))

    result = _run_unsafe_login(username, password)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/sqli/safe-login", methods=["POST"])
def api_sqli_safe_login() -> Any:
    data = request.get_json(force=True)
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    return jsonify(_run_safe_login(username, password))


@app.route("/api/xss/post", methods=["POST"])
def api_xss_post() -> Any:
    data = request.get_json(force=True)
    author = str(data.get("author", "Anonymous")).strip()[:40] or "Anonymous"
    content = str(data.get("content", "")).strip()[:400]

    if not content:
        return jsonify({"ok": False, "message": "Comment cannot be empty."}), 400

    conn = get_connection()
    conn.execute(
        "INSERT INTO comments (author, content, created_at, is_flagged) VALUES (?, ?, ?, ?)",
        (author, content, utc_now(), 1 if "<script" in content.lower() else 0),
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "message": "Comment stored. Now compare unsafe and safe rendering."})


@app.route("/api/xss/render")
def api_xss_render() -> Any:
    mode = request.args.get("mode", "unsafe").strip().lower()
    if mode not in {"safe", "unsafe"}:
        return jsonify({"ok": False, "message": "mode must be safe or unsafe"}), 400
    return jsonify(_render_comments(mode))


@app.route("/api/scrape/run", methods=["POST"])
def api_scrape_run() -> Any:
    data = request.get_json(force=True)
    selector = str(data.get("selector", "")).strip()
    attribute = str(data.get("attribute", "text")).strip() or "text"

    if not selector:
        return jsonify({"ok": False, "message": "Please provide a CSS selector."}), 400

    return jsonify(_run_scrape(selector, attribute))


@app.route("/api/sqlmap/simulate", methods=["POST"])
def api_sqlmap_simulate() -> Any:
    data = request.get_json(force=True)
    command = str(data.get("command", "")).strip()
    if not command:
        return jsonify({"ok": False, "message": "Please enter a SQLMap command."}), 400

    result = _simulate_sqlmap(command)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/sqlmap/example")
def api_sqlmap_example() -> Any:
    command = (
        "sqlmap -u http://127.0.0.1:5000/api/sqli/unsafe-login?username=test&password=test "
        "-p username --batch --risk=1 --level=2"
    )
    explanation = (
        "This practice command targets the local training endpoint and one parameter. "
        "Never run SQLMap on systems without explicit authorization."
    )
    return jsonify({"command": command, "explanation": explanation})


@app.route("/api/challenge/submit", methods=["POST"])
def api_challenge_submit() -> Any:
    data = request.get_json(force=True)
    lesson_slug = str(data.get("lesson_slug", "")).strip().lower()
    learner_name = str(data.get("learner_name", "Learner")).strip()[:60] or "Learner"
    learner_key = str(data.get("learner_key", "")).strip()
    answer = str(data.get("answer", "")).strip()[:1200]

    if lesson_slug not in LESSON_RUBRICS:
        return jsonify({"ok": False, "message": "Unknown lesson."}), 400
    if len(answer.split()) < 5:
        return jsonify({"ok": False, "message": "Please write a fuller explanation before submitting."}), 400

    if not learner_key:
        learner_key = _slugify_learner_name(learner_name)

    score, passed, feedback = _score_reflection(lesson_slug, answer)
    conn = get_connection()

    conn.execute(
        "INSERT OR IGNORE INTO learners (learner_key, display_name, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
        (learner_key, learner_name, utc_now(), utc_now()),
    )

    conn.execute(
        """
        INSERT INTO challenge_submissions (lesson_slug, learner_key, learner_name, answer, score, passed, feedback, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lesson_slug, learner_key, learner_name, answer, score, 1 if passed else 0, feedback, utc_now()),
    )

    conn.execute(
        "UPDATE learners SET last_seen_at = ? WHERE learner_key = ?",
        (utc_now(), learner_key),
    )

    conn.commit()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "lesson_slug": lesson_slug,
            "learner_key": learner_key,
            "score": score,
            "passed": passed,
            "feedback": feedback,
        }
    )


@app.route("/api/learner/register", methods=["POST"])
def api_learner_register() -> Any:
    data = request.get_json(force=True)
    learner_name = str(data.get("learner_name", "Learner")).strip()[:60] or "Learner"
    learner_key = str(data.get("learner_key", "")).strip()

    if not learner_name or len(learner_name) < 2:
        return jsonify({"ok": False, "message": "Please enter a name with at least 2 characters."}), 400

    if not learner_key:
        learner_key = _slugify_learner_name(learner_name)

    conn = get_connection()

    existing = conn.execute("SELECT learner_key FROM learners WHERE learner_key = ?", (learner_key,)).fetchone()
    if existing:
        conn.close()
        return jsonify(
            {
                "ok": True,
                "learner_key": learner_key,
                "display_name": learner_name,
                "message": "Welcome back!",
                "is_returning": True,
            }
        )

    conn.execute(
        "INSERT INTO learners (learner_key, display_name, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
        (learner_key, learner_name, utc_now(), utc_now()),
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "learner_key": learner_key,
            "display_name": learner_name,
            "message": "Welcome! Your learning profile has been created.",
            "is_returning": False,
        }
    )


@app.route("/api/challenge/progress")
def api_challenge_progress() -> Any:
    conn = get_connection()
    lessons = conn.execute("SELECT slug, title, objective FROM lessons ORDER BY sequence_no").fetchall()

    progress = []
    passed_count = 0
    for lesson in lessons:
        agg = conn.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                COALESCE(MAX(score), 0) AS best_score,
                COALESCE(MAX(passed), 0) AS has_pass
            FROM challenge_submissions
            WHERE lesson_slug = ?
            """,
            (lesson["slug"],),
        ).fetchone()

        passed = bool(agg["has_pass"])
        if passed:
            passed_count += 1

        progress.append(
            {
                "slug": lesson["slug"],
                "title": lesson["title"],
                "objective": lesson["objective"],
                "attempts": int(agg["attempts"]),
                "best_score": int(agg["best_score"]),
                "passed": passed,
            }
        )

    conn.close()
    total = len(progress)
    completion = round((passed_count / total) * 100) if total else 0
    return jsonify({"ok": True, "lessons": progress, "completion_rate": completion})


@app.route("/api/learner/<learner_key>/progress")
def api_learner_progress(learner_key: str) -> Any:
    learner_key = str(learner_key).strip().lower()
    conn = get_connection()

    learner = conn.execute("SELECT display_name, created_at, last_seen_at FROM learners WHERE learner_key = ?", (learner_key,)).fetchone()
    if not learner:
        conn.close()
        return jsonify({"ok": False, "message": "Learner not found."}), 404

    display_name = learner["display_name"]
    created_at = learner["created_at"]
    last_seen_at = learner["last_seen_at"]

    lessons = conn.execute("SELECT slug, title, objective FROM lessons ORDER BY sequence_no").fetchall()
    progress = []
    passed_count = 0

    for lesson in lessons:
        agg = conn.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                COALESCE(MAX(score), 0) AS best_score,
                COALESCE(MAX(passed), 0) AS has_pass
            FROM challenge_submissions
            WHERE lesson_slug = ? AND learner_key = ?
            """,
            (lesson["slug"], learner_key),
        ).fetchone()

        passed = bool(agg["has_pass"])
        if passed:
            passed_count += 1

        progress.append(
            {
                "slug": lesson["slug"],
                "title": lesson["title"],
                "objective": lesson["objective"],
                "attempts": int(agg["attempts"]),
                "best_score": int(agg["best_score"]),
                "passed": passed,
            }
        )

    total = len(progress)
    completion = round((passed_count / total) * 100) if total else 0

    submissions = conn.execute(
        """
        SELECT lesson_slug, score, passed, feedback, created_at, learner_name
        FROM challenge_submissions WHERE learner_key = ? ORDER BY created_at DESC LIMIT 50
        """,
        (learner_key,),
    ).fetchall()

    submission_history = [
        {
            "lesson_slug": s["lesson_slug"],
            "score": s["score"],
            "passed": bool(s["passed"]),
            "feedback": s["feedback"],
            "created_at": s["created_at"],
            "learner_name": s["learner_name"],
        }
        for s in submissions
    ]

    conn.close()

    return jsonify(
        {
            "ok": True,
            "learner_key": learner_key,
            "display_name": display_name,
            "created_at": created_at,
            "last_seen_at": last_seen_at,
            "lessons": progress,
            "completion_rate": completion,
            "submission_history": submission_history,
        }
    )


@app.route("/api/admin/meta")
def api_admin_meta() -> Any:
    return jsonify({"ok": True, "tables": ADMIN_TABLES})


@app.route("/api/admin/stats")
def api_admin_stats() -> Any:
    conn = get_connection()
    table_counts = {}
    for table_name in ADMIN_TABLES:
        total = conn.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()["total"]
        table_counts[table_name] = int(total)

    challenge_agg = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(passed), 0) AS passed_total FROM challenge_submissions"
    ).fetchone()
    total = int(challenge_agg["total"])
    passed_total = int(challenge_agg["passed_total"])
    pass_rate = round((passed_total / total) * 100) if total else 0

    flagged_comments = conn.execute(
        "SELECT COUNT(*) AS total FROM comments WHERE is_flagged = 1"
    ).fetchone()["total"]
    conn.close()

    return jsonify(
        {
            "ok": True,
            "table_counts": table_counts,
            "challenge_pass_rate": pass_rate,
            "flagged_comments": int(flagged_comments),
        }
    )


@app.route("/api/admin/rows")
def api_admin_rows() -> Any:
    table = request.args.get("table", "users").strip().lower()
    if table not in ADMIN_TABLES:
        return jsonify({"ok": False, "message": "Unknown table."}), 400

    search = request.args.get("search", "").strip()
    filter_column = request.args.get("filter_column", "").strip()
    filter_value = request.args.get("filter_value", "").strip()
    sort_by = request.args.get("sort_by", ADMIN_TABLES[table]["columns"][0]).strip()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    page = _safe_int(request.args.get("page"), 1, 1, 500)
    per_page = _safe_int(request.args.get("per_page"), 10, 1, 100)

    data = _admin_query_rows(
        table=table,
        search=search,
        filter_column=filter_column,
        filter_value=filter_value,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        per_page=per_page,
    )
    data["ok"] = True
    return jsonify(data)


@app.route("/api/terminal/execute", methods=["POST"])
def api_terminal_execute() -> Any:
    data = request.get_json(force=True)
    tool = str(data.get("tool", "sqli")).strip().lower() or "sqli"
    command = str(data.get("command", "")).strip()

    if tool not in TERMINAL_TOOLS:
        return jsonify({"ok": False, "message": "Unknown tool profile."}), 400

    result = _execute_terminal_command(tool, command)
    summary = " | ".join(result.get("lines", [])[:3])
    log_activity(tool, command, bool(result.get("ok")), summary)

    status = 200 if result.get("ok") else 400
    return jsonify(result), status


if __name__ == "__main__":
    _db_ready = True
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)
'''