const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const terminalControllers = new Map();

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || data.error || "Request failed.");
  }
  return data;
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function classifyTerminalLine(line) {
  const lowered = String(line).toLowerCase();
  if (lowered.includes("[error]")) return "error";
  if (lowered.includes("[warning]") || lowered.includes("[warn]")) return "warn";
  if (lowered.includes("[ok]") || lowered.includes("[critical]") || lowered.includes("[next]")) return "ok";
  return "normal";
}

function appendTerminalLine(outputEl, line, kind = "normal") {
  if (!outputEl) return;
  const row = document.createElement("p");
  row.className = `terminal-line ${kind}`;
  row.textContent = String(line);
  outputEl.appendChild(row);
  outputEl.scrollTop = outputEl.scrollHeight;
}

function renderXssBoardFromData(data) {
  const board = $("#xss-board");
  const status = $("#xss-mode-status");
  if (!board || !status || !data?.items) return;

  board.innerHTML = "";
  for (const item of data.items) {
    const row = document.createElement("div");
    row.className = "comment-row";
    row.innerHTML = item.rendered;
    board.appendChild(row);
  }

  status.textContent = `Current mode: ${String(data.mode).toUpperCase()} | ${data.message}`;
}

function createTerminalController(shell) {
  const output = $(".terminal-output", shell);
  const input = $(".terminal-input", shell);
  const prompt = $(".prompt", shell);
  const runButton = $(".terminal-run", shell);
  const clearButton = $(".terminal-clear", shell);

  let tool = shell.dataset.tool || "sqli";

  function setTool(nextTool) {
    tool = nextTool;
    shell.dataset.tool = nextTool;
    if (prompt) prompt.textContent = `${nextTool}$`;
    shell.dispatchEvent(new CustomEvent("toolChanged", { detail: { tool: nextTool } }));
  }

  function getTool() {
    return tool;
  }

  function clearOutput() {
    if (output) output.innerHTML = "";
  }

  async function execute(rawCommand) {
    const command = String(rawCommand || "").trim();
    if (!command) return;

    appendTerminalLine(output, `${tool}$ ${command}`, "prompt");

    if (command.toLowerCase() === "clear") {
      clearOutput();
      return;
    }

    try {
      const data = await fetchJSON("/api/terminal/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, command }),
      });

      if (data.action === "clear") {
        clearOutput();
      }

      if (data.next_tool) {
        setTool(data.next_tool);
      }

      const lines = Array.isArray(data.lines) ? data.lines : [];
      for (const line of lines) {
        appendTerminalLine(output, line, classifyTerminalLine(line));
      }

      if (data.summary) {
        appendTerminalLine(output, `[info] ${data.summary}`);
      }

      if (data.payload?.mode && data.payload?.items) {
        renderXssBoardFromData(data.payload);
      }
    } catch (error) {
      appendTerminalLine(output, `[error] ${error.message}`, "error");
    }
  }

  runButton?.addEventListener("click", () => {
    execute(input?.value || "");
    if (input) input.value = "";
    input?.focus();
  });

  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      execute(input.value);
      input.value = "";
    }
  });

  clearButton?.addEventListener("click", () => {
    clearOutput();
    appendTerminalLine(output, `[info] ${tool} profile ready. Type help to list commands.`);
  });

  setTool(tool);
  appendTerminalLine(output, `[info] ${tool} profile ready. Type help to list commands.`);

  return {
    execute,
    clearOutput,
    setTool,
    getTool,
  };
}

function initTerminalShells() {
  for (const shell of $$(".terminal-shell")) {
    const controller = createTerminalController(shell);
    if (shell.id) {
      terminalControllers.set(shell.id, controller);
    }
  }
}

function initCommandChips() {
  for (const button of $$(".chip[data-terminal-target]")) {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-terminal-target") || "";
      const command = button.getAttribute("data-command") || "";
      const controller = terminalControllers.get(targetId);
      if (!controller) return;
      controller.execute(command);
    });
  }
}

async function refreshXssBoard(mode) {
  const data = await fetchJSON(`/api/xss/render?mode=${encodeURIComponent(mode)}`);
  renderXssBoardFromData(data);
}

function initXssBoard() {
  const form = $("#xss-post-form");
  const status = $("#xss-mode-status");
  if (!form || !status) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      author: form.author.value,
      content: form.content.value,
    };

    try {
      await fetchJSON("/api/xss/post", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      form.content.value = "";
      await refreshXssBoard("unsafe");
    } catch (error) {
      status.textContent = `[error] ${error.message}`;
    }
  });

  for (const button of $$("[data-xss-mode]")) {
    button.addEventListener("click", () => {
      const mode = button.getAttribute("data-xss-mode") || "unsafe";
      refreshXssBoard(mode).catch((error) => {
        status.textContent = `[error] ${error.message}`;
      });
    });
  }

  refreshXssBoard("unsafe").catch((error) => {
    status.textContent = `[error] ${error.message}`;
  });
}

async function loadProgressPanel() {
  const cards = $("#progress-cards");
  const summary = $("#progress-summary");
  if (!cards || !summary) return;

  try {
    const data = await fetchJSON("/api/challenge/progress");
    cards.innerHTML = "";

    for (const lesson of data.lessons) {
      const card = document.createElement("article");
      card.className = `progress-card ${lesson.passed ? "pass" : "pending"}`;
      card.innerHTML = `
        <h3>${escapeHTML(lesson.title)}</h3>
        <p>${escapeHTML(lesson.objective)}</p>
        <p>Attempts: ${lesson.attempts}</p>
        <p>Best score: ${lesson.best_score}%</p>
        <p>Status: ${lesson.passed ? "Passed" : "Not passed yet"}</p>
      `;
      cards.appendChild(card);
    }

    summary.textContent = `Overall completion: ${data.completion_rate}%`;
  } catch (error) {
    summary.textContent = `[error] ${error.message}`;
  }
}

function initChallengeForms() {
  for (const form of $$(".challenge-form")) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const lessonSlug = form.getAttribute("data-lesson") || "";
      const resultNode = $(".challenge-result", form);

      const payload = {
        lesson_slug: lessonSlug,
        learner_name: form.learner_name.value,
        learner_key: sessionStorage.getItem("learner_key") || "",
        answer: form.answer.value,
      };

      try {
        const data = await fetchJSON("/api/challenge/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (resultNode) {
          resultNode.className = `challenge-result ${data.passed ? "pass" : "fail"}`;
          resultNode.textContent = `Score ${data.score}%: ${data.feedback}`;
        }

        loadProgressPanel().catch(() => {});
      } catch (error) {
        if (resultNode) {
          resultNode.className = "challenge-result fail";
          resultNode.textContent = error.message;
        }
      }
    });
  }
}

const adminState = {
  meta: null,
  page: 1,
  totalPages: 1,
};

function buildSelectOptions(selectEl, values) {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectEl.appendChild(option);
  }
}

function renderAdminStats(data) {
  const statsGrid = $("#admin-stats");
  if (!statsGrid) return;

  statsGrid.innerHTML = "";
  const entries = Object.entries(data.table_counts || {});
  for (const [table, total] of entries) {
    const card = document.createElement("article");
    card.className = "stat-card";
    card.innerHTML = `<h3>${escapeHTML(table)}</h3><p>${total}</p>`;
    statsGrid.appendChild(card);
  }

  const passRate = document.createElement("article");
  passRate.className = "stat-card";
  passRate.innerHTML = `<h3>challenge_pass_rate</h3><p>${data.challenge_pass_rate}%</p>`;
  statsGrid.appendChild(passRate);

  const flagged = document.createElement("article");
  flagged.className = "stat-card";
  flagged.innerHTML = `<h3>flagged_comments</h3><p>${data.flagged_comments}</p>`;
  statsGrid.appendChild(flagged);
}

function renderAdminTable(data) {
  const head = $("#admin-table-grid thead");
  const body = $("#admin-table-grid tbody");
  const meta = $("#admin-meta");
  const pageStatus = $("#admin-page-status");
  const prevBtn = $("#admin-prev");
  const nextBtn = $("#admin-next");

  if (!head || !body || !meta || !pageStatus || !prevBtn || !nextBtn) return;

  head.innerHTML = "";
  body.innerHTML = "";

  const headerRow = document.createElement("tr");
  for (const col of data.columns) {
    const th = document.createElement("th");
    th.textContent = col;
    headerRow.appendChild(th);
  }
  head.appendChild(headerRow);

  for (const row of data.rows) {
    const tr = document.createElement("tr");
    for (const col of data.columns) {
      const td = document.createElement("td");
      td.textContent = row[col] == null ? "" : String(row[col]);
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }

  if (!data.rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = data.columns.length;
    td.textContent = "No records matched your current filters.";
    tr.appendChild(td);
    body.appendChild(tr);
  }

  adminState.page = data.page;
  adminState.totalPages = data.total_pages;

  meta.textContent = `Showing ${data.rows.length} rows from ${data.table} (total ${data.total}).`;
  pageStatus.textContent = `Page ${data.page} of ${data.total_pages}`;
  prevBtn.disabled = data.page <= 1;
  nextBtn.disabled = data.page >= data.total_pages;
}

function updateAdminColumnSelectors() {
  const tableSelect = $("#admin-table");
  const sortBy = $("#admin-sort-by");
  const filterColumn = $("#admin-filter-column");
  if (!tableSelect || !sortBy || !filterColumn || !adminState.meta) return;

  const table = tableSelect.value;
  const columns = adminState.meta.tables[table]?.columns || [];
  buildSelectOptions(sortBy, columns);
  buildSelectOptions(filterColumn, ["", ...columns]);
}

async function loadAdminRows() {
  const table = $("#admin-table")?.value || "users";
  const search = $("#admin-search")?.value?.trim() || "";
  const filterColumn = $("#admin-filter-column")?.value || "";
  const filterValue = $("#admin-filter-value")?.value?.trim() || "";
  const sortBy = $("#admin-sort-by")?.value || "id";
  const sortDir = $("#admin-sort-dir")?.value || "asc";
  const perPage = $("#admin-per-page")?.value || "10";

  const params = new URLSearchParams({
    table,
    page: String(adminState.page),
    per_page: String(perPage),
    sort_by: sortBy,
    sort_dir: sortDir,
  });

  if (search) params.set("search", search);
  if (filterColumn && filterValue) {
    params.set("filter_column", filterColumn);
    params.set("filter_value", filterValue);
  }

  const data = await fetchJSON(`/api/admin/rows?${params.toString()}`);
  renderAdminTable(data);
}

async function initAdminDashboard() {
  const root = $("#admin-view");
  if (!root) return;

  try {
    const [meta, stats] = await Promise.all([fetchJSON("/api/admin/meta"), fetchJSON("/api/admin/stats")]);
    adminState.meta = meta;

    const tableNames = Object.keys(meta.tables || {});
    buildSelectOptions($("#admin-table"), tableNames);
    updateAdminColumnSelectors();
    renderAdminStats(stats);
    await loadAdminRows();
  } catch (error) {
    const metaLine = $("#admin-meta");
    if (metaLine) metaLine.textContent = `[error] ${error.message}`;
  }

  $("#admin-table")?.addEventListener("change", () => {
    adminState.page = 1;
    updateAdminColumnSelectors();
    loadAdminRows().catch(() => {});
  });

  $("#admin-apply")?.addEventListener("click", () => {
    adminState.page = 1;
    loadAdminRows().catch(() => {});
  });

  $("#admin-prev")?.addEventListener("click", () => {
    adminState.page = Math.max(1, adminState.page - 1);
    loadAdminRows().catch(() => {});
  });

  $("#admin-next")?.addEventListener("click", () => {
    adminState.page = Math.min(adminState.totalPages, adminState.page + 1);
    loadAdminRows().catch(() => {});
  });
}

function initGlobalTerminalSelect() {
  const select = $("#terminal-tool-select");
  const shell = $("#global-shell");
  if (!select || !shell) return;

  const controller = terminalControllers.get("global-shell");
  if (!controller) return;

  select.value = controller.getTool();

  select.addEventListener("change", () => {
    controller.setTool(select.value);
  });

  shell.addEventListener("toolChanged", (event) => {
    const tool = event.detail?.tool;
    if (!tool) return;
    select.value = tool;
  });
}

function initRevealAnimations() {
  const revealNodes = $$(".reveal");
  if (!revealNodes.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.14 }
  );

  revealNodes.forEach((node) => observer.observe(node));
}

window.addEventListener("DOMContentLoaded", () => {
  initRevealAnimations();
  initTerminalShells();
  initCommandChips();
  initXssBoard();
  initChallengeForms();
  initGlobalTerminalSelect();
  initAdminDashboard();
  loadProgressPanel().catch(() => {});
});
/* Legacy duplicate frontend code below is disabled.

function termWrite(el, lines) {
  if (!el) return;
  const normalized = Array.isArray(lines) ? lines : [String(lines)];
  normalized.forEach((line) => {
    const p = document.createElement("p");
    p.textContent = line;
    el.appendChild(p);
  });
  el.scrollTop = el.scrollHeight;
}

function termClear(el) {
  if (!el) return;
  el.innerHTML = "";
}

function appendQuestions(el, questions) {
  if (!el || !questions?.length) return;
  termWrite(el, ["Reflect:", ...questions.map((q, i) => `  ${i + 1}. ${q}`), ""]);
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || data.error || "Request failed");
  }
  return data;
}

async function loadUsersTable() {
  const tbody = $("#users-table tbody");
  if (!tbody) return;
  const users = await fetchJSON("/api/db/users");
  tbody.innerHTML = "";
  users.forEach((u) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${u.id}</td><td>${u.username}</td><td>${u.password}</td><td>${u.role}</td>`;
    tbody.appendChild(tr);
  });
}

function initSQLi() {
  const terminal = $("#sqli-terminal");
  const form = $("#sqli-form");
  const unsafeBtn = $("#run-unsafe");
  const safeBtn = $("#run-safe");
  const refreshBtn = $("#refresh-users");

  if (!form || !terminal) return;

  const run = async (url, modeLabel) => {
    const username = form.username.value;
    const password = form.password.value;
    termWrite(terminal, [`$ ${modeLabel}`, `username=${username}`, `password=${password}`]);

    try {
      const data = await fetchJSON(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      termWrite(terminal, [
        `query: ${data.query}`,
        data.bound_parameters ? `params: ${JSON.stringify(data.bound_parameters)}` : "",
        `matched users: ${data.matched_users.length}`,
        ...data.matched_users.map((u) => `  -> ${u.username} (${u.role})`),
        `note: ${data.message}`,
        "",
      ]);

      if (url.includes("unsafe")) {
        if (data.matched_users.length > 1) {
          appendQuestions(terminal, [
            "Which part of your input changed the WHERE condition's truth value?",
            "Why do multiple returned rows indicate logic manipulation?",
            "How would this result differ if input were treated only as data?",
          ]);
        } else if (data.matched_users.length === 1) {
          appendQuestions(terminal, [
            "Did you authenticate as a real user, or alter query logic?",
            "What evidence in the query text supports your conclusion?",
            "What alternate input could test logic bypass more clearly?",
          ]);
        } else {
          appendQuestions(terminal, [
            "Did your input close or alter the quoted SQL value correctly?",
            "Could a boolean expression help test whether logic can be forced true?",
            "What single change will you try next?",
          ]);
        }
      } else {
        appendQuestions(terminal, [
          "You reused the same input; why did safe mode behave differently?",
          "How do placeholders prevent your text from becoming SQL code?",
          "What security rule can you extract from this comparison?",
        ]);
      }
    } catch (err) {
      termWrite(terminal, [`[error] ${err.message}`, ""]);
      appendQuestions(terminal, [
        "What does the error suggest about quote balance or SQL syntax?",
        "How can you simplify your input to test one idea at a time?",
      ]);
    }
  };

  unsafeBtn?.addEventListener("click", () => run("/api/sqli/unsafe-login", "run vulnerable-login"));
  safeBtn?.addEventListener("click", () => run("/api/sqli/safe-login", "run safe-login"));
  refreshBtn?.addEventListener("click", () => loadUsersTable());

  termClear(terminal);
  termWrite(terminal, [
    "SQL Injection Terminal",
    "Goal: discover an input that changes vulnerable query logic.",
    "Start with a normal login attempt, then modify only username.",
    "Observe query text and matched row count after each run.",
    "",
  ]);
  appendQuestions(terminal, [
    "Which operator can combine two conditions in SQL (AND/OR)?",
    "What happens if one side of an OR condition is always true?",
    "How can you test that idea with minimal input changes?",
  ]);

  loadUsersTable().catch((err) => termWrite(terminal, [`[error] ${err.message}`]));
}

function initXSS() {
  const form = $("#xss-form");
  const board = $("#xss-board");
  const modeLabel = $("#xss-mode-label");
  const unsafeBtn = $("#render-unsafe");
  const safeBtn = $("#render-safe");

  if (!form || !board) return;

  const render = async (mode) => {
    const data = await fetchJSON(`/api/xss/render?mode=${mode}`);
    modeLabel.textContent = `Current mode: ${mode.toUpperCase()} | ${data.message}`;
    board.innerHTML = "";
    data.items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "comment";
      row.innerHTML = item.rendered;
      board.appendChild(row);
    });
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await fetchJSON("/api/xss/post", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: form.author.value,
          content: form.content.value,
        }),
      });
      form.content.value = "";
      await render("unsafe");
    } catch (err) {
      modeLabel.textContent = `[error] ${err.message}`;
    }
  });

  unsafeBtn?.addEventListener("click", () => render("unsafe"));
  safeBtn?.addEventListener("click", () => render("safe"));
  render("unsafe").catch((err) => {
    modeLabel.textContent = `[error] ${err.message}`;
  });
}

function initScraping() {
  const form = $("#scrape-form");
  const terminal = $("#scrape-terminal");
  if (!form || !terminal) return;

  termWrite(terminal, [
    "Scraper Terminal",
    "Goal: extract product names, then extract SKU values.",
    "Read the HTML block and identify repeating structure first.",
    "",
  ]);
  appendQuestions(terminal, [
    "Which element wraps each product card?",
    "Which child element holds only the title text?",
    "When should you request text vs an attribute value?",
  ]);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selector = form.selector.value;
    const attribute = form.attribute.value;

    termWrite(terminal, [`$ scrape --selector "${selector}" --attribute ${attribute}`]);

    try {
      const data = await fetchJSON("/api/scrape/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selector, attribute }),
      });
      termWrite(terminal, [
        `matches: ${data.count}`,
        ...data.results.map((r, i) => `[${i + 1}] ${r}`),
        `note: ${data.message}`,
        "",
      ]);

      if (data.count === 0) {
        appendQuestions(terminal, [
          "Did your selector match the exact tag and class names?",
          "Could spacing or nesting in your selector be too strict?",
          "What simpler selector can you test first?",
        ]);
      } else if (data.count > 3) {
        appendQuestions(terminal, [
          "You matched many elements. Which parent/child detail narrows this set?",
          "Can you include a class to target only product cards?",
          "What exact field are you trying to collect?",
        ]);
      } else {
        appendQuestions(terminal, [
          "Does this output contain only the field you intended?",
          "How would you adjust selector or attribute for the next field?",
          "What pattern could you reuse on a larger site?",
        ]);
      }
    } catch (err) {
      termWrite(terminal, [`[error] ${err.message}`, ""]);
      appendQuestions(terminal, [
        "Did you provide a valid CSS selector string?",
        "What is the smallest valid selector you can try next?",
      ]);
    }
  });
}

function initSQLMap() {
  const loadExample = $("#load-sqlmap-example");
  const runBtn = $("#run-sqlmap");
  const commandBox = $("#sqlmap-command");
  const terminal = $("#sqlmap-terminal");
  const summary = $("#sqlmap-summary");

  if (!commandBox || !terminal) return;

  const setExample = async () => {
    const data = await fetchJSON("/api/sqlmap/example");
    commandBox.value = data.command;
    summary.textContent = data.explanation;
  };

  loadExample?.addEventListener("click", () => {
    setExample().catch((err) => {
      summary.textContent = `[error] ${err.message}`;
    });
  });

  runBtn?.addEventListener("click", async () => {
    termWrite(terminal, [`$ ${commandBox.value}`]);
    try {
      const data = await fetchJSON("/api/sqlmap/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: commandBox.value }),
      });
      termWrite(terminal, [...data.lines, ""]);
      summary.textContent = data.summary;

      const hasFinding = data.lines.some((line) => line.toLowerCase().includes("[critical]"));
      if (hasFinding) {
        appendQuestions(terminal, [
          "Which specific parameter was reported as injectable?",
          "Which line gives you confidence this is not a false positive?",
          "What should a defender fix first in application code?",
        ]);
      } else {
        appendQuestions(terminal, [
          "Did your URL include a testable parameter value?",
          "Would selecting a specific parameter with -p improve focus?",
          "Which option would you change first and why?",
        ]);
      }
    } catch (err) {
      termWrite(terminal, [`[error] ${err.message}`, ""]);
      appendQuestions(terminal, [
        "Does your command begin with sqlmap and include a target URL?",
        "What is the minimum command you can run to validate syntax?",
      ]);
    }
  });

  termWrite(terminal, [
    "SQLMap Simulator Terminal",
    "Goal: build your own command from first principles.",
    "Include a target URL and think about which parameter to test.",
    "Output is educational and constrained to this local lab.",
    "",
  ]);
  appendQuestions(terminal, [
    "Which part of the URL likely contains user-controlled input?",
    "Why might targeting one parameter be useful before broad scanning?",
    "What flag helps reduce interactive prompts during practice?",
  ]);

  setExample().catch(() => {});
}

function initRevealAnimations() {
  const elements = document.querySelectorAll(".reveal");
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  elements.forEach((el) => observer.observe(el));
}

function initTerminalPopout() {
  const buttons = document.querySelectorAll("[data-terminal-target]");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-terminal-target");
      const terminal = targetId ? document.getElementById(targetId) : null;
      if (!terminal) return;

      const isOpen = terminal.classList.toggle("terminal-popout-open");

      if (isOpen) {
        // Move the terminal to <body> while popped out to avoid transformed-parent stacking bugs.
        const placeholder = document.createComment(`terminal-home:${targetId}`);
        terminal.parentNode?.insertBefore(placeholder, terminal);
        terminal.dataset.popoutPlaceholder = targetId;
        document.body.appendChild(terminal);
      } else {
        const placeholderId = terminal.dataset.popoutPlaceholder;
        if (placeholderId) {
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_COMMENT);
          let node = walker.nextNode();
          while (node) {
            if (node.nodeValue === `terminal-home:${placeholderId}`) {
              node.parentNode?.insertBefore(terminal, node);
              node.parentNode?.removeChild(node);
              break;
            }
            node = walker.nextNode();
          }
          delete terminal.dataset.popoutPlaceholder;
        }
      }

      button.textContent = isOpen ? "Return Terminal" : "Pop Out Terminal";
      document.body.classList.toggle("terminal-popout-active", isOpen);
    });
  });
}

window.addEventListener("DOMContentLoaded", () => {
  initRevealAnimations();
  initTerminalPopout();
  initSQLi();
  initXSS();
  initScraping();
  initSQLMap();
});
*/
