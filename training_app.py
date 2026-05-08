from __future__ import annotations

import datetime as dt
import html
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "training_app.db"


SCRAPE_TARGET_HTML = """
<section id="catalog">
  <article class="item" data-sku="BK-101">
    <h3>DSP Textbook</h3>
    <p class="category">Books</p>
    <p class="price">$42.00</p>
  </article>
  <article class="item" data-sku="EL-220">
    <h3>Laptop</h3>
    <p class="category">Electronics</p>
    <p class="price">$899.99</p>
  </article>
  <article class="item" data-sku="LAB-77">
    <h3>USB Oscilloscope</h3>
    <p class="category">Lab Tools</p>
    <p class="price">$120.50</p>
  </article>
  <article class="item" data-sku="ST-18">
    <h3>Notebook</h3>
    <p class="category">Stationery</p>
    <p class="price">$4.75</p>
  </article>
</section>
""".strip()


@dataclass(frozen=True)
class LessonConfig:
    key: str
    title: str
    concept: str
    task: str
    keywords: tuple[str, ...]


LESSONS: dict[str, LessonConfig] = {
    "sqli": LessonConfig(
        key="sqli",
        title="SQL Injection",
        concept="When a query is built from plain text, the user's text can change the meaning of the query.",
        task="Use the fake bank login to show what unsafe login reveals, then compare it with the safe login.",
        keywords=("parameterized", "placeholder", "query", "data", "logic"),
    ),
    "xss": LessonConfig(
        key="xss",
        title="Cross-Site Scripting",
        concept="If untrusted content is shown as HTML instead of text, a browser can run attacker-controlled code.",
        task="Post a comment, then compare unsafe rendering with safe escaping.",
        keywords=("escape", "encode", "browser", "html", "script"),
    ),
    "scraping": LessonConfig(
        key="scraping",
        title="Web Scraping",
        concept="Scraping is precise reading: use the right selector and the right attribute to extract exactly what you want.",
        task="Use a selector to pull the right names and SKUs from a fake catalog.",
        keywords=("selector", "attribute", "extract", "match", "pattern"),
    ),
    "sqlmap": LessonConfig(
        key="sqlmap",
        title="SQLMap Concepts",
        concept="Tools like SQLMap read evidence. The lesson is how to interpret scan output and choose the right defense.",
        task="Run a simulated scan, read the evidence, and explain the defensive fix.",
        keywords=("parameter", "evidence", "permission", "defense", "risk"),
    ),
}


class TrainingRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def now() -> str:
        return dt.datetime.utcnow().replace(microsecond=0).isoformat()

    def init_db(self) -> None:
        conn = self.connect()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS learners (
                name TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lesson_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_name TEXT NOT NULL,
                lesson_key TEXT NOT NULL,
                answer TEXT NOT NULL,
                score INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                feedback TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                account_no TEXT NOT NULL,
                balance REAL NOT NULL,
                ssn TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        if cur.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"] == 0:
            cur.executemany(
                "INSERT INTO customers (username, password, full_name, account_no, balance, ssn) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("alice", "wonderland123", "Alice Chen", "AC-1029", 4850.75, "111-22-3333"),
                    ("bob", "builder456", "Bob Rivera", "BR-3381", 912.40, "222-33-4444"),
                    ("charlie", "signal789", "Charlie Patel", "CP-7784", 12870.10, "333-44-5555"),
                    ("dana", "defender007", "Dana Wong", "DW-5542", 2205.98, "444-55-6666"),
                ],
            )

        if cur.execute("SELECT COUNT(*) AS count FROM comments").fetchone()["count"] == 0:
            now = self.now()
            cur.executemany(
                "INSERT INTO comments (author, content, created_at) VALUES (?, ?, ?)",
                [
                    ("Tutor", "Welcome. Test safely and explain every result in your own words.", now),
                    ("Student", "I can compare unsafe output and safe output now.", now),
                ],
            )

        if cur.execute("SELECT COUNT(*) AS count FROM catalog_items").fetchone()["count"] == 0:
            cur.executemany(
                "INSERT INTO catalog_items (sku, name, category, price) VALUES (?, ?, ?, ?)",
                [
                    ("BK-101", "DSP Textbook", "Books", 42.00),
                    ("EL-220", "Laptop", "Electronics", 899.99),
                    ("LAB-77", "USB Oscilloscope", "Lab Tools", 120.50),
                    ("ST-18", "Notebook", "Stationery", 4.75),
                ],
            )

        conn.commit()
        conn.close()

    def log_activity(self, tool: str, action: str, success: bool, details: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO activity_log (tool, action, success, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (tool, action, 1 if success else 0, details[:500], self.now()),
        )
        conn.commit()
        conn.close()

    def get_or_create_learner(self, name: str) -> dict[str, Any]:
        learner_name = name.strip()[:80] or "Learner"
        conn = self.connect()
        existing = conn.execute("SELECT name, created_at, last_seen_at FROM learners WHERE name = ?", (learner_name,)).fetchone()
        if existing:
            conn.execute("UPDATE learners SET last_seen_at = ? WHERE name = ?", (self.now(), learner_name))
            conn.commit()
            conn.close()
            return dict(existing)

        now = self.now()
        conn.execute(
            "INSERT INTO learners (name, created_at, last_seen_at) VALUES (?, ?, ?)",
            (learner_name, now, now),
        )
        conn.commit()
        conn.close()
        return {"name": learner_name, "created_at": now, "last_seen_at": now}

    def record_attempt(self, learner_name: str, lesson_key: str, answer: str) -> tuple[int, bool, str]:
        score, passed, feedback = score_reflection(lesson_key, answer)
        conn = self.connect()
        conn.execute(
            """
            INSERT INTO lesson_attempts (learner_name, lesson_key, answer, score, passed, feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (learner_name, lesson_key, answer[:1500], score, 1 if passed else 0, feedback, self.now()),
        )
        conn.commit()
        conn.close()
        self.log_activity("reflection", lesson_key, passed, feedback)
        return score, passed, feedback

    def lesson_progress(self, learner_name: str) -> list[dict[str, Any]]:
        conn = self.connect()
        rows = []
        for lesson_key, lesson in LESSONS.items():
            agg = conn.execute(
                """
                SELECT
                    COUNT(*) AS attempts,
                    COALESCE(MAX(score), 0) AS best_score,
                    COALESCE(MAX(passed), 0) AS has_pass
                FROM lesson_attempts
                WHERE learner_name = ? AND lesson_key = ?
                """,
                (learner_name, lesson_key),
            ).fetchone()
            rows.append(
                {
                    "lesson_key": lesson_key,
                    "title": lesson.title,
                    "attempts": int(agg["attempts"]),
                    "best_score": int(agg["best_score"]),
                    "passed": bool(agg["has_pass"]),
                }
            )
        conn.close()
        return rows

    def recent_attempts(self, learner_name: str, limit: int = 20) -> list[dict[str, Any]]:
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT lesson_key, score, passed, feedback, created_at, answer
            FROM lesson_attempts
            WHERE learner_name = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (learner_name, limit),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def customers(self, query: str = "") -> list[dict[str, Any]]:
        conn = self.connect()
        if query:
            rows = conn.execute(
                """
                SELECT id, username, password, full_name, account_no, balance, ssn
                FROM customers
                WHERE username LIKE ? OR full_name LIKE ? OR account_no LIKE ?
                ORDER BY id
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, username, password, full_name, account_no, balance, ssn FROM customers ORDER BY id"
            ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def unsafe_login(self, username: str, password: str) -> dict[str, Any]:
        sql = (
            "SELECT id, username, full_name, account_no, balance, ssn FROM customers "
            f"WHERE username = '{username}' AND password = '{password}'"
        )
        conn = self.connect()
        rows = conn.execute(sql).fetchall()
        conn.close()
        self.log_activity("sqli", "unsafe-login", bool(rows), sql)
        return {"sql": sql, "rows": [dict(row) for row in rows]}

    def safe_login(self, username: str, password: str) -> dict[str, Any]:
        sql = "SELECT id, username, full_name, account_no, balance, ssn FROM customers WHERE username = ? AND password = ?"
        conn = self.connect()
        rows = conn.execute(sql, (username, password)).fetchall()
        conn.close()
        self.log_activity("sqli", "safe-login", bool(rows), sql)
        return {"sql": sql, "rows": [dict(row) for row in rows]}

    def add_comment(self, author: str, content: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO comments (author, content, created_at) VALUES (?, ?, ?)",
            (author.strip()[:50] or "Learner", content.strip()[:800], self.now()),
        )
        conn.commit()
        conn.close()
        self.log_activity("xss", "post-comment", True, content)

    def comments(self) -> list[dict[str, Any]]:
        conn = self.connect()
        rows = conn.execute("SELECT id, author, content, created_at FROM comments ORDER BY id DESC").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def scrape_catalog(self, selector: str, attribute: str) -> list[str]:
        soup = BeautifulSoup(SCRAPE_TARGET_HTML, "html.parser")
        matches = soup.select(selector)
        results: list[str] = []
        if attribute == "text":
            for match in matches:
                text = match.get_text(" ", strip=True)
                if text:
                    results.append(text)
        else:
            for match in matches:
                value = match.get(attribute)
                if value:
                    results.append(str(value))
        self.log_activity("scrape", selector, bool(results), f"{selector} -> {attribute}")
        return results

    def sqlmap_scan(self, target: str, command: str) -> list[str]:
        lowered = target.lower()
        vulnerable = ("unsafe" in lowered) or (("login" in lowered) and ("safe" not in lowered))
        lines = [
            "[info] starting scan",
            f"[info] target: {target}",
            f"[info] command: {command}",
        ]
        if vulnerable:
            lines.extend(
                [
                    "[critical] parameter 'username' appears injectable",
                    "[critical] boolean-based blind response confirmed",
                    "[critical] time-based response variation observed",
                    "[next] fix: use parameterized queries and avoid string concatenation",
                ]
            )
        else:
            lines.extend(
                [
                    "[warning] no clear injection point found",
                    "[hint] focus on a known vulnerable endpoint before testing",
                    "[next] defend by keeping input as data and limiting attack surface",
                ]
            )
        self.log_activity("sqlmap", target, vulnerable, command)
        return lines

    def database_tables(self) -> dict[str, list[dict[str, Any]]]:
        conn = self.connect()
        table_map = {
            "learners": "SELECT name, created_at, last_seen_at FROM learners ORDER BY name",
            "lesson_attempts": "SELECT id, learner_name, lesson_key, score, passed, created_at FROM lesson_attempts ORDER BY id DESC",
            "customers": "SELECT id, username, password, full_name, account_no, balance, ssn FROM customers ORDER BY id",
            "comments": "SELECT id, author, content, created_at FROM comments ORDER BY id DESC",
            "catalog_items": "SELECT id, sku, name, category, price FROM catalog_items ORDER BY id",
            "activity_log": "SELECT id, tool, action, success, details, created_at FROM activity_log ORDER BY id DESC",
        }
        result: dict[str, list[dict[str, Any]]] = {}
        for table, sql in table_map.items():
            result[table] = [dict(row) for row in conn.execute(sql).fetchall()]
        conn.close()
        return result


def score_reflection(lesson_key: str, answer: str) -> tuple[int, bool, str]:
    lesson = LESSONS.get(lesson_key)
    if not lesson:
        return 0, False, "Unknown lesson."

    normalized = answer.lower()
    hits = [keyword for keyword in lesson.keywords if keyword in normalized]
    score = round((len(hits) / len(lesson.keywords)) * 100) if lesson.keywords else 0
    enough_words = len(answer.split()) >= 10
    passed = score >= 60 and enough_words

    missing = [keyword for keyword in lesson.keywords if keyword not in hits]
    if passed:
        feedback = "Good. You explained the evidence and the defense clearly."
    else:
        feedback = f"Add more detail about: {', '.join(missing) if missing else 'the evidence'}"
    return score, passed, feedback


class TrainingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.repo = TrainingRepository(DB_PATH)
        self.title("Defender Ops Training Studio")
        self.geometry("1560x980")
        self.minsize(1300, 860)
        self.configure(bg="#101826")

        self.learner_name = tk.StringVar(value="Learner")
        self.status_text = tk.StringVar(value="Enter a learner name, then use a lesson to learn and prove understanding.")

        self.lesson_refs: dict[str, dict[str, Any]] = {}
        self.table_refs: dict[str, ttk.Treeview] = {}

        self._configure_style()
        self._build_shell()
        self._refresh_all_views()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#101826")
        style.configure("Panel.TFrame", background="#142033")
        style.configure("Title.TLabel", background="#101826", foreground="#f4f7fb", font=("Segoe UI", 22, "bold"))
        style.configure("SubTitle.TLabel", background="#101826", foreground="#c9d6e8", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background="#142033", foreground="#f4f7fb", font=("Segoe UI", 14, "bold"))
        style.configure("Body.TLabel", background="#142033", foreground="#dde6f3", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.configure("TNotebook", background="#101826", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 10), font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_shell(self) -> None:
        header = ttk.Frame(self, style="App.TFrame", padding=(16, 14))
        header.pack(fill="x")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Defender Ops Training Studio", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="A local app that teaches the concept first, then lets the learner demonstrate it in a real emulation.",
            style="SubTitle.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        profile = ttk.Frame(header, style="App.TFrame")
        profile.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Label(profile, text="Learner", style="SubTitle.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.learner_entry = ttk.Entry(profile, textvariable=self.learner_name, width=28)
        self.learner_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(profile, text="Load Profile", style="Accent.TButton", command=self._load_learner).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(profile, text="Reset", command=self._reset_learner).grid(row=0, column=3)

        self.progress_strip = ttk.Frame(self, style="App.TFrame", padding=(16, 0, 16, 10))
        self.progress_strip.pack(fill="x")
        ttk.Label(self.progress_strip, textvariable=self.status_text, style="SubTitle.TLabel").pack(anchor="w")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.overview_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
        self.sqli_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
        self.xss_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
        self.scrape_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
        self.sqlmap_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
        self.database_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
        self.progress_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)

        self.notebook.add(self.overview_tab, text="Start Here")
        self.notebook.add(self.sqli_tab, text="SQL Injection")
        self.notebook.add(self.xss_tab, text="XSS")
        self.notebook.add(self.scrape_tab, text="Scraping")
        self.notebook.add(self.sqlmap_tab, text="SQLMap")
        self.notebook.add(self.database_tab, text="Database View")
        self.notebook.add(self.progress_tab, text="Progress")

        self._build_overview_tab()
        self._build_sqli_tab()
        self._build_xss_tab()
        self._build_scrape_tab()
        self._build_sqlmap_tab()
        self._build_database_tab()
        self._build_progress_tab()

        footer = ttk.Frame(self, style="App.TFrame", padding=(16, 0, 16, 14))
        footer.pack(fill="x")
        ttk.Label(footer, text="Local defensive training only. Never test systems without permission.", style="SubTitle.TLabel").pack(anchor="w")

    def _panel(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        frame.pack(fill="both", expand=True, pady=(0, 12))
        return frame

    def _text_output(self, parent: ttk.Frame, height: int = 12) -> scrolledtext.ScrolledText:
        box = scrolledtext.ScrolledText(parent, wrap="word", height=height, font=("Consolas", 10), bg="#0f1726", fg="#eff5ff", insertbackground="#eff5ff")
        box.configure(state="disabled")
        return box

    def _write_output(self, widget: scrolledtext.ScrolledText, lines: list[str] | str) -> None:
        if isinstance(lines, str):
            lines = [lines]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", "\n".join(lines))
        widget.configure(state="disabled")

    def _append_output(self, widget: scrolledtext.ScrolledText, lines: list[str] | str) -> None:
        if isinstance(lines, str):
            lines = [lines]
        widget.configure(state="normal")
        for line in lines:
            widget.insert("end", f"{line}\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _table_widget(self, parent: ttk.Frame, columns: tuple[str, ...], headings: tuple[str, ...], height: int) -> tuple[ttk.Frame, ttk.Treeview]:
        container = ttk.Frame(parent, style="Panel.TFrame")
        tree = ttk.Treeview(container, columns=columns, show="headings", height=height)
        for column, heading in zip(columns, headings, strict=True):
            tree.heading(column, text=heading)
            tree.column(column, width=160, anchor="w", stretch=True)
        if len(columns) == 1:
            tree.column(columns[0], width=420, anchor="w", stretch=True)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return container, tree

    def _load_learner(self) -> None:
        learner = self.repo.get_or_create_learner(self.learner_name.get())
        self.learner_name.set(learner["name"])
        self.status_text.set(f"Loaded learner profile: {learner['name']}\nNow use a lesson tab, then explain what you saw.")
        self._refresh_all_views()

    def _reset_learner(self) -> None:
        self.learner_name.set("Learner")
        self.status_text.set("Learner profile reset. Enter a name to begin.")
        self._refresh_all_views()

    def _current_learner(self) -> str:
        name = self.learner_name.get().strip() or "Learner"
        self.learner_name.set(name)
        return self.repo.get_or_create_learner(name)["name"]

    def _build_overview_tab(self) -> None:
        panel = self._panel(self.overview_tab)
        panel.columnconfigure(0, weight=2)
        panel.columnconfigure(1, weight=1)

        left = ttk.Frame(panel, style="Panel.TFrame")
        right = ttk.Frame(panel, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(left, text="Start Here", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="This app teaches each concept in plain language, then asks the learner to prove understanding inside the emulation.",
            style="Body.TLabel",
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(8, 12))

        for title, body in [
            ("1. Learn", "Read the explanation first. The app tells you what the technique does and why it matters."),
            ("2. Test", "Use the fake bank login, comment board, catalog scraper, or scan simulator to act it out."),
            ("3. Explain", "Write a short reflection. The app scores it and saves your progress."),
        ]:
            card = ttk.Frame(left, style="Panel.TFrame", padding=12)
            card.pack(fill="x", pady=6)
            ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="w")
            ttk.Label(card, text=body, style="Body.TLabel", wraplength=760, justify="left").pack(anchor="w", pady=(4, 0))

        ttk.Label(right, text="Learner Progress", style="Section.TLabel").pack(anchor="w")
        self.overview_text = ttk.Label(right, text="", style="Body.TLabel", justify="left")
        self.overview_text.pack(anchor="w", pady=(8, 12))

    def _make_reflection_block(self, parent: ttk.Frame) -> tuple[tk.Text, ttk.Label]:
        box = ttk.Frame(parent, style="Panel.TFrame")
        box.pack(fill="x", pady=(10, 0))
        ttk.Label(box, text="Demonstrate Understanding", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            box,
            text="Write what happened, what evidence you saw, and which defense should be used.",
            style="Body.TLabel",
            wraplength=850,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))
        answer = tk.Text(box, height=5, wrap="word", font=("Segoe UI", 10), bg="#f6f8fb", fg="#111827")
        answer.pack(fill="x", expand=True)
        result = ttk.Label(box, text="", style="Body.TLabel", wraplength=850, justify="left")
        result.pack(anchor="w", pady=(8, 0))
        return answer, result

    def _build_sqli_tab(self) -> None:
        panel = self._panel(self.sqli_tab)
        panel.columnconfigure(0, weight=2)
        panel.columnconfigure(1, weight=1)
        left = ttk.Frame(panel, style="Panel.TFrame")
        right = ttk.Frame(panel, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        lesson = LESSONS["sqli"]
        ttk.Label(left, text=lesson.title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=lesson.concept, style="Body.TLabel", wraplength=840, justify="left").pack(anchor="w", pady=(6, 6))
        ttk.Label(left, text=lesson.task, style="Body.TLabel", wraplength=840, justify="left").pack(anchor="w", pady=(0, 12))

        bank = ttk.LabelFrame(left, text="Fake Bank Login", padding=12)
        bank.pack(fill="x", pady=(0, 12))
        bank.columnconfigure(1, weight=1)
        ttk.Label(bank, text="Username") .grid(row=0, column=0, sticky="w", pady=4)
        self.sqli_user = ttk.Entry(bank)
        self.sqli_user.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(bank, text="Password").grid(row=1, column=0, sticky="w", pady=4)
        self.sqli_pass = ttk.Entry(bank, show="*")
        self.sqli_pass.grid(row=1, column=1, sticky="ew", pady=4)
        btns = ttk.Frame(bank)
        btns.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(btns, text="Unsafe Login", command=self._sqli_unsafe).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Safe Login", command=self._sqli_safe).pack(side="left")

        self.sqli_output = self._text_output(left, height=14)
        self.sqli_output.pack(fill="both", expand=True, pady=(0, 12))

        self.sqli_answer, self.sqli_result = self._make_reflection_block(left)
        ttk.Button(left, text="Submit Reflection", style="Accent.TButton", command=lambda: self._submit_reflection("sqli")).pack(anchor="w", pady=(8, 0))

        ttk.Label(right, text="Live Bank Database", style="Section.TLabel").pack(anchor="w")
        ttk.Label(right, text="This preview shows the same fake customer records the login query reads from.", style="Body.TLabel", wraplength=450, justify="left").pack(anchor="w", pady=(6, 8))
        sqli_container, self.sqli_db = self._table_widget(right, ("username", "full_name", "account_no", "balance", "ssn"), ("Username", "Name", "Account", "Balance", "SSN"), 10)
        sqli_container.pack(fill="both", expand=True)
        self.lesson_refs["sqli"] = {"answer": self.sqli_answer, "result": self.sqli_result}

    def _build_xss_tab(self) -> None:
        panel = self._panel(self.xss_tab)
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)
        left = ttk.Frame(panel, style="Panel.TFrame")
        right = ttk.Frame(panel, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        lesson = LESSONS["xss"]
        ttk.Label(left, text=lesson.title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=lesson.concept, style="Body.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(6, 6))
        ttk.Label(left, text=lesson.task, style="Body.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(0, 12))

        form = ttk.LabelFrame(left, text="Fake Comment Board", padding=12)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Author").grid(row=0, column=0, sticky="w", pady=4)
        self.xss_author = ttk.Entry(form)
        self.xss_author.insert(0, "Student")
        self.xss_author.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Content").grid(row=1, column=0, sticky="nw", pady=4)
        self.xss_content = tk.Text(form, height=4, wrap="word", font=("Segoe UI", 10), bg="#f6f8fb", fg="#111827")
        self.xss_content.grid(row=1, column=1, sticky="ew", pady=4)
        controls = ttk.Frame(form)
        controls.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(controls, text="Store Comment", command=self._xss_store_comment).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Unsafe Render", command=lambda: self._xss_render("unsafe")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Safe Render", command=lambda: self._xss_render("safe")).pack(side="left")

        self.xss_output = self._text_output(left, height=14)
        self.xss_output.pack(fill="both", expand=True, pady=(0, 12))

        self.xss_answer, self.xss_result = self._make_reflection_block(left)
        ttk.Button(left, text="Submit Reflection", style="Accent.TButton", command=lambda: self._submit_reflection("xss")).pack(anchor="w", pady=(8, 0))

        ttk.Label(right, text="Rendered Comment Board", style="Section.TLabel").pack(anchor="w")
        ttk.Label(right, text="Unsafe mode is a simulated browser preview. Safe mode escapes the same text so it stays plain.", style="Body.TLabel", wraplength=450, justify="left").pack(anchor="w", pady=(6, 8))
        xss_container, self.xss_board = self._table_widget(right, ("author", "content", "created_at"), ("Author", "Content", "Created"), 16)
        xss_container.pack(fill="both", expand=True)
        self.lesson_refs["xss"] = {"answer": self.xss_answer, "result": self.xss_result}

    def _build_scrape_tab(self) -> None:
        panel = self._panel(self.scrape_tab)
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)
        left = ttk.Frame(panel, style="Panel.TFrame")
        right = ttk.Frame(panel, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        lesson = LESSONS["scraping"]
        ttk.Label(left, text=lesson.title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=lesson.concept, style="Body.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(6, 6))
        ttk.Label(left, text=lesson.task, style="Body.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(0, 12))

        source_frame = ttk.LabelFrame(left, text="Fake Catalog HTML", padding=10)
        source_frame.pack(fill="x", pady=(0, 12))
        self.scrape_source = tk.Text(source_frame, height=12, wrap="word", font=("Consolas", 9), bg="#f6f8fb", fg="#111827")
        self.scrape_source.insert("1.0", SCRAPE_TARGET_HTML)
        self.scrape_source.configure(state="disabled")
        self.scrape_source.pack(fill="x")

        query = ttk.LabelFrame(left, text="Selector Practice", padding=10)
        query.pack(fill="x", pady=(0, 12))
        query.columnconfigure(1, weight=1)
        ttk.Label(query, text="Selector").grid(row=0, column=0, sticky="w", pady=4)
        self.scrape_selector = ttk.Entry(query)
        self.scrape_selector.insert(0, "article.item h3")
        self.scrape_selector.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(query, text="Attribute").grid(row=1, column=0, sticky="w", pady=4)
        self.scrape_attribute = ttk.Combobox(query, values=["text", "data-sku"], state="readonly")
        self.scrape_attribute.set("text")
        self.scrape_attribute.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(query, text="Extract", command=self._scrape_run).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.scrape_output = self._text_output(left, height=10)
        self.scrape_output.pack(fill="both", expand=True, pady=(0, 12))

        self.scrape_answer, self.scrape_result = self._make_reflection_block(left)
        ttk.Button(left, text="Submit Reflection", style="Accent.TButton", command=lambda: self._submit_reflection("scraping")).pack(anchor="w", pady=(8, 0))

        ttk.Label(right, text="Extracted Results", style="Section.TLabel").pack(anchor="w")
        ttk.Label(right, text="The live app shows how specific selectors pull only the intended records.", style="Body.TLabel", wraplength=450, justify="left").pack(anchor="w", pady=(6, 8))
        scrape_container, self.scrape_results = self._table_widget(right, ("value",), ("Value",), 16)
        scrape_container.pack(fill="both", expand=True)
        self.lesson_refs["scraping"] = {"answer": self.scrape_answer, "result": self.scrape_result}

    def _build_sqlmap_tab(self) -> None:
        panel = self._panel(self.sqlmap_tab)
        panel.columnconfigure(0, weight=2)
        panel.columnconfigure(1, weight=1)
        left = ttk.Frame(panel, style="Panel.TFrame")
        right = ttk.Frame(panel, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        lesson = LESSONS["sqlmap"]
        ttk.Label(left, text=lesson.title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=lesson.concept, style="Body.TLabel", wraplength=840, justify="left").pack(anchor="w", pady=(6, 6))
        ttk.Label(left, text=lesson.task, style="Body.TLabel", wraplength=840, justify="left").pack(anchor="w", pady=(0, 12))

        scan = ttk.LabelFrame(left, text="Simulated Scan", padding=12)
        scan.pack(fill="x", pady=(0, 12))
        scan.columnconfigure(1, weight=1)
        ttk.Label(scan, text="Target").grid(row=0, column=0, sticky="w", pady=4)
        self.sqlmap_target = ttk.Combobox(scan, values=["Fake Bank Login (unsafe)", "Fake Bank Login (safe)"], state="readonly")
        self.sqlmap_target.set("Fake Bank Login (unsafe)")
        self.sqlmap_target.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(scan, text="Command").grid(row=1, column=0, sticky="w", pady=4)
        self.sqlmap_command = ttk.Entry(scan)
        self.sqlmap_command.insert(0, "sqlmap -u bank://login -p username --batch")
        self.sqlmap_command.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(scan, text="Run Scan", command=self._sqlmap_scan).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.sqlmap_output = self._text_output(left, height=14)
        self.sqlmap_output.pack(fill="both", expand=True, pady=(0, 12))

        self.sqlmap_answer, self.sqlmap_result = self._make_reflection_block(left)
        ttk.Button(left, text="Submit Reflection", style="Accent.TButton", command=lambda: self._submit_reflection("sqlmap")).pack(anchor="w", pady=(8, 0))

        ttk.Label(right, text="Evidence Summary", style="Section.TLabel").pack(anchor="w")
        ttk.Label(right, text="Use the scan output to decide what defensive code change should come first.", style="Body.TLabel", wraplength=450, justify="left").pack(anchor="w", pady=(6, 8))
        self.sqlmap_evidence = self._text_output(right, height=24)
        self.sqlmap_evidence.pack(fill="both", expand=True)
        self._write_output(self.sqlmap_evidence, ["Run a scan to see evidence."])
        self.lesson_refs["sqlmap"] = {"answer": self.sqlmap_answer, "result": self.sqlmap_result}

    def _build_database_tab(self) -> None:
        panel = self._panel(self.database_tab)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        controls = ttk.Frame(panel, style="Panel.TFrame")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(controls, text="Table", style="Body.TLabel").pack(side="left", padx=(0, 6))
        self.db_table = ttk.Combobox(controls, values=list(self.repo.database_tables().keys()), state="readonly", width=24)
        self.db_table.set("customers")
        self.db_table.pack(side="left", padx=(0, 10))
        ttk.Label(controls, text="Search", style="Body.TLabel").pack(side="left", padx=(0, 6))
        self.db_search = ttk.Entry(controls, width=30)
        self.db_search.pack(side="left", padx=(0, 10))
        ttk.Button(controls, text="Refresh", command=self._refresh_database_view).pack(side="left")

        self.db_status = ttk.Label(panel, text="", style="Body.TLabel")
        self.db_status.grid(row=0, column=0, sticky="e", pady=(0, 10))

        db_container, self.db_tree = self._table_widget(panel, ("value",), ("Value",), 24)
        db_container.grid(row=1, column=0, sticky="nsew")

    def _build_progress_tab(self) -> None:
        panel = self._panel(self.progress_tab)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        self.progress_summary = ttk.Label(panel, text="", style="Body.TLabel", justify="left")
        self.progress_summary.grid(row=0, column=0, sticky="w", pady=(0, 12))

        inner = ttk.Frame(panel, style="Panel.TFrame")
        inner.grid(row=1, column=0, sticky="nsew")
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)
        inner.rowconfigure(0, weight=1)

        left = ttk.Frame(inner, style="Panel.TFrame")
        right = ttk.Frame(inner, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(left, text="Lesson Progress", style="Section.TLabel").pack(anchor="w")
        progress_container, self.progress_table = self._table_widget(left, ("lesson", "attempts", "best_score", "passed"), ("Lesson", "Attempts", "Best", "Passed"), 12)
        progress_container.pack(fill="both", expand=True, pady=(8, 0))

        ttk.Label(right, text="Recent Attempts", style="Section.TLabel").pack(anchor="w")
        history_container, self.history_table = self._table_widget(right, ("lesson", "score", "passed", "created_at"), ("Lesson", "Score", "Passed", "Time"), 12)
        history_container.pack(fill="both", expand=True, pady=(8, 0))

    def _submit_reflection(self, lesson_key: str) -> None:
        learner = self._current_learner()
        answer_widget = self.lesson_refs[lesson_key]["answer"]
        result_widget = self.lesson_refs[lesson_key]["result"]
        answer = answer_widget.get("1.0", "end").strip()
        if len(answer.split()) < 8:
            messagebox.showinfo("More detail needed", "Write a fuller explanation before submitting.")
            return
        score, passed, feedback = self.repo.record_attempt(learner, lesson_key, answer)
        result_widget.configure(text=f"Score {score}% | {'Passed' if passed else 'Needs more detail'} | {feedback}")
        self.status_text.set(f"Saved reflection for {learner}. Score {score}% on {LESSONS[lesson_key].title}.")
        self._refresh_all_views()

    def _sqli_unsafe(self) -> None:
        learner = self._current_learner()
        username = self.sqli_user.get().strip() or "admin"
        password = self.sqli_pass.get().strip() or "x"
        result = self.repo.unsafe_login(username, password)
        lines = [
            "[lesson] SQL Injection: unsafe string concatenation lets input change the query.",
            f"[query] {result['sql']}",
        ]
        if result["rows"]:
            lines.append("[critical] query returned customer data:")
            for row in result["rows"]:
                lines.append(f"  - {row['username']} | {row['full_name']} | {row['account_no']} | ${row['balance']:.2f} | {row['ssn']}")
            lines.append("[next] defend this by keeping the user input as data, not SQL.")
        else:
            lines.append("[info] no row matched.")
        self._write_output(self.sqli_output, lines)
        self.status_text.set(f"{learner} tested the unsafe bank login. Now compare it with the safe version.")
        self._refresh_all_views()

    def _sqli_safe(self) -> None:
        learner = self._current_learner()
        username = self.sqli_user.get().strip() or "admin"
        password = self.sqli_pass.get().strip() or "x"
        result = self.repo.safe_login(username, password)
        lines = [
            "[lesson] SQL Injection defense: placeholders keep the text as data.",
            f"[query] {result['sql']}",
        ]
        if result["rows"]:
            lines.append("[ok] login succeeded with a real account.")
            for row in result["rows"]:
                lines.append(f"  - {row['username']} | {row['full_name']} | {row['account_no']} | ${row['balance']:.2f} | {row['ssn']}")
        else:
            lines.append("[ok] injected text did not bypass the login.")
            lines.append("[next] explain why the query no longer treats the text like code.")
        self._write_output(self.sqli_output, lines)
        self.status_text.set(f"{learner} tested the safe bank login. The query stayed fixed.")
        self._refresh_all_views()

    def _xss_store_comment(self) -> None:
        author = self.xss_author.get().strip()
        content = self.xss_content.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Comment needed", "Enter some content first.")
            return
        self.repo.add_comment(author or self._current_learner(), content)
        self.xss_content.delete("1.0", "end")
        self._xss_render("unsafe")

    def _xss_render(self, mode: str) -> None:
        rows = self.repo.comments()
        display_lines = [
            "[lesson] XSS: the difference is whether the text is escaped before it reaches the page.",
            f"[mode] {mode.upper()}",
        ]
        self._clear_tree(self.xss_board)
        for row in rows:
            content = row["content"]
            if mode == "safe":
                preview = html.escape(content)
                note = "escaped"
            else:
                preview = content
                note = "raw"
                if "<script" in content.lower():
                    display_lines.append("[critical] in a browser this would execute as script.")
            self.xss_board.insert("", "end", values=(row["author"], preview, row["created_at"]))
            display_lines.append(f"  - {row['author']}: {preview} ({note})")
        self._write_output(self.xss_output, display_lines)
        self.status_text.set(f"XSS board rendered in {mode} mode. Compare the text with how a browser would treat it.")
        self._refresh_all_views()

    def _scrape_run(self) -> None:
        selector = self.scrape_selector.get().strip() or "article.item h3"
        attribute = self.scrape_attribute.get().strip() or "text"
        soup = BeautifulSoup(SCRAPE_TARGET_HTML, "html.parser")
        matches = soup.select(selector)
        values: list[str] = []
        if attribute == "text":
            for match in matches:
                text = match.get_text(" ", strip=True)
                if text:
                    values.append(text)
        else:
            for match in matches:
                value = match.get(attribute)
                if value:
                    values.append(str(value))
        self._clear_tree(self.scrape_results)
        for value in values:
            self.scrape_results.insert("", "end", values=(value,))
        lines = [
            "[lesson] Scraping: use a selector that matches only the data you want.",
            f"[selector] {selector}",
            f"[attribute] {attribute}",
            f"[matches] {len(matches)}",
        ]
        if values:
            lines.extend([f"  - {value}" for value in values])
        else:
            lines.append("[warning] nothing matched.")
        self._write_output(self.scrape_output, lines)
        self.status_text.set("Scraping demo complete. Explain why the selector and attribute matter.")
        self._refresh_all_views()

    def _sqlmap_scan(self) -> None:
        target = self.sqlmap_target.get().strip()
        command = self.sqlmap_command.get().strip()
        lines = self.repo.sqlmap_scan(target, command)
        self._write_output(self.sqlmap_output, lines)
        self._write_output(self.sqlmap_evidence, lines)
        self.status_text.set("SQLMap simulation complete. Read the scan evidence before answering.")
        self._refresh_all_views()

    def _refresh_database_view(self) -> None:
        table = self.db_table.get().strip() or "customers"
        search = self.db_search.get().strip().lower()
        data_map = self.repo.database_tables()
        rows = data_map.get(table, [])
        if search:
            rows = [row for row in rows if search in " ".join(str(value).lower() for value in row.values())]
        self.db_status.configure(text=f"Showing {len(rows)} row(s) from {table}.")
        self._clear_tree(self.db_tree)
        if not rows:
            self.db_tree["columns"] = ("value",)
            self.db_tree.heading("value", text="Value")
            self.db_tree.column("value", width=900, anchor="w")
            self.db_tree.insert("", "end", values=("No records matched your search.",))
            return

        columns = tuple(rows[0].keys())
        self.db_tree["columns"] = columns
        for column in columns:
            self.db_tree.heading(column, text=column.replace("_", " ").title())
            self.db_tree.column(column, width=160, anchor="w")
        for row in rows:
            self.db_tree.insert("", "end", values=tuple(row[column] for column in columns))

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def _refresh_all_views(self) -> None:
        learner = self._current_learner()
        progress = self.repo.lesson_progress(learner)
        attempts = self.repo.recent_attempts(learner)
        total_attempts = sum(item["attempts"] for item in progress)
        passed = sum(1 for item in progress if item["passed"])
        completion = round((passed / len(progress)) * 100) if progress else 0

        self.status_text.set(f"Learner: {learner} | Completion: {completion}% | Passed: {passed}/{len(progress)} | Attempts: {total_attempts}")
        if hasattr(self, "overview_text"):
            self.overview_text.configure(text=f"Learner: {learner}\nCompletion: {completion}%\nLessons passed: {passed}/{len(progress)}\nTotal attempts: {total_attempts}")
        self.progress_summary.configure(text=f"Learner: {learner}\nCompletion: {completion}%\nLessons passed: {passed}/{len(progress)}\nTotal attempts: {total_attempts}")

        self._clear_tree(self.progress_table)
        for item in progress:
            self.progress_table.insert("", "end", values=(item["title"], item["attempts"], item["best_score"], "Yes" if item["passed"] else "No"))

        self._clear_tree(self.history_table)
        for attempt in attempts:
            self.history_table.insert("", "end", values=(attempt["lesson_key"], attempt["score"], "Yes" if attempt["passed"] else "No", attempt["created_at"]))

        self._clear_tree(self.sqli_db)
        for row in self.repo.customers():
            self.sqli_db.insert("", "end", values=(row["username"], row["full_name"], row["account_no"], f"${row['balance']:.2f}", row["ssn"]))

        self._clear_tree(self.xss_board)
        for row in self.repo.comments():
            self.xss_board.insert("", "end", values=(row["author"], row["content"], row["created_at"]))

        self._refresh_database_view()


def main() -> int:
    app = TrainingApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
