import os
import html
import re

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')


TUTORIAL_STEPS = [
    {
        'id': 'intro',
        'title': 'Welcome',
        'subtitle': 'How this tutorial works',
    },
    {
        'id': 'xss',
        'title': 'XSS',
        'subtitle': 'What it is, why it executes, and how to stop it',
    },
    {
        'id': 'sqli',
        'title': 'SQL Injection',
        'subtitle': 'How query structure gets hijacked by user input',
    },
    {
        'id': 'scraping',
        'title': 'Web Scraping',
        'subtitle': 'Why exposed data is still risky and how to reduce abuse',
    },
    {
        'id': 'wrapup',
        'title': 'Wrap-up',
        'subtitle': 'Key takeaways and what to do next',
    },
]


def _get_step_index(step_id: str) -> int:
    for index, step in enumerate(TUTORIAL_STEPS):
        if step['id'] == step_id:
            return index
    return -1


def _get_tutorial_state() -> dict:
    visited = set(session.get('tutorial_visited', []))
    total = len(TUTORIAL_STEPS)
    progress_count = len(visited.intersection({s['id'] for s in TUTORIAL_STEPS}))
    progress_percent = int((progress_count / total) * 100) if total else 0
    return {
        'visited': visited,
        'progress_count': progress_count,
        'total_steps': total,
        'progress_percent': progress_percent,
    }


def _mark_step_visited(step_id: str) -> None:
    visited = set(session.get('tutorial_visited', []))
    visited.add(step_id)
    session['tutorial_visited'] = sorted(visited)


def _tutorial_xss_context() -> dict:
    payload = ''
    sink = 'innerHTML'
    analysis = None

    if request.method == 'POST':
        payload = request.form.get('payload', '')
        sink = request.form.get('sink', 'innerHTML')
        lower_payload = payload.lower()

        indicators = [
            ('<script', 'Contains a script tag.'),
            ('onerror=', 'Contains an inline event handler.'),
            ('onload=', 'Contains an inline event handler.'),
            ('javascript:', 'Contains a javascript: URL.'),
            ('document.cookie', 'Attempts to access cookies.'),
            ('<img', 'Injects an HTML element.'),
            ('<svg', 'Injects an SVG element.'),
        ]

        hits = [message for token, message in indicators if token in lower_payload]
        risk_score = 10
        risk_score += 20 if sink == 'innerHTML' else 5
        risk_score += min(len(hits) * 15, 60)

        if risk_score >= 70:
            risk_level = 'High'
        elif risk_score >= 40:
            risk_level = 'Medium'
        else:
            risk_level = 'Low'

        analysis = {
            'hits': hits,
            'risk_level': risk_level,
            'unsafe_output': f"<div class='comment'>{payload}</div>",
            'safe_output': f"<div class='comment'>{html.escape(payload)}</div>",
            'browser_flow': [
                'Server places user input into HTML response.',
                'Browser parses tags/attributes, not just text.',
                'If JavaScript is present in executable context, it runs.',
                'Attacker code executes with the victim\'s session privileges.',
            ],
            'why_it_works': 'Browsers trust page markup by default, and unsafe sinks treat input as code rather than plain text.',
        }

    return {
        'payload': payload,
        'sink': sink,
        'analysis': analysis,
    }


def _tutorial_sqli_context() -> dict:
    username = ''
    password = ''
    analysis = None

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        vulnerable_query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}';"
        safe_query = "SELECT * FROM users WHERE username = ? AND password = ?;"

        combined = f"{username} {password}"
        combined_lower = combined.lower()
        signal_rules = [
            (r"\bor\b\s*['\"]?\d+['\"]?\s*=\s*['\"]?\d+", 'Boolean logic was injected (tautology pattern).'),
            (r"--", 'SQL comment marker detected, which can ignore the rest of a query.'),
            (r"\bunion\b", 'UNION keyword detected, often used to extract additional data.'),
            (r";", 'Statement separator detected, which can chain extra commands.'),
            (r"\bselect\b", 'Unexpected SELECT keyword present in user input.'),
        ]

        detected_signals = []
        for pattern, message in signal_rules:
            if re.search(pattern, combined_lower):
                detected_signals.append(message)

        valid_credentials = (username == 'admin' and password == 'password')
        injection_markers = ["' or '1'='1", '" or "1"="1', '--']
        vulnerable_grants_access = valid_credentials or any(
            marker in combined_lower for marker in injection_markers
        )

        analysis = {
            'vulnerable_query': vulnerable_query,
            'safe_query': safe_query,
            'detected_signals': detected_signals,
            'vulnerable_result': 'Access granted' if vulnerable_grants_access else 'Access denied',
            'safe_result': 'Access granted' if valid_credentials else 'Access denied',
            'how_it_works': [
                'App concatenates raw user input into SQL text.',
                'Database parses final SQL string as executable query structure.',
                'Injected operators/comments change query logic.',
                'Authentication or data boundaries can be bypassed.',
            ],
            'why_it_works': 'Databases execute SQL grammar, and string concatenation lets attacker input become part of that grammar.',
        }

    return {
        'username': username,
        'password': password,
        'analysis': analysis,
    }


def _tutorial_scraping_context() -> dict:
    data_exposure = 'semi-public'
    request_volume = 300
    has_auth = False
    has_rate_limit = False
    has_bot_detection = False
    endpoint_granularity = 'fine-grained'
    analysis = None

    if request.method == 'POST':
        data_exposure = request.form.get('data_exposure', 'semi-public')
        request_volume = int(request.form.get('request_volume', '300') or '300')
        has_auth = request.form.get('has_auth') == 'on'
        has_rate_limit = request.form.get('has_rate_limit') == 'on'
        has_bot_detection = request.form.get('has_bot_detection') == 'on'
        endpoint_granularity = request.form.get('endpoint_granularity', 'fine-grained')

        exposure_points = {
            'public': 10,
            'semi-public': 25,
            'sensitive': 45,
        }
        volume_points = 8
        if request_volume > 1000:
            volume_points = 25
        elif request_volume > 500:
            volume_points = 18
        elif request_volume > 250:
            volume_points = 12

        granularity_points = 8 if endpoint_granularity == 'fine-grained' else 2
        control_reduction = 0
        if has_auth:
            control_reduction += 20
        if has_rate_limit:
            control_reduction += 15
        if has_bot_detection:
            control_reduction += 12

        risk_score = max(0, min(100, exposure_points[data_exposure] + volume_points + granularity_points - control_reduction))
        if risk_score >= 65:
            risk_level = 'High'
        elif risk_score >= 35:
            risk_level = 'Medium'
        else:
            risk_level = 'Low'

        estimated_records = request_volume * (4 if endpoint_granularity == 'fine-grained' else 1)
        analysis = {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'estimated_records': estimated_records,
            'why_it_works': [
                'Scrapers automate requests faster than humans.',
                'Predictable HTML/JSON structure makes parsing cheap.',
                'No auth/rate controls means low-cost bulk extraction.',
            ],
            'defensive_notes': [
                'Require auth for sensitive fields.',
                'Apply per-user and per-IP rate limiting.',
                'Track unusual request patterns and rotate keys/tokens.',
            ],
        }

    return {
        'data_exposure': data_exposure,
        'request_volume': request_volume,
        'has_auth': has_auth,
        'has_rate_limit': has_rate_limit,
        'has_bot_detection': has_bot_detection,
        'endpoint_granularity': endpoint_granularity,
        'analysis': analysis,
    }


def _tutorial_wrapup_context() -> dict:
    answers = {
        'q1': '',
        'q2': '',
        'q3': '',
    }
    result = None

    if request.method == 'POST':
        answers['q1'] = request.form.get('q1', '')
        answers['q2'] = request.form.get('q2', '')
        answers['q3'] = request.form.get('q3', '')

        key = {
            'q1': 'escape-output',
            'q2': 'parameterized',
            'q3': 'rate-limit',
        }
        score = sum(1 for q, correct in key.items() if answers[q] == correct)
        result = {
            'score': score,
            'total': 3,
            'message': 'Great job. You have a strong grasp of the concepts.' if score == 3 else 'Good progress. Review the incorrect answers and retest.',
        }

    return {
        'answers': answers,
        'result': result,
    }

@app.route('/')
def home():
    tutorial = _get_tutorial_state()
    return render_template('home.html', active_page='home', tutorial=tutorial)


@app.route('/tutorial')
def tutorial_index():
    tutorial = _get_tutorial_state()
    steps = []
    for step in TUTORIAL_STEPS:
        steps.append({
            **step,
            'url': url_for('tutorial_step', step_id=step['id']),
            'visited': step['id'] in tutorial['visited'],
        })
    return render_template('tutorial.html', active_page='tutorial', tutorial=tutorial, steps=steps)


@app.route('/tutorial/reset', methods=['POST'])
def tutorial_reset():
    session.pop('tutorial_visited', None)
    return redirect(url_for('tutorial_index'))


@app.route('/tutorial/<step_id>', methods=['GET', 'POST'])
def tutorial_step(step_id: str):
    step_index = _get_step_index(step_id)
    if step_index < 0:
        return redirect(url_for('tutorial_index'))

    _mark_step_visited(step_id)
    tutorial = _get_tutorial_state()

    prev_step = TUTORIAL_STEPS[step_index - 1]['id'] if step_index > 0 else None
    next_step = TUTORIAL_STEPS[step_index + 1]['id'] if step_index < len(TUTORIAL_STEPS) - 1 else None

    base_ctx = {
        'active_page': 'tutorial',
        'tutorial': tutorial,
        'step_id': step_id,
        'step_index': step_index,
        'step_title': TUTORIAL_STEPS[step_index]['title'],
        'step_subtitle': TUTORIAL_STEPS[step_index]['subtitle'],
        'prev_step_url': url_for('tutorial_step', step_id=prev_step) if prev_step else None,
        'next_step_url': url_for('tutorial_step', step_id=next_step) if next_step else None,
    }

    if step_id == 'intro':
        return render_template('tutorial_intro.html', **base_ctx)
    if step_id == 'xss':
        ctx = _tutorial_xss_context()
        return render_template('tutorial_xss.html', **base_ctx, **ctx)
    if step_id == 'sqli':
        ctx = _tutorial_sqli_context()
        return render_template('tutorial_sqli.html', **base_ctx, **ctx)
    if step_id == 'scraping':
        ctx = _tutorial_scraping_context()
        return render_template('tutorial_scraping.html', **base_ctx, **ctx)
    if step_id == 'wrapup':
        ctx = _tutorial_wrapup_context()
        return render_template('tutorial_wrapup.html', **base_ctx, **ctx)

    return redirect(url_for('tutorial_index'))

if __name__ == '__main__':
    app.run(debug=True)