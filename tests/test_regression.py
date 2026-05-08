from __future__ import annotations

import app as app_module
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "regression_lab.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db)
    monkeypatch.setattr(app_module, "_db_ready", False)

    app_module.init_db()
    app_module._db_ready = True
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as flask_client:
        yield flask_client


def test_core_pages_are_available(client):
    for route in ["/", "/sqli", "/xss", "/scraping", "/sqlmap", "/terminal", "/admin"]:
        response = client.get(route)
        assert response.status_code == 200


def test_sqli_unsafe_differs_from_safe(client):
    payload = {"username": "admin' OR '1'='1", "password": "x"}

    unsafe = client.post("/api/sqli/unsafe-login", json=payload)
    safe = client.post("/api/sqli/safe-login", json=payload)

    unsafe_data = unsafe.get_json()
    safe_data = safe.get_json()

    assert unsafe.status_code == 200
    assert safe.status_code == 200
    assert len(unsafe_data["matched_users"]) >= 1
    assert len(safe_data["matched_users"]) == 0


def test_xss_safe_render_escapes_script_text(client):
    post_resp = client.post(
        "/api/xss/post",
        json={"author": "tester", "content": "<script>alert(1)</script>"},
    )
    safe_resp = client.get("/api/xss/render?mode=safe")
    unsafe_resp = client.get("/api/xss/render?mode=unsafe")

    safe_data = safe_resp.get_json()
    unsafe_data = unsafe_resp.get_json()

    assert post_resp.status_code == 200

    safe_blob = "\n".join(item["rendered"] for item in safe_data["items"])
    unsafe_blob = "\n".join(item["rendered"] for item in unsafe_data["items"])

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in safe_blob
    assert "<script>alert(1)</script>" in unsafe_blob


def test_scraping_returns_expected_skus(client):
    response = client.post(
        "/api/scrape/run",
        json={"selector": "article.item", "attribute": "data-sku"},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] == 4
    assert data["results"] == ["BK-101", "EL-220", "LAB-77", "ST-18"]


def test_sqlmap_simulator_reports_findings_for_vulnerable_pattern(client):
    response = client.post(
        "/api/sqlmap/simulate",
        json={
            "command": "sqlmap -u http://127.0.0.1:5000/api/sqli/unsafe-login?username=t&password=t -p username --batch"
        },
    )
    data = response.get_json()
    blob = "\n".join(data["lines"]).lower()

    assert response.status_code == 200
    assert "critical" in blob
    assert "sqlite" in blob


def test_challenge_submission_and_progress(client):
    submit = client.post(
        "/api/challenge/submit",
        json={
            "lesson_slug": "sqli",
            "learner_name": "Regression Tester",
            "answer": "Parameterized queries keep user input as data. Placeholders prevent input from changing query logic.",
        },
    )
    progress = client.get("/api/challenge/progress")

    submit_data = submit.get_json()
    progress_data = progress.get_json()

    assert submit.status_code == 200
    assert submit_data["score"] >= 60
    assert submit_data["passed"] is True
    assert progress.status_code == 200
    assert any(item["slug"] == "sqli" for item in progress_data["lessons"])


def test_terminal_api_executes_and_logs_commands(client):
    run_cmd = client.post(
        "/api/terminal/execute",
        json={"tool": "db", "command": "tables"},
    )
    rows = client.get("/api/admin/rows?table=activity_log&sort_by=id&sort_dir=desc&per_page=10&page=1")

    run_data = run_cmd.get_json()
    rows_data = rows.get_json()

    assert run_cmd.status_code == 200
    assert any("users" in line for line in run_data["lines"])
    assert rows.status_code == 200
    assert any(row.get("command") == "tables" for row in rows_data["rows"])


def test_admin_rows_supports_search_and_sort(client):
    response = client.get(
        "/api/admin/rows?table=users&search=admin&sort_by=username&sort_dir=asc&per_page=5&page=1"
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["table"] == "users"
    assert data["total"] >= 1
    assert any("admin" in row["username"] for row in data["rows"])


def test_learner_registration_and_persistence(client):
    """Test that learner registration creates persistent identity and can be retrieved."""
    # Register a new learner
    reg_resp = client.post(
        "/api/learner/register",
        json={"learner_name": "Test Learner Alpha"},
    )
    reg_data = reg_resp.get_json()

    assert reg_resp.status_code == 200
    assert reg_data["ok"] is True
    assert "learner_key" in reg_data
    assert reg_data["display_name"] == "Test Learner Alpha"
    assert "is_returning" in reg_data

    learner_key = reg_data["learner_key"]

    # Verify learner can be retrieved
    progress_resp = client.get(f"/api/learner/{learner_key}/progress")
    progress_data = progress_resp.get_json()

    assert progress_resp.status_code == 200
    assert progress_data["ok"] is True
    assert progress_data["learner_key"] == learner_key
    assert progress_data["display_name"] == "Test Learner Alpha"


def test_learner_specific_progress_tracking(client):
    """Test that challenges submitted with learner_key are tracked per learner."""
    # Register two learners
    learner1_reg = client.post(
        "/api/learner/register",
        json={"learner_name": "Learner One"},
    ).get_json()
    learner2_reg = client.post(
        "/api/learner/register",
        json={"learner_name": "Learner Two"},
    ).get_json()

    key1 = learner1_reg["learner_key"]
    key2 = learner2_reg["learner_key"]

    # Submit challenges for learner 1
    client.post(
        "/api/challenge/submit",
        json={
            "lesson_slug": "sqli",
            "learner_name": "Learner One",
            "learner_key": key1,
            "answer": "SQL injection vulnerability parameterized statements vulnerable attack injection query prepared statement",
        },
    )

    # Submit challenges for learner 2
    client.post(
        "/api/challenge/submit",
        json={
            "lesson_slug": "xss",
            "learner_name": "Learner Two",
            "learner_key": key2,
            "answer": "Cross-site scripting input sanitization escaping encoding user-supplied HTML execute browser vulnerable XSS",
        },
    )

    # Check learner 1's progress (should show sqli attempt, not xss)
    progress1 = client.get(f"/api/learner/{key1}/progress").get_json()
    assert progress1["ok"] is True
    sqli_lesson1 = next((l for l in progress1["lessons"] if l["slug"] == "sqli"), None)
    xss_lesson1 = next((l for l in progress1["lessons"] if l["slug"] == "xss"), None)

    assert sqli_lesson1 is not None
    assert sqli_lesson1["attempts"] == 1
    assert xss_lesson1 is not None
    assert xss_lesson1["attempts"] == 0

    # Check learner 2's progress (should show xss attempt, not sqli)
    progress2 = client.get(f"/api/learner/{key2}/progress").get_json()
    assert progress2["ok"] is True
    sqli_lesson2 = next((l for l in progress2["lessons"] if l["slug"] == "sqli"), None)
    xss_lesson2 = next((l for l in progress2["lessons"] if l["slug"] == "xss"), None)

    assert sqli_lesson2 is not None
    assert sqli_lesson2["attempts"] == 0
    assert xss_lesson2 is not None
    assert xss_lesson2["attempts"] == 1


def test_learner_submission_history_visible_in_progress(client):
    """Test that submission history is returned in learner progress."""
    # Register learner
    learner_reg = client.post(
        "/api/learner/register",
        json={"learner_name": "History Test"},
    ).get_json()
    learner_key = learner_reg["learner_key"]

    # Submit multiple challenges
    for i in range(2):
        client.post(
            "/api/challenge/submit",
            json={
                "lesson_slug": "sqli",
                "learner_name": "History Test",
                "learner_key": learner_key,
                "answer": "SQL injection vulnerability parameterized statements vulnerable attack injection query prepared statement",
            },
        )

    # Get learner progress
    progress = client.get(f"/api/learner/{learner_key}/progress").get_json()

    assert progress["ok"] is True
    assert "submission_history" in progress
    assert len(progress["submission_history"]) >= 2
    assert all(sub["lesson_slug"] == "sqli" for sub in progress["submission_history"])