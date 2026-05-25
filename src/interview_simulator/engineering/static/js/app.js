/**
 * Interview Simulator UI — talks to FastAPI /interview/* on same origin by default.
 */

const $ = (id) => document.getElementById(id);

const state = {
  sessionId: null,
  finalized: false,
  roundHistory: [],
  /** Mirrors GET /interview/status context — used for labels before each submit. */
  sessionContext: { main_round_index: 0, follow_ups_in_round: 0 },
};

const SAMPLE = {
  job_description: `岗位职责：
- 负责支付核心链路的后端开发与稳定性保障
- 设计高并发、高可用的微服务架构

技术要求：Python / Go、PostgreSQL、Redis、Kafka、Kubernetes`,
  resume: `张三 · 5年后端
- 主导支付清结算服务重构，QPS 从 2k 提升至 15k
- 熟悉 FastAPI、分布式事务（Outbox）、可观测性（Prometheus）
- 有团队 Code Review 与 on-call 经验`,
  interview_dimension: "distributed systems",
};

function apiBase() {
  const raw = $("apiBase").value.trim();
  return raw ? raw.replace(/\/$/, "") : "";
}

function showLoading(text = "正在调用 AI，请稍候…") {
  $("loadingText").textContent = text;
  $("loadingOverlay").classList.remove("hidden");
}

function hideLoading() {
  $("loadingOverlay").classList.add("hidden");
}

function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast${type === "error" ? " error" : ""}`;
  el.textContent = msg;
  $("toastContainer").appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

async function api(path, options = {}) {
  const url = `${apiBase()}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  let body = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    body = await res.json();
  } else {
    body = await res.text();
  }
  if (!res.ok) {
    const detail =
      typeof body === "object" && body?.detail
        ? typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail)
        : String(body);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return body;
}

async function checkHealth() {
  const dot = $("healthDot");
  try {
    const data = await api("/healthz");
    dot.className = "health-dot ok";
    dot.title = `服务正常 · backend: ${data.backend || "?"}`;
  } catch {
    dot.className = "health-dot err";
    dot.title = "无法连接 API";
  }
}

function renderScores(scores) {
  if (!scores) return "";
  const dims = [
    ["技术深度", scores.technical_depth],
    ["表达清晰", scores.clarity],
    ["相关性", scores.relevance],
  ];
  return dims
    .map(
      ([label, val]) => `
    <div class="score-item">
      <div class="val">${val}<span class="score-max">/5</span></div>
      <div class="dim">${label}</div>
    </div>`
    )
    .join("");
}

function formatRoundLabel(mainRoundIndex, followUpsInRound) {
  const round = (mainRoundIndex ?? 0) + 1;
  const fu = followUpsInRound ?? 0;
  if (fu > 0) {
    return `第 ${round} 轮追问（${fu}）`;
  }
  return `第 ${round} 轮主问`;
}

function syncSessionContext(context) {
  if (!context) return;
  state.sessionContext = {
    main_round_index: context.main_round_index ?? 0,
    follow_ups_in_round: context.follow_ups_in_round ?? 0,
  };
}

function updateTimeline(entry) {
  state.roundHistory.push(entry);
  const ul = $("timeline");
  ul.innerHTML = state.roundHistory
    .map((r) => {
      const suffix =
        r.outcome && r.outcome !== r.roundLabel ? ` · ${r.outcome}` : "";
      return `
    <li class="done">
      <div class="t-title">${escapeHtml(r.roundLabel)}${escapeHtml(suffix)}</div>
      <div class="t-scores">${r.summary}</div>
    </li>`;
    })
    .join("");
}

function setInterviewVisible(active) {
  $("emptyState").classList.toggle("hidden", active);
  $("interviewActive").classList.toggle("hidden", !active);
  $("setupPanel").classList.toggle("disabled", active && !state.finalized);
}

function updateStateBadge(apiState, context) {
  $("stateBadge").textContent = apiState || "—";
  syncSessionContext(context);
  const c = state.sessionContext;
  $("roundLabel").textContent = formatRoundLabel(
    c.main_round_index,
    c.follow_ups_in_round
  );
}

function renderReport(data) {
  const box = $("reportContent");
  const pending = $("reportPending");
  if (data.report_pending && !data.overall_assessment) {
    pending.classList.remove("hidden");
  } else {
    pending.classList.add("hidden");
  }

  const strengths = (data.strengths || [])
    .map((s) => `<li>${escapeHtml(s)}</li>`)
    .join("");
  const tips = (data.improvement_suggestions || [])
    .map((s) => `<li>${escapeHtml(s)}</li>`)
    .join("");
  const topics = (data.recommended_study_topics || [])
    .map((s) => `<li>${escapeHtml(s)}</li>`)
    .join("");

  box.innerHTML = `
    <p><strong>来源：</strong>${data.report_source || "—"}</p>
    <p>${escapeHtml(data.closing_summary || "")}</p>
    ${
      data.overall_assessment
        ? `<h4>总体评价</h4><p>${escapeHtml(data.overall_assessment)}</p>`
        : ""
    }
    ${strengths ? `<h4>优势</h4><ul>${strengths}</ul>` : ""}
    ${tips ? `<h4>改进建议</h4><ul>${tips}</ul>` : ""}
    ${topics ? `<h4>推荐学习</h4><ul>${topics}</ul>` : ""}
  `;
  $("reportBlock").classList.remove("hidden");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function loadReport() {
  if (!state.sessionId) return;
  showLoading("正在生成报告…");
  try {
    const data = await api(`/interview/report/${state.sessionId}`);
    renderReport(data);
    toast("报告已加载");
  } catch (e) {
    if (e.message.includes("409") || e.message.includes("not finalized")) {
      toast("面试尚未结束", "error");
    } else {
      toast(e.message, "error");
    }
  } finally {
    hideLoading();
  }
}

async function refreshStatus() {
  if (!state.sessionId) return;
  try {
    const data = await api(`/interview/status/${state.sessionId}`);
    updateStateBadge(data.state, data.context);
    if (data.current_question) {
      $("currentQuestion").textContent = data.current_question;
    }
    if (data.report_ready) {
      await loadReport();
    }
  } catch (e) {
    toast(e.message, "error");
  }
}

$("fillSample").addEventListener("click", () => {
  $("jobDescription").value = SAMPLE.job_description;
  $("resume").value = SAMPLE.resume;
  $("interviewDimension").value = SAMPLE.interview_dimension;
  toast("已填入示例 JD 与简历");
});

$("startForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  showLoading("正在生成首题（单次 AI 调用，约 10–60 秒；智谱繁忙时请稍候）…");
  $("startBtn").disabled = true;

  const payload = {
    job_description: $("jobDescription").value.trim(),
    resume: $("resume").value.trim(),
    expected_depth: $("expectedDepth").value,
    interview_language: $("interviewLanguage").value,
    prompt_strategy: $("promptStrategy").value,
    evaluation_policy: {
      max_main_questions: Number($("maxMainQuestions").value) || 3,
      max_follow_ups_per_round: Number($("maxFollowUps").value) || 1,
    },
  };
  const dim = $("interviewDimension").value.trim();
  if (dim) {
    payload.interview_dimension = dim;
  }

  try {
    const data = await api("/interview/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.sessionId = data.session_id;
    state.finalized = false;
    state.roundHistory = [];
    state.sessionContext = { main_round_index: 0, follow_ups_in_round: 0 };

    $("currentQuestion").textContent = data.current_question;
    $("answer").value = "";
    $("lastFeedback").classList.add("hidden");
    $("reportBlock").classList.add("hidden");
    $("timeline").innerHTML = "";

    updateStateBadge(data.state, state.sessionContext);
    setInterviewVisible(true);
    toast("面试已开始");
    $("answer").focus();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    hideLoading();
    $("startBtn").disabled = false;
  }
});

$("askForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!state.sessionId) {
    toast("请先开始面试", "error");
    return;
  }
  if (state.finalized) {
    toast("面试已结束", "error");
    return;
  }

  const answer = $("answer").value.trim();
  if (!answer) return;

  showLoading("正在评分并准备下一题（出题约 10–60 秒）…");
  $("submitBtn").disabled = true;

  const atSubmit = { ...state.sessionContext };

  try {
    const data = await api("/interview/ask", {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId, answer }),
    });

    if (data.warning && !data.scores) {
      $("scoreGrid").innerHTML = "";
      $("evalReasoning").textContent = data.warning;
      $("responseMessage").textContent = data.message || "";
      $("lastFeedback").classList.remove("hidden");
      toast(data.warning, "error");
    } else if (data.scores) {
      $("scoreGrid").innerHTML = renderScores(data.scores);
      $("evalReasoning").textContent = data.evaluation_reasoning
        ? `评语：${data.evaluation_reasoning}`
        : "";
      $("responseMessage").textContent = data.message || "";
      $("lastFeedback").classList.remove("hidden");

      const weighted =
        0.3 * data.scores.technical_depth +
        0.2 * data.scores.clarity +
        0.5 * data.scores.relevance;
      updateTimeline({
        roundLabel: formatRoundLabel(
          atSubmit.main_round_index,
          atSubmit.follow_ups_in_round
        ),
        outcome: data.finalized ? "面试结束" : null,
        summary: `技术 ${data.scores.technical_depth}/5 · 清晰 ${data.scores.clarity}/5 · 相关 ${data.scores.relevance}/5（加权 ${weighted.toFixed(2)}/5）`,
      });
    }

    state.finalized = data.finalized;
    if (!data.finalized) {
      await refreshStatus();
    } else {
      updateStateBadge(data.state, state.sessionContext);
    }

    if (data.finalized) {
      $("currentQuestion").textContent = "面试已结束，请查看右侧报告。";
      $("answer").disabled = true;
      $("submitBtn").disabled = true;
      $("setupPanel").classList.remove("disabled");
      toast("面试结束");
      await loadReport();
    } else if (data.current_question) {
      $("currentQuestion").textContent = data.current_question;
      if (data.scores) {
        $("answer").value = "";
      }
      $("answer").focus();
      if (!data.warning) {
        toast(data.message || "请继续作答");
      }
    }
  } catch (e) {
    toast(e.message, "error");
  } finally {
    hideLoading();
    if (!state.finalized) $("submitBtn").disabled = false;
  }
});

$("copySessionId").addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    await navigator.clipboard.writeText(state.sessionId);
    toast("已复制 session_id");
  } catch {
    toast(state.sessionId);
  }
});

$("refreshStatus").addEventListener("click", () => refreshStatus());
$("reloadReport").addEventListener("click", () => loadReport());

checkHealth();
setInterval(checkHealth, 30000);
