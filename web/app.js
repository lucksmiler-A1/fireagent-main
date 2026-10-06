const defaultBaseUrl = "http://127.0.0.1:8010";
const apiPrefix = "/api/v1";
const historyStorageKey = "fire_safety_web_history_records_v1";
const insightsCollapseStorageKey = "fire_safety_web_insights_collapsed_v1";
const agentConversationStorageKey = "fire_safety_web_agent_conversation_v2";
const agentSessionStorageKey = "fire_safety_web_agent_session_v1";
const maxHistoryCount = 50;
const maxAgentHistoryCount = 20;
const maxAgentInputLength = 600;
const agentThinkingSteps = [
  "正在规划回答路径",
  "正在调取法规与历史工具",
  "正在整理风险判断与建议",
];

const loadingFacts = [
  "厨房油锅起火不能泼水，应先关火并用锅盖隔绝空气。",
  "电动车电池不要在楼道或室内充电，避免夜间长时间无人看管。",
  "灭火器使用口诀：提、拔、握、压，对准火焰根部喷射。",
  "逃生时优先选择安全出口和疏散楼梯，不要乘坐电梯。",
  "浓烟环境要低姿前进，可用湿毛巾捂住口鼻减少吸入。",
  "插线板避免串联使用，大功率设备不要共用一个插排。",
  "消防通道必须保持畅通，严禁堆放杂物或上锁封堵。",
];

const baseUrlInput = document.getElementById("baseUrl");
const saveConfigButton = document.getElementById("saveConfig");
const configStatus = document.getElementById("configStatus");

const uploadForm = document.getElementById("uploadForm");
const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const sceneSelect = document.getElementById("sceneSelect");
const startAnalyzeButton = document.getElementById("startAnalyze");
const uploadStatus = document.getElementById("uploadStatus");
const progressWrap = document.getElementById("progressWrap");
const progressSteps = Array.from(document.querySelectorAll(".progress-step"));
const loadingFactsWrap = document.getElementById("loadingFacts");
const loadingFactText = document.getElementById("loadingFactText");

const openHistoryButton = document.getElementById("openHistory");
const refreshHistoryButton = document.getElementById("refreshHistory");
const rethinkAnalyzeButton = document.getElementById("rethinkAnalyze");
const clearRemoteHistoryButton = document.getElementById("clearRemoteHistory");
const clearLocalHistoryButton = document.getElementById("clearLocalHistory");
const historyCard = document.getElementById("historyCard");
const historyStatus = document.getElementById("historyStatus");
const historyList = document.getElementById("historyList");
const refreshInsightsButton = document.getElementById("refreshInsights");
const toggleInsightsButton = document.getElementById("toggleInsights");
const insightBody = document.getElementById("insightBody");
const insightStatus = document.getElementById("insightStatus");
const insightMetrics = document.getElementById("insightMetrics");
const insightAlerts = document.getElementById("insightAlerts");
const insightRecommendations = document.getElementById("insightRecommendations");
const hasInsightsUI = Boolean(
  refreshInsightsButton &&
    toggleInsightsButton &&
    insightBody &&
    insightStatus &&
    insightMetrics &&
    insightAlerts &&
    insightRecommendations
);

const agentForm = document.getElementById("agentForm");
const agentInput = document.getElementById("agentInput");
const agentSubmit = document.getElementById("agentSubmit");
const agentSceneSelect = document.getElementById("agentSceneSelect");
const sceneGuidePanel = document.getElementById("sceneGuidePanel");
const sceneGuideScene = document.getElementById("sceneGuideScene");
const sceneGuidePoem = document.getElementById("sceneGuidePoem");
const sceneGuideFocus = document.getElementById("sceneGuideFocus");
const sceneGuideList = document.getElementById("sceneGuideList");
const sceneGuideTips = document.getElementById("sceneGuideTips");
const agentStatus = document.getElementById("agentStatus");
const agentSubstatus = document.getElementById("agentSubstatus");
const agentLiveBadge = document.getElementById("agentLiveBadge");
const agentContextPanel = document.getElementById("agentContextPanel");
const agentContextMeta = document.getElementById("agentContextMeta");
const agentContextSummary = document.getElementById("agentContextSummary");
const agentUseCurrentRecord = document.getElementById("agentUseCurrentRecord");
const agentFollowupPrompts = Array.from(document.querySelectorAll(".agent-followup-prompt"));
const agentToolRail = document.getElementById("agentToolRail");
const agentCharCount = document.getElementById("agentCharCount");
const agentMessagesWrap = document.getElementById("agentMessages");
const clearAgentChatButton = document.getElementById("clearAgentChat");
const agentQuickPrompts = Array.from(document.querySelectorAll(".quick-prompt"));
const agentComposerShell = document.querySelector(".agent-composer-shell");
const agentSceneChangeKey = "fire_safety_web_agent_scene_notice_v1";

// Memory Inspector wiring (four-layer memory)
const memoryInspectorEl = document.getElementById("agentMemoryInspector");
const memoryInspectorStatus = document.getElementById("memoryInspectorStatus");
const refreshMemorySnapshotButton = document.getElementById("refreshMemorySnapshot");
const memoryCoreBadge = document.getElementById("memoryCoreBadge");
const memoryCoreRules = document.getElementById("memoryCoreRules");
const memoryTaskBadge = document.getElementById("memoryTaskBadge");
const memoryTaskDetail = document.getElementById("memoryTaskDetail");
const memoryShortBadge = document.getElementById("memoryShortBadge");
const memoryShortSummary = document.getElementById("memoryShortSummary");
const memoryShortMeta = document.getElementById("memoryShortMeta");
const memoryLongBadge = document.getElementById("memoryLongBadge");
const memoryLongMode = document.getElementById("memoryLongMode");
const memoryLongRecurring = document.getElementById("memoryLongRecurring");
const memoryLongSimilar = document.getElementById("memoryLongSimilar");
const memoryLongTasks = document.getElementById("memoryLongTasks");

// P1: recurrence alert bar + remediation task card
const recurrenceAlertEl = document.getElementById("recurrenceAlert");
const recurrenceAlertTitle = document.getElementById("recurrenceAlertTitle");
const recurrenceAlertBody = document.getElementById("recurrenceAlertBody");
const recurrenceAlertDismiss = document.getElementById("recurrenceAlertDismiss");
const memoryTasksList = document.getElementById("memoryTasksList");
const memoryTasksStatus = document.getElementById("memoryTasksStatus");
const refreshMemoryTasksButton = document.getElementById("refreshMemoryTasks");
const recurrenceDismissStorageKey = "fire_safety_web_recurrence_dismissed_v1";

// P2: Admin drawer (Core Memory CRUD + clear-all)
const adminDrawerBackdropEl = document.getElementById("adminDrawerBackdrop");
const adminDrawerEl = document.getElementById("adminDrawer");
const openAdminDrawerButton = document.getElementById("openAdminDrawer");
const closeAdminDrawerButton = document.getElementById("closeAdminDrawer");
const adminTokenInput = document.getElementById("adminTokenInput");
const saveAdminTokenButton = document.getElementById("saveAdminToken");
const clearAdminTokenButton = document.getElementById("clearAdminToken");
const adminTokenStatus = document.getElementById("adminTokenStatus");
const adminCoreScopeFilter = document.getElementById("adminCoreScopeFilter");
const refreshAdminCoreButton = document.getElementById("refreshAdminCore");
const adminCoreList = document.getElementById("adminCoreList");
const adminCoreNewScope = document.getElementById("adminCoreNewScope");
const adminCoreNewPriority = document.getElementById("adminCoreNewPriority");
const adminCoreNewText = document.getElementById("adminCoreNewText");
const adminCoreCreate = document.getElementById("adminCoreCreate");
const adminCoreStatus = document.getElementById("adminCoreStatus");
const adminClearAll = document.getElementById("adminClearAll");
const adminClearStatus = document.getElementById("adminClearStatus");
const adminTokenStorageKey = "fire_safety_web_admin_token_v1";

const resultEmpty = document.getElementById("resultEmpty");
const resultPanel = document.getElementById("resultPanel");
const resultImage = document.getElementById("resultImage");
const resultRisk = document.getElementById("resultRisk");
const resultSummary = document.getElementById("resultSummary");
const resultItems = document.getElementById("resultItems");
const resultCitations = document.getElementById("resultCitations");
const resultStage1 = document.getElementById("resultStage1");
const resultRaw = document.getElementById("resultRaw");
const resultDebug = document.getElementById("resultDebug");

let progressTimer = null;
let progressCurrent = -1;
let loadingFactTimer = null;
let loadingFactIndex = 0;
let remoteHistoryRecords = [];
let insightsCollapsed = false;
let agentConversation = [];
let agentPending = false;
let agentThinkingTimer = null;
let agentThinkingIndex = 0;
let agentTransitionRunning = false;
let currentAgentRecordContext = null;
let currentAgentSessionId = null;
let lastUploadedFile = null;
let lastUploadedScene = null;
// Memory Inspector state — track latest goal_version per session so we can
// detect resets and announce them in the chat as a system notice.
let lastMemoryGoalVersion = null;
let lastMemorySessionId = null;
let latestMemorySnapshot = null;

function loadInsightsCollapseState() {
  try {
    const raw = localStorage.getItem(insightsCollapseStorageKey);
    insightsCollapsed = raw === "1";
  } catch (_) {
    insightsCollapsed = false;
  }
}

function applyInsightsCollapsedState() {
  if (!hasInsightsUI) return;
  insightBody.classList.toggle("hidden", insightsCollapsed);
  toggleInsightsButton.textContent = insightsCollapsed ? "展开建议" : "折叠建议";
}

function toggleInsightsCollapsed() {
  insightsCollapsed = !insightsCollapsed;
  try {
    localStorage.setItem(insightsCollapseStorageKey, insightsCollapsed ? "1" : "0");
  } catch (_) {
    // noop
  }
  applyInsightsCollapsedState();
}

function loadConfig() {
  const saved = localStorage.getItem("baseUrl") || defaultBaseUrl;
  baseUrlInput.value = saved;
}

function applyPrimaryButtonStyles() {
  document.querySelectorAll(".btn.primary").forEach((button) => {
    button.style.backgroundColor = "#0a5b55";
    button.style.backgroundImage = "linear-gradient(135deg, #0f766e 0%, #0a5b55 100%)";
    button.style.color = "#ffffff";
    button.style.borderColor = "#0a5751";
  });
}

function updateSelectedFileName() {
  if (!fileName || !fileInput) return;
  const selected = fileInput.files && fileInput.files[0];
  fileName.textContent = selected ? selected.name : "未选择图片";
}

function ensureAnalyzeButtonText() {
  if (!startAnalyzeButton) return;
  const text = String(startAnalyzeButton.textContent || "").trim();
  if (!text) startAnalyzeButton.textContent = "开始识别";
  startAnalyzeButton.setAttribute("aria-label", "开始识别");
}

function mapSceneLabel(scene) {
  const key = String(scene || "").toLowerCase();
  const map = {
    campus: "校园",
    dormitory: "宿舍",
    residential: "居民区",
    office: "办公",
    warehouse: "仓储",
    industrial: "工业",
    construction: "工地",
  };
  return map[key] || key || "未选择";
}

function buildSceneSwitchNotice(scene) {
  const key = String(scene || "").toLowerCase();
  const label = mapSceneLabel(key);
  if (key === "construction") {
    return `场景已切换为：${label}。可直接询问临时用电、动火作业、吊装、高处作业、受限空间与PPE等生产安全问题。`;
  }
  if (key === "industrial") {
    return `场景已切换为：${label}。可直接询问电气设备风险、动火审批、吊装作业、设备维护与应急处置等生产安全问题。`;
  }
  return `场景已切换为：${label}`;
}

function renderSceneGuide(data) {
  if (!sceneGuidePanel) return;
  if (!data || !data.scene) {
    sceneGuidePanel.classList.add("hidden");
    return;
  }
  sceneGuidePanel.classList.remove("hidden");
  if (sceneGuideScene) sceneGuideScene.textContent = mapSceneLabel(data.scene);
  if (sceneGuidePoem) sceneGuidePoem.textContent = data.poem || "";
  if (sceneGuideFocus) {
    sceneGuideFocus.textContent = data.focus_area ? `重点区域：${data.focus_area}` : "";
  }

  if (sceneGuideList) {
    sceneGuideList.innerHTML = "";
    const items = Array.isArray(data.checklist) ? data.checklist : [];
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      sceneGuideList.appendChild(li);
    });
  }

  if (sceneGuideTips) {
    const tips = Array.isArray(data.tips) ? data.tips : [];
    sceneGuideTips.textContent = tips.length ? `提示：${tips.join("；")}` : "";
  }
}

async function fetchSceneGuide(scene) {
  if (!sceneGuidePanel) return;
  try {
    const resp = await fetch(buildApiUrl(`/scene-guides?scene=${encodeURIComponent(scene)}`));
    const text = await resp.text();
    let data = {};
    try {
      data = JSON.parse(text);
    } catch (_) {
      data = {};
    }
    if (!resp.ok) throw new Error(data.detail || text || `HTTP ${resp.status}`);
    renderSceneGuide(data);
  } catch (_) {
    renderSceneGuide({ scene, poem: "", focus_area: "", checklist: [], tips: [] });
  }
}

function saveConfig() {
  const value = (baseUrlInput.value || "").trim().replace(/\/$/, "");
  if (!value) {
    configStatus.textContent = "请输入有效的 BASE_URL";
    return;
  }
  localStorage.setItem("baseUrl", value);
  configStatus.textContent = "已保存";
  fetchRemoteHistory();
  fetchInsights(7);
}

function getBaseUrl() {
  return ((baseUrlInput.value || "").trim() || defaultBaseUrl).replace(/\/$/, "");
}

function buildApiUrl(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${getBaseUrl()}${apiPrefix}${normalized}`;
}

function normalizeImageUrl(url) {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${getBaseUrl()}${url}`;
}

function normalizeRiskKey(risk) {
  const raw = String(risk || "").trim().toLowerCase();
  if (!raw) return "warning";

  if (["safe", "low", "安全", "低"].includes(raw)) return "safe";
  if (["warning", "medium", "隐患", "中"].includes(raw)) return "warning";
  if (["danger", "high", "严重隐患", "高", "危险"].includes(raw)) return "danger";
  return "warning";
}

function mapRiskClass(risk) {
  return normalizeRiskKey(risk);
}

function riskText(risk) {
  const key = normalizeRiskKey(risk);
  if (key === "safe") return "安全";
  if (key === "danger") return "严重隐患";
  return "隐患";
}

function renderItems(items) {
  resultItems.innerHTML = "";
  if (!Array.isArray(items) || !items.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "没有结构化风险项，可查看下方原始输出。";
    resultItems.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "item";

    const title = document.createElement("div");
    title.className = "item-title";
    const risk = item.risk || "warning";
    title.textContent = `${item.type || "Unknown"} (${riskText(risk)})`;

    const desc = document.createElement("div");
    desc.textContent = item.desc || "";

    const suggest = document.createElement("div");
    suggest.className = "hint";
    suggest.textContent = item.suggest || "";

    card.appendChild(title);
    if (desc.textContent) card.appendChild(desc);
    if (suggest.textContent) card.appendChild(suggest);
    resultItems.appendChild(card);
  });
}

function renderCitations(citations) {
  resultCitations.innerHTML = "";
  if (!Array.isArray(citations) || !citations.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "未返回法规引用。";
    resultCitations.appendChild(empty);
    return;
  }

  citations.forEach((c) => {
    const card = document.createElement("div");
    card.className = "item";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = `${c.article || "-"} | ${c.source || "-"}`;

    const quote = document.createElement("div");
    quote.textContent = c.quote || "";

    card.appendChild(title);
    if (quote.textContent) card.appendChild(quote);
    resultCitations.appendChild(card);
  });
}

function renderResult(data) {
  resultEmpty.classList.add("hidden");
  resultPanel.classList.remove("hidden");

  const imageUrl = normalizeImageUrl(data.annotated_url || data.image_url || "");
  if (imageUrl) {
    resultImage.classList.remove("hidden");
    resultImage.src = imageUrl;
  } else {
    resultImage.classList.add("hidden");
    resultImage.removeAttribute("src");
  }

  const risk = data.overall_risk || "warning";
  resultRisk.className = `badge ${mapRiskClass(risk)}`;
  resultRisk.textContent = `风险等级: ${riskText(risk)}`;
  resultSummary.textContent = data.summary || "";

  renderItems(data.items || []);
  renderCitations(data.citations || []);

  resultRaw.textContent = data.raw_output || "";
  resultStage1.textContent = JSON.stringify(data.stage1_result || {}, null, 2);
  resultDebug.textContent = JSON.stringify(data._debug || {}, null, 2);
}

function buildCurrentRecordContext(data, scene) {
  const items = Array.isArray(data.items) ? data.items : [];
  return {
    record_id: String(data.record_id || ""),
    scene: String(scene || data.scene || ""),
    overall_risk: String(data.overall_risk || ""),
    summary: String(data.summary || ""),
    citations: Array.isArray(data.citations) ? data.citations.slice(0, 3) : [],
    items: items.slice(0, 6).map((item) => ({
      type: String(item.type || ""),
      risk: String(item.risk || ""),
      desc: String(item.desc || ""),
      suggest: String(item.suggest || ""),
    })),
  };
}

function renderAgentRecordContext() {
  if (!agentContextPanel || !agentContextMeta || !agentContextSummary) return;

  if (!currentAgentRecordContext || !currentAgentRecordContext.record_id) {
    agentContextPanel.classList.add("hidden");
    agentContextMeta.innerHTML = "";
    agentContextSummary.textContent = "";
    return;
  }

  agentContextPanel.classList.remove("hidden");
  agentContextMeta.innerHTML = "";

  const chips = [
    `记录: ${currentAgentRecordContext.record_id}`,
    `场景: ${currentAgentRecordContext.scene || "-"}`,
    `风险: ${riskText(currentAgentRecordContext.overall_risk)}`,
    `隐患项: ${currentAgentRecordContext.items.length}`,
  ];

  chips.forEach((text) => {
    const chip = document.createElement("div");
    chip.className = "agent-context-chip";
    chip.textContent = text;
    agentContextMeta.appendChild(chip);
  });

  agentContextSummary.textContent =
    currentAgentRecordContext.summary || "当前识图结果已载入，可以围绕这次识别继续追问。";
}

function setCurrentAgentRecordContext(context) {
  currentAgentRecordContext = context && context.record_id ? context : null;
  renderAgentRecordContext();
}

function runWithViewTransition(update) {
  update();
}

function updateAgentCharCount() {
  if (!agentCharCount || !agentInput) return;
  const count = String(agentInput.value || "").length;
  agentCharCount.textContent = `${count} / ${maxAgentInputLength}`;
}

function autoResizeAgentInput() {
  if (!agentInput) return;
  agentInput.style.height = "auto";
  const nextHeight = Math.min(Math.max(agentInput.scrollHeight, 64), 220);
  agentInput.style.height = `${nextHeight}px`;
}

function setAgentComposerPending(isPending) {
  if (agentComposerShell) {
    agentComposerShell.classList.toggle("pending", Boolean(isPending));
  }
  if (agentSubmit) {
    agentSubmit.setAttribute("aria-disabled", isPending ? "true" : "false");
  }
  if (agentInput) {
    agentInput.disabled = Boolean(isPending);
  }
}

function setAgentStatus(main, sub = "", state = "ready") {
  if (agentStatus) agentStatus.textContent = main;
  if (agentSubstatus) agentSubstatus.textContent = sub;

  const panel = document.querySelector(".agent-status-panel");
  if (panel) panel.dataset.state = state;

  if (agentLiveBadge) {
    agentLiveBadge.textContent =
      state === "thinking" ? "Thinking" : state === "error" ? "Retry" : "Ready";
  }
}

function saveAgentConversation() {
  try {
    localStorage.setItem(
      agentConversationStorageKey,
      JSON.stringify(agentConversation.slice(-maxAgentHistoryCount))
    );
  } catch (_) {
    // noop
  }
}

function loadAgentConversation() {
  try {
    const raw = localStorage.getItem(agentConversationStorageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.length) return null;
    return parsed
      .map((item) =>
        createAgentMessage(item.role, item.content, {
          citations: item.citations,
          next_actions: item.next_actions,
          used_tools: item.used_tools,
        })
      )
      .filter((item) => item.content);
  } catch (_) {
    return null;
  }
}

function saveAgentSessionId() {
  try {
    if (currentAgentSessionId) {
      localStorage.setItem(agentSessionStorageKey, currentAgentSessionId);
      return;
    }
    localStorage.removeItem(agentSessionStorageKey);
  } catch (_) {
    // noop
  }
}

function loadAgentSessionId() {
  try {
    const raw = localStorage.getItem(agentSessionStorageKey);
    return raw ? String(raw) : null;
  } catch (_) {
    return null;
  }
}

function stopAgentThinkingState() {
  if (agentThinkingTimer) {
    clearInterval(agentThinkingTimer);
    agentThinkingTimer = null;
  }
}

function startAgentThinkingState() {
  stopAgentThinkingState();
  agentThinkingIndex = 0;
  setAgentStatus("Agent 正在思考并调用工具...", agentThinkingSteps[0], "thinking");

  agentThinkingTimer = setInterval(() => {
    agentThinkingIndex = (agentThinkingIndex + 1) % agentThinkingSteps.length;
    setAgentStatus("Agent 正在思考并调用工具...", agentThinkingSteps[agentThinkingIndex], "thinking");
  }, 1600);
}

function renderAgentToolRail() {
  if (!agentToolRail) return;
  const latestAssistant = [...agentConversation].reverse().find((item) => item.role === "assistant");
  const tools = latestAssistant && Array.isArray(latestAssistant.used_tools) ? latestAssistant.used_tools : [];

  agentToolRail.innerHTML = "";
  if (!tools.length) {
    agentToolRail.classList.add("hidden");
    return;
  }

  tools.forEach((tool) => {
    const chip = document.createElement("div");
    chip.className = "agent-tool-rail-chip";
    chip.textContent = `已使用 ${tool}`;
    agentToolRail.appendChild(chip);
  });
  agentToolRail.classList.remove("hidden");
}

function createAgentMessage(role, content, extra = {}) {
  return {
    role,
    content: String(content || "").trim(),
    citations: Array.isArray(extra.citations) ? extra.citations : [],
    next_actions: Array.isArray(extra.next_actions) ? extra.next_actions : [],
    used_tools: Array.isArray(extra.used_tools) ? extra.used_tools : [],
  };
}

function pushAgentSystemNotice(text) {
  const message = createAgentMessage("assistant", text, {
    used_tools: ["scene_notice"],
  });
  agentConversation.push(message);
  saveAgentConversation();
  renderAgentMessages();
}

function loadLastAgentSceneNotice() {
  try {
    const raw = localStorage.getItem(agentSceneChangeKey);
    return raw ? String(raw) : "";
  } catch (_) {
    return "";
  }
}

function saveLastAgentSceneNotice(scene) {
  try {
    localStorage.setItem(agentSceneChangeKey, scene);
  } catch (_) {
    // noop
  }
}

function createPendingAgentNode() {
  const item = document.createElement("div");
  item.className = "agent-message assistant pending";

  const role = document.createElement("div");
  role.className = "agent-role";
  role.textContent = "助手";

  const bubble = document.createElement("div");
  bubble.className = "agent-bubble";

  const thinking = document.createElement("div");
  thinking.className = "agent-thinking";

  const label = document.createElement("div");
  label.className = "agent-thinking-label";
  label.textContent = agentThinkingSteps[agentThinkingIndex] || "正在思考";

  const bar = document.createElement("div");
  bar.className = "agent-thinking-bar";
  for (let index = 0; index < 3; index += 1) {
    bar.appendChild(document.createElement("span"));
  }

  thinking.appendChild(label);
  thinking.appendChild(bar);
  bubble.appendChild(thinking);
  item.appendChild(role);
  item.appendChild(bubble);
  return item;
}

function renderAgentMessages() {
  if (!agentMessagesWrap) return;
  runWithViewTransition(() => {
    agentMessagesWrap.innerHTML = "";

    agentConversation.forEach((message) => {
      const isSystemNotice =
        message.role === "assistant" &&
        Array.isArray(message.used_tools) &&
        message.used_tools.includes("scene_notice");
      const item = document.createElement("div");
      item.className = `agent-message ${message.role === "assistant" ? "assistant" : "user"}${
        isSystemNotice ? " system" : ""
      }`;

      const role = document.createElement("div");
      role.className = "agent-role";
      role.textContent = isSystemNotice ? "系统" : message.role === "assistant" ? "助手" : "我";

      const bubble = document.createElement("div");
      bubble.className = "agent-bubble";
      bubble.textContent = message.content || "";

      item.appendChild(role);
      item.appendChild(bubble);

      if (
        !isSystemNotice &&
        message.role === "assistant" &&
        Array.isArray(message.used_tools) &&
        message.used_tools.length
      ) {
        const meta = document.createElement("div");
        meta.className = "agent-meta";
        message.used_tools.forEach((tool) => {
          const chip = document.createElement("span");
          chip.className = "agent-tool";
          chip.textContent = tool;
          meta.appendChild(chip);
        });
        item.appendChild(meta);
      }

      if (message.role === "assistant" && Array.isArray(message.citations) && message.citations.length) {
        const extra = document.createElement("div");
        extra.className = "agent-extra";
        message.citations.forEach((citation) => {
          const card = document.createElement("div");
          card.className = "agent-citation";

          const title = document.createElement("div");
          title.className = "agent-citation-title";
          title.textContent = `${citation.source || "-"} ${citation.article || "-"}`.trim();

          const quote = document.createElement("div");
          quote.className = "agent-citation-quote";
          quote.textContent = citation.quote || "";

          card.appendChild(title);
          card.appendChild(quote);
          extra.appendChild(card);
        });
        item.appendChild(extra);
      }

      if (message.role === "assistant" && Array.isArray(message.next_actions) && message.next_actions.length) {
        const extra = document.createElement("div");
        extra.className = "agent-extra";
        message.next_actions.forEach((action) => {
          const card = document.createElement("div");
          card.className = "agent-next";

          const title = document.createElement("div");
          title.className = "agent-next-title";
          title.textContent = "接下来可以继续问";

          const text = document.createElement("div");
          text.className = "agent-next-text";
          text.textContent = action;

          card.appendChild(title);
          card.appendChild(text);
          extra.appendChild(card);
        });
        item.appendChild(extra);
      }

      agentMessagesWrap.appendChild(item);
    });

    if (agentPending) {
      agentMessagesWrap.appendChild(createPendingAgentNode());
    }
  });

  renderAgentToolRail();
  saveAgentConversation();
  agentMessagesWrap.scrollTop = agentMessagesWrap.scrollHeight;
}

function buildAgentHistoryPayload() {
  return agentConversation.slice(-6).map((message) => ({
    role: message.role === "assistant" ? "assistant" : "user",
    content: String(message.content || "").slice(0, 600),
  }));
}

async function askAgent(message, scene, currentRecord) {
  const resp = await fetch(buildApiUrl("/agent/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      scene,
      session_id: currentAgentSessionId || undefined,
      history: buildAgentHistoryPayload(),
      current_record: currentRecord || null,
    }),
  });

  const text = await resp.text();
  let data = {};
  try {
    data = JSON.parse(text);
  } catch (_) {
    data = {};
  }

  if (!resp.ok) {
    throw new Error(data.detail || text || `HTTP ${resp.status}`);
  }

  return data;
}

function initAgentMessages() {
  const saved = loadAgentConversation();
  currentAgentSessionId = loadAgentSessionId();
  agentConversation =
    saved && saved.length
      ? saved
      : [
          createAgentMessage(
            "assistant",
            "我是网页端的消防智能助手。你可以直接问法规依据、历史隐患、趋势变化，或者让我给你一份整改建议。"
          ),
        ];
  stopAgentThinkingState();
  agentPending = false;
  setAgentComposerPending(false);
  setAgentStatus(
    "助手已就绪",
    saved && saved.length ? "已恢复上次会话，可以继续追问" : "支持法规检索、趋势复盘和整改建议生成",
    "ready"
  );
  renderAgentRecordContext();
  renderAgentMessages();
}

function startLoadingFacts() {
  if (!loadingFactsWrap || !loadingFactText || !loadingFacts.length) return;
  stopLoadingFacts();
  loadingFactsWrap.classList.remove("hidden");

  loadingFactIndex = Math.floor(Math.random() * loadingFacts.length);
  loadingFactText.textContent = loadingFacts[loadingFactIndex];

  loadingFactTimer = setInterval(() => {
    loadingFactIndex = (loadingFactIndex + 1) % loadingFacts.length;
    loadingFactText.textContent = loadingFacts[loadingFactIndex];
  }, 2600);
}

function stopLoadingFacts() {
  if (loadingFactTimer) {
    clearInterval(loadingFactTimer);
    loadingFactTimer = null;
  }
  if (loadingFactsWrap) loadingFactsWrap.classList.add("hidden");
}

function clearProgressTimer() {
  if (!progressTimer) return;
  clearInterval(progressTimer);
  progressTimer = null;
}

function paintProgress(current, isError = false) {
  progressSteps.forEach((step, idx) => {
    step.classList.remove("active", "done", "error");
    if (idx < current) step.classList.add("done");
    if (idx === current) {
      step.classList.add("active");
      if (isError) step.classList.add("error");
    }
  });
}

function resetProgress() {
  clearProgressTimer();
  stopLoadingFacts();
  progressCurrent = -1;
  progressWrap.classList.add("hidden");
  progressSteps.forEach((step) => step.classList.remove("active", "done", "error"));
}

function startProgress() {
  clearProgressTimer();
  startLoadingFacts();
  progressWrap.classList.remove("hidden");
  progressCurrent = 0;
  paintProgress(progressCurrent);

  progressTimer = setInterval(() => {
    if (progressCurrent < 3) {
      progressCurrent += 1;
      paintProgress(progressCurrent);
      return;
    }
    clearProgressTimer();
  }, 1300);
}

function completeProgress() {
  clearProgressTimer();
  stopLoadingFacts();
  progressWrap.classList.remove("hidden");

  const finalIndex = progressSteps.length - 1;
  progressCurrent = finalIndex;
  progressSteps.forEach((step, idx) => {
    step.classList.remove("active", "done", "error");
    if (idx < finalIndex) step.classList.add("done");
    if (idx === finalIndex) step.classList.add("active", "done");
  });
}

function failProgress() {
  clearProgressTimer();
  stopLoadingFacts();
  progressWrap.classList.remove("hidden");
  if (progressCurrent < 0) progressCurrent = 0;
  paintProgress(progressCurrent, true);
}

function loadLocalHistoryRecords() {
  try {
    const raw = localStorage.getItem(historyStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

function saveLocalHistoryRecords(records) {
  const safeRecords = Array.isArray(records) ? records.slice(0, maxHistoryCount) : [];
  localStorage.setItem(historyStorageKey, JSON.stringify(safeRecords));
  return safeRecords;
}

function upsertLocalHistory(record) {
  const records = loadLocalHistoryRecords();
  const id = String(record.id || "");
  if (!id) return records;

  const idx = records.findIndex((item) => String(item.id || "") === id);
  if (idx >= 0) records[idx] = record;
  else records.unshift(record);

  return saveLocalHistoryRecords(records);
}

function clearLocalHistory() {
  saveLocalHistoryRecords([]);
}

function makeHistoryRecordFromResult(data, scene) {
  return {
    id: String(data.record_id || `local_${Date.now()}`),
    timestamp: new Date().toISOString(),
    overall_risk: data.overall_risk || "warning",
    summary: data.summary || "",
    image_url: normalizeImageUrl(data.annotated_url || data.image_url || ""),
    source: "local",
    scene: scene || "-",
  };
}

function mapRemoteHistoryRecord(item) {
  return {
    id: String(item.record_id || ""),
    timestamp: item.created_at || "",
    overall_risk: item.overall_risk || "warning",
    summary: item.summary || "",
    image_url: normalizeImageUrl(item.thumbnail_url || ""),
    source: "server",
    scene: item.scene || "-",
  };
}

function mergeHistoryRecords(localRecords, serverRecords) {
  const map = new Map();
  const merged = [];

  const push = (record) => {
    if (!record) return;
    const id = String(record.id || "");
    if (!id || map.has(id)) return;
    map.set(id, true);
    merged.push(record);
  };

  (localRecords || []).forEach(push);
  (serverRecords || []).forEach(push);

  merged.sort((a, b) => {
    const ta = new Date(a.timestamp || 0).getTime();
    const tb = new Date(b.timestamp || 0).getTime();
    return tb - ta;
  });

  return merged.slice(0, maxHistoryCount);
}

function formatHistoryTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";

  const now = Date.now();
  const diff = now - date.getTime();

  if (diff < 60 * 1000) return "刚刚";
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))} 分钟前`;
  if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / (60 * 60 * 1000))} 小时前`;
  if (diff < 7 * 24 * 60 * 60 * 1000) return `${Math.floor(diff / (24 * 60 * 60 * 1000))} 天前`;

  return date.toLocaleDateString("zh-CN");
}

function renderHistory() {
  const localRecords = loadLocalHistoryRecords();
  const records = mergeHistoryRecords(localRecords, remoteHistoryRecords);

  historyList.innerHTML = "";

  if (!records.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "暂无历史记录，完成一次识别后会自动保存。";
    historyList.appendChild(empty);
  } else {
    records.forEach((record) => {
      const item = document.createElement("div");
      item.className = "history-item";

      let thumb;
      if (record.image_url) {
        thumb = document.createElement("img");
        thumb.className = "history-thumb";
        thumb.src = record.image_url;
        thumb.alt = "历史图片";
      } else {
        thumb = document.createElement("div");
        thumb.className = "history-thumb placeholder";
        thumb.textContent = "无图";
      }

      const meta = document.createElement("div");
      meta.className = "history-meta";

      const badge = document.createElement("div");
      badge.className = `badge ${mapRiskClass(record.overall_risk)}`;
      badge.textContent = `风险: ${riskText(record.overall_risk)}`;

      const summary = document.createElement("div");
      summary.className = "history-summary";
      summary.textContent = record.summary || "无摘要";

      const time = document.createElement("div");
      time.className = "history-time";
      time.textContent = formatHistoryTime(record.timestamp);

      meta.appendChild(badge);
      meta.appendChild(summary);
      meta.appendChild(time);

      const tags = document.createElement("div");
      tags.className = "history-tags";

      const source = document.createElement("div");
      source.className = "history-source";
      source.textContent = record.source === "server" ? "后端" : "本地";

      const scene = document.createElement("div");
      scene.className = "history-source";
      scene.textContent = `场景: ${record.scene || "-"}`;

      tags.appendChild(source);
      tags.appendChild(scene);

      item.appendChild(thumb);
      item.appendChild(meta);
      item.appendChild(tags);
      historyList.appendChild(item);
    });
  }

  historyStatus.textContent = `本地 ${localRecords.length} 条，后端 ${remoteHistoryRecords.length} 条`;
}

function toPercent(value) {
  const num = Number(value || 0);
  if (Number.isNaN(num)) return "0.0";
  return num.toFixed(1);
}

function renderInsightMetrics(data) {
  if (!hasInsightsUI) return;
  insightMetrics.innerHTML = "";
  const windows = (data && data.windows) || {};
  const metrics7 = windows["7d"] || {};
  const metrics30 = windows["30d"] || {};
  const trends = (data && data.trends) || {};
  const trend7 = trends["7d"] || {};

  const cards = [
    {
      title: "7天高风险占比",
      value: `${toPercent(metrics7.high_risk_ratio)}%`,
      desc: `样本 ${metrics7.total_records || 0} 条`,
    },
    {
      title: "30天高风险占比",
      value: `${toPercent(metrics30.high_risk_ratio)}%`,
      desc: `样本 ${metrics30.total_records || 0} 条`,
    },
    {
      title: "安全改进分",
      value: `${data && data.safety_score ? data.safety_score : 0}`,
      desc: `${trend7.summary || "暂无趋势信息"}`,
    },
  ];

  cards.forEach((card) => {
    const node = document.createElement("div");
    node.className = "insight-metric-card";

    const t = document.createElement("div");
    t.className = "insight-metric-title";
    t.textContent = card.title;

    const v = document.createElement("div");
    v.className = "insight-metric-value";
    v.textContent = card.value;

    const d = document.createElement("div");
    d.className = "insight-metric-desc";
    d.textContent = card.desc;

    node.appendChild(t);
    node.appendChild(v);
    node.appendChild(d);
    insightMetrics.appendChild(node);
  });
}

function renderInsightAlerts(data) {
  if (!hasInsightsUI) return;
  insightAlerts.innerHTML = "";
  const alerts = (data && data.recurrence_alerts) || [];
  const repeatedScenes = (((data || {}).windows || {})["30d"] || {}).repeated_scenes || [];
  const topHazards = (((data || {}).windows || {})["30d"] || {}).top_hazards || [];

  const tags = [];
  if (topHazards.length) {
    tags.push(`Top隐患: ${topHazards[0].type} (${topHazards[0].count}次)`);
  }
  if (repeatedScenes.length) {
    tags.push(`高频场景: ${repeatedScenes[0].scene} (${repeatedScenes[0].count}次)`);
  }
  alerts.forEach((a) => {
    tags.push(`复发预警: ${a.hazard_type} 连续 ${a.streak} 次`);
  });

  if (!tags.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "暂无复发预警，继续保持巡检。";
    insightAlerts.appendChild(empty);
    return;
  }

  tags.slice(0, 5).forEach((text) => {
    const tag = document.createElement("span");
    tag.className = "insight-alert-tag";
    tag.textContent = text;
    insightAlerts.appendChild(tag);
  });
}

function renderInsightRecommendations(data) {
  if (!hasInsightsUI) return;
  insightRecommendations.innerHTML = "";
  const items = (data && data.recommendations) || [];
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "暂无建议。";
    insightRecommendations.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "item";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = `P${item.priority || "-"} · ${item.title || "综合建议"}`;

    const reason = document.createElement("div");
    reason.textContent = `原因：${item.reason || "-"}`;

    const steps = document.createElement("div");
    const stepText = Array.isArray(item.steps) ? item.steps.filter(Boolean).join("；") : "-";
    steps.textContent = `执行步骤：${stepText}`;

    const effect = document.createElement("div");
    effect.className = "hint";
    effect.textContent = `预期效果：${item.expected_effect || "-"}`;

    card.appendChild(title);
    card.appendChild(reason);
    card.appendChild(steps);
    card.appendChild(effect);
    insightRecommendations.appendChild(card);
  });
}

function renderInsights(data) {
  if (!hasInsightsUI) return;
  const generatedAt = data && data.generated_at ? new Date(data.generated_at) : null;
  const ts =
    generatedAt && !Number.isNaN(generatedAt.getTime())
      ? generatedAt.toLocaleString("zh-CN")
      : "未知时间";
  const source = (data && data.recommendation_source) || "rule_based";
  const sourceText = source === "llm" ? "LLM建议" : "规则建议";
  const cacheText = data && data.cached ? " · 缓存命中" : "";
  insightStatus.textContent = `更新时间: ${ts} · ${sourceText}${cacheText}`;

  renderInsightMetrics(data);
  renderInsightAlerts(data);
  renderInsightRecommendations(data);
}

async function fetchInsights(days = 7) {
  if (!hasInsightsUI) return;
  insightStatus.textContent = "正在生成综合建议...";
  try {
    const resp = await fetch(buildApiUrl(`/records/insights?days=${days}`));
    const text = await resp.text();
    let data = {};
    try {
      data = JSON.parse(text);
    } catch (_) {
      data = {};
    }
    if (!resp.ok) throw new Error(data.detail || text || `HTTP ${resp.status}`);
    renderInsights(data);
  } catch (err) {
    insightStatus.textContent = `综合建议生成失败: ${err.message}`;
    insightMetrics.innerHTML = "";
    insightAlerts.innerHTML = "";
    insightRecommendations.innerHTML = "";
  }
}

async function fetchRemoteHistory() {
  historyStatus.textContent = "同步后端历史中...";
  try {
    const resp = await fetch(buildApiUrl("/records?limit=20&offset=0"));
    const text = await resp.text();
    let data = {};

    try {
      data = JSON.parse(text);
    } catch (_) {
      data = {};
    }

    if (!resp.ok) throw new Error(data.detail || text || `HTTP ${resp.status}`);

    const list = Array.isArray(data.records) ? data.records : [];
    remoteHistoryRecords = list.map(mapRemoteHistoryRecord).filter((item) => item.id);

    renderHistory();
    historyStatus.textContent = `已同步后端历史 ${remoteHistoryRecords.length} 条`;
  } catch (err) {
    remoteHistoryRecords = [];
    renderHistory();
    historyStatus.textContent = `后端历史同步失败: ${err.message}`;
  }
}

async function clearRemoteHistory() {
  const resp = await fetch(buildApiUrl("/records/"), {
    method: "DELETE",
  });
  const text = await resp.text();
  let data = {};
  try {
    data = JSON.parse(text);
  } catch (_) {
    data = {};
  }
  if (!resp.ok) {
    throw new Error(data.detail || text || `HTTP ${resp.status}`);
  }
  return data;
}

async function uploadAndAnalyze(file, scene, force = false) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("scene", scene);
  if (force) {
    formData.append("force", "true");
  }

  const resp = await fetch(buildApiUrl("/analysis/upload"), {
    method: "POST",
    body: formData,
  });

  const text = await resp.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch (_) {
    // noop
  }

  if (!resp.ok) {
    const detail = (json && json.detail) || text || `HTTP ${resp.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return json;
}

async function runAnalysisRequest(file, scene, force = false) {
  startProgress();
  uploadStatus.textContent = force ? "重新思考中..." : "上传并识别中...";

  try {
    const result = await uploadAndAnalyze(file, scene, force);

    completeProgress();
    uploadStatus.textContent = force ? "重新思考完成" : "识别完成";
    renderResult(result);
    setCurrentAgentRecordContext(buildCurrentRecordContext(result, scene));
    if (agentSceneSelect) agentSceneSelect.value = scene;
    setAgentStatus(
      "识图结果已接入助手",
      "你现在可以围绕这次识别结果继续追问，也可以关闭上下文做通用问答",
      "ready"
    );

    const historyRecord = makeHistoryRecordFromResult(result, scene);
    upsertLocalHistory(historyRecord);
    renderHistory();
    fetchRemoteHistory();
    fetchInsights(7);
    return result;
  } catch (err) {
    failProgress();
    uploadStatus.textContent = `${force ? "重新思考" : "识别"}失败: ${err.message}`;
    throw err;
  }
}

// ------------------------------------------------------------------ //
// Memory Inspector — render the four memory layers returned by the    //
// backend on /agent/chat (data.memory + data.tool_outputs.long_term). //
// Mirrors the four-layer memory design and observable, not             //
// a black-box).                                                       //
// ------------------------------------------------------------------ //
function setMemoryInspectorStatus(text) {
  if (memoryInspectorStatus) memoryInspectorStatus.textContent = text || "";
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function renderEmptyInto(el, message) {
  if (!el) return;
  el.innerHTML = "";
  const note = document.createElement("div");
  note.className = "memory-empty";
  note.textContent = message;
  el.appendChild(note);
}

function renderMemoryCore(coreLayer) {
  if (!memoryCoreRules || !memoryCoreBadge) return;
  const rules = safeArray(coreLayer.rules);
  const scope = String(coreLayer.scope || coreLayer.scope_label || "global");
  memoryCoreBadge.textContent = `${rules.length} 条 · ${scope}`;
  memoryCoreBadge.className = `memory-layer-badge ${rules.length ? "" : "muted"}`.trim();

  memoryCoreRules.innerHTML = "";
  if (!rules.length) {
    renderEmptyInto(memoryCoreRules, "暂无 Core Memory 规则 (检查是否已 seed)");
    return;
  }
  rules.forEach((rule) => {
    const li = document.createElement("li");
    // rules can be plain strings (legacy) or {text, scope, priority, ...}
    if (typeof rule === "string") {
      li.textContent = rule;
      li.dataset.scope = "global";
    } else {
      const safeRule = safeObject(rule);
      li.textContent = String(safeRule.text || "");
      li.dataset.scope = String(safeRule.scope || "global");
      if (Number.isFinite(safeRule.priority)) {
        li.title = `priority ${safeRule.priority}${safeRule.source ? " · " + safeRule.source : ""}`;
      }
    }
    memoryCoreRules.appendChild(li);
  });
}

function renderMemoryTask(taskLayer) {
  if (!memoryTaskDetail || !memoryTaskBadge) return;
  const goalVersion = Number(taskLayer.goal_version || 0);
  const resetReason = String(taskLayer.goal_reset_reason || "");
  const scene = String(taskLayer.scene || "");
  const userGoal = String(taskLayer.task_goal || taskLayer.user_goal || "");
  const planner = safeObject(taskLayer.planner_intent);
  const needs = Object.entries(planner)
    .filter(([k, v]) => k.startsWith("needs_") && v)
    .map(([k]) => k.replace(/^needs_/, ""));

  memoryTaskBadge.textContent = `v${goalVersion || "?"}${resetReason ? " · " + resetReason : ""}`;
  memoryTaskBadge.className = `memory-layer-badge ${resetReason ? "warn" : ""}`.trim();

  memoryTaskDetail.innerHTML = "";
  const dl = document.createElement("dl");
  dl.className = "memory-task-detail";
  const rows = [
    ["session_id", String(taskLayer.session_id || "(none)")],
    ["scene", scene || "(none)"],
    ["task_goal", userGoal || "(none)"],
    ["planner.goal", String(planner.goal || "(none)")],
    ["planner.response_style", String(planner.response_style || "(none)")],
    ["needs_tools", needs.length ? needs.join(", ") : "(none)"],
    ["goal_version", String(goalVersion || "?")],
    [
      "goal_reset_reason",
      resetReason ? `🔄 ${resetReason}` : "(stable)",
    ],
  ];
  rows.forEach(([label, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    if (label === "goal_reset_reason" && resetReason) {
      dd.classList.add("task-reset");
    }
    dl.appendChild(dt);
    dl.appendChild(dd);
  });
  memoryTaskDetail.appendChild(dl);
}

function renderMemoryShortTerm(shortLayer) {
  if (!memoryShortBadge || !memoryShortSummary || !memoryShortMeta) return;
  const messageCount = Number(shortLayer.message_count || 0);
  memoryShortBadge.textContent = `${messageCount} 轮`;
  memoryShortBadge.className = `memory-layer-badge ${messageCount ? "" : "muted"}`.trim();

  memoryShortSummary.textContent = String(shortLayer.summary || "(no summary yet)");

  memoryShortMeta.innerHTML = "";
  const recent = safeArray(shortLayer.recent_messages);
  const lastAssistant = [...recent].reverse().find((m) => m && m.role === "assistant");
  if (!lastAssistant || !lastAssistant.metadata) {
    renderEmptyInto(memoryShortMeta, "上一轮无审计元数据 (检查后端 chat_messages 是否已加列)");
    return;
  }
  const meta = safeObject(lastAssistant.metadata);
  const rulesQuery = String(meta.rules_query || "");
  const evidenceIds = safeArray(meta.evidence_ids);
  const guardrail = safeObject(meta.guardrail);

  const rowsToBuild = [
    {
      label: "rules_query",
      chips: rulesQuery
        ? [{ text: rulesQuery, kind: "" }]
        : [{ text: "(本轮未触发法规检索)", kind: "muted" }],
    },
    {
      label: "evidence_ids",
      chips: evidenceIds.length
        ? evidenceIds.map((id) => ({ text: id, kind: "evidence" }))
        : [{ text: "(no evidence)", kind: "muted" }],
    },
    {
      label: "guardrail",
      chips: [
        {
          text: `asked_for_rules=${Boolean(guardrail.asked_for_rules)}`,
          kind: guardrail.asked_for_rules ? "warn" : "",
        },
        {
          text: `has_rule_evidence=${Boolean(guardrail.has_rule_evidence)}`,
          kind: guardrail.has_rule_evidence ? "evidence" : "danger",
        },
        {
          text: `kept_citations=${Number(guardrail.kept_citations || 0)}`,
          kind: "",
        },
        guardrail.confidence
          ? {
              text: `confidence=${guardrail.confidence}`,
              kind:
                guardrail.confidence === "low"
                  ? "warn"
                  : guardrail.confidence === "high"
                  ? "evidence"
                  : "",
            }
          : null,
      ].filter(Boolean),
    },
  ];

  rowsToBuild.forEach((row) => {
    const wrap = document.createElement("div");
    wrap.className = "memory-short-meta-row";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = row.label;
    wrap.appendChild(label);
    row.chips.forEach((chip) => {
      const span = document.createElement("span");
      span.className = `memory-meta-chip ${chip.kind || ""}`.trim();
      span.textContent = chip.text;
      wrap.appendChild(span);
    });
    memoryShortMeta.appendChild(wrap);
  });
}

function renderMemoryLongTerm(longLayer) {
  if (
    !memoryLongBadge ||
    !memoryLongMode ||
    !memoryLongRecurring ||
    !memoryLongSimilar ||
    !memoryLongTasks
  ) {
    return;
  }
  const profiles = safeArray(longLayer.profiles);
  const recurring = safeArray(longLayer.recurring_hazards);
  const similar = safeArray(longLayer.similar_cases);
  const openTasks = safeArray(longLayer.open_tasks);
  const mode = String(longLayer.similar_cases_mode || "");

  const muMatch = /mu=(\d+(?:\.\d+)?)/i.exec(mode);
  const muValue = muMatch ? Number(muMatch[1]) : null;
  const isDegraded = muValue === 0 || /lexical/i.test(mode);

  memoryLongBadge.textContent = `${profiles.length} 画像 · ${recurring.length} 复发`;
  memoryLongBadge.className = `memory-layer-badge ${recurring.length ? "warn" : profiles.length ? "" : "muted"}`.trim();

  memoryLongMode.innerHTML = "";
  if (mode) {
    const pill = document.createElement("span");
    pill.className = `mu-pill ${isDegraded ? "degraded" : ""}`.trim();
    pill.textContent = muValue !== null ? `μ=${muValue.toFixed(2)}` : mode;
    memoryLongMode.appendChild(pill);
    const trailing = document.createElement("span");
    trailing.textContent = isDegraded
      ? `检索模式: ${mode} (向量降级，纯词法兜底)`
      : `检索模式: ${mode}`;
    memoryLongMode.appendChild(trailing);
  } else {
    memoryLongMode.textContent = "(尚未触发长期检索)";
  }

  const renderSection = (host, title, items, renderer, emptyMsg) => {
    host.innerHTML = "";
    const head = document.createElement("div");
    head.className = "memory-long-section-title";
    head.textContent = `${title} (${items.length})`;
    host.appendChild(head);
    if (!items.length) {
      renderEmptyInto(host, emptyMsg);
      return;
    }
    items.slice(0, 4).forEach((item) => host.appendChild(renderer(item)));
  };

  renderSection(
    memoryLongRecurring,
    "复发隐患 (count_30d ≥ 2)",
    recurring,
    (item) => {
      const row = document.createElement("div");
      const isDanger = Number(item.count_30d || 0) >= 4;
      row.className = `memory-long-item ${isDanger ? "danger" : ""}`.trim();
      const name = document.createElement("span");
      name.className = "hazard-name";
      name.textContent = String(item.hazard_type || "?");
      const meta = document.createElement("span");
      meta.className = "hazard-meta";
      meta.textContent = `30d=${item.count_30d || 0} · 7d=${item.count_7d || 0} · scene=${item.scene || "?"}`;
      row.appendChild(name);
      row.appendChild(meta);
      return row;
    },
    "尚未识别到复发隐患",
  );

  renderSection(
    memoryLongSimilar,
    "相似历史案例",
    similar,
    (item) => {
      const row = document.createElement("div");
      row.className = "memory-long-item";
      const name = document.createElement("span");
      name.className = "hazard-name";
      name.textContent = String(item.summary || item.record_id || "(no summary)");
      const meta = document.createElement("span");
      meta.className = "hazard-meta";
      const score = Number(item.score || 0);
      meta.textContent = `score=${score.toFixed(3)} · risk=${item.overall_risk || "?"} · scene=${item.scene || "?"}`;
      row.appendChild(name);
      row.appendChild(meta);
      return row;
    },
    "尚无相似案例",
  );

  renderSection(
    memoryLongTasks,
    "未关闭的整改任务",
    openTasks,
    (item) => {
      const row = document.createElement("div");
      row.className = `memory-long-item ${Number(item.priority) === 1 ? "danger" : ""}`.trim();
      const name = document.createElement("span");
      name.className = "hazard-name";
      name.textContent = String(item.title || item.task_id || "(no title)");
      const meta = document.createElement("span");
      meta.className = "hazard-meta";
      meta.textContent = `priority=${item.priority || "?"} · hazard=${item.hazard_type || "?"}`;
      row.appendChild(name);
      row.appendChild(meta);
      return row;
    },
    "没有待办整改任务",
  );
}

function renderMemoryInspector(memory, toolOutputs, statusOverride) {
  if (!memoryInspectorEl) return;
  latestMemorySnapshot = memory || null;
  const memSafe = safeObject(memory);
  const core = safeObject(memSafe.core);
  const task = safeObject(memSafe.task);
  const shortTerm = safeObject(memSafe.short_term);
  // Long-term layer in /agent/chat is wrapped under tool_outputs; for the
  // /memory/snapshot endpoint it lands under memory.long_term directly.
  const longTermFromMem = safeObject(memSafe.long_term);
  const longTermFromTools = safeObject(safeObject(toolOutputs).long_term_memory);
  const longTerm = Object.keys(longTermFromMem).length ? longTermFromMem : longTermFromTools;

  renderMemoryCore(core);
  renderMemoryTask(task);
  renderMemoryShortTerm(shortTerm);
  renderMemoryLongTerm(longTerm);

  if (statusOverride) {
    setMemoryInspectorStatus(statusOverride);
  } else {
    const stamp = new Date().toLocaleTimeString();
    const ver = Number(task.goal_version || 0);
    setMemoryInspectorStatus(`已同步 · v${ver || "?"} · ${stamp}`);
  }
}

// Detect a task-memory reset between two consecutive chat turns and emit a
// system notice into the conversation (scene/goal change
// triggers an active reset).
function detectAndAnnounceTaskReset(memory) {
  const task = safeObject(safeObject(memory).task);
  const goalVersion = Number(task.goal_version || 0);
  const sessionId = String(task.session_id || "");
  if (!goalVersion || !sessionId) return;

  // Reset tracker if the session itself changed (new conversation).
  if (lastMemorySessionId && lastMemorySessionId !== sessionId) {
    lastMemoryGoalVersion = null;
  }
  lastMemorySessionId = sessionId;

  if (lastMemoryGoalVersion !== null && goalVersion > lastMemoryGoalVersion) {
    const reason = String(task.goal_reset_reason || "目标变更");
    const reasonLabel =
      reason === "scene_change"
        ? "场景切换"
        : reason === "goal_change"
        ? "目标切换"
        : reason;
    pushAgentSystemNotice(
      `🔄 任务记忆已重置 (v${lastMemoryGoalVersion} → v${goalVersion}，原因：${reasonLabel})`,
    );
  }
  lastMemoryGoalVersion = goalVersion;
}

async function fetchMemorySnapshot() {
  if (!memoryInspectorEl) return;
  const scene = agentSceneSelect ? agentSceneSelect.value : "campus";
  const query = String((agentInput && agentInput.value) || "").slice(0, 200);
  const params = new URLSearchParams({ scene });
  if (currentAgentSessionId) params.set("session_id", currentAgentSessionId);
  if (query) params.set("query", query);
  setMemoryInspectorStatus("正在拉取 /memory/snapshot ...");
  try {
    const resp = await fetch(buildApiUrl(`/memory/snapshot?${params.toString()}`));
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await resp.json();
    // Snapshot endpoint already nests long_term under memory; pass null for
    // tool outputs so we read from memory.long_term directly.
    renderMemoryInspector(data, null, `快照已更新 · ${new Date().toLocaleTimeString()}`);
  } catch (err) {
    setMemoryInspectorStatus(`快照拉取失败：${err.message || "未知错误"}`);
  }
}

if (refreshMemorySnapshotButton) {
  refreshMemorySnapshotButton.addEventListener("click", fetchMemorySnapshot);
}

// ------------------------------------------------------------------ //
// P1: recurrence alert + remediation task list                        //
// Both backed by /memory/overview (single call returns both pieces).  //
// ------------------------------------------------------------------ //

// Persist a dismissal signature so the alert doesn't reappear every page
// load if the user already acknowledged the same recurring hazards.
function loadDismissedRecurrenceSignature() {
  try {
    return localStorage.getItem(recurrenceDismissStorageKey) || "";
  } catch (_) {
    return "";
  }
}

function saveDismissedRecurrenceSignature(sig) {
  try {
    if (sig) localStorage.setItem(recurrenceDismissStorageKey, sig);
    else localStorage.removeItem(recurrenceDismissStorageKey);
  } catch (_) {
    /* noop */
  }
}

function buildRecurrenceSignature(scene, hazards) {
  const tokens = hazards
    .map((h) => `${h.hazard_type || ""}:${h.count_30d || 0}`)
    .sort()
    .join("|");
  return `${scene || ""}::${tokens}`;
}

function renderRecurrenceAlert(scene, recurringHazards) {
  if (!recurrenceAlertEl) return;
  const hazards = safeArray(recurringHazards).filter(
    (h) => h && Number(h.count_30d || 0) >= 2,
  );
  if (!hazards.length) {
    recurrenceAlertEl.classList.add("hidden");
    return;
  }
  const sig = buildRecurrenceSignature(scene, hazards);
  if (sig && sig === loadDismissedRecurrenceSignature()) {
    // User acknowledged this exact set; keep hidden until it changes.
    recurrenceAlertEl.classList.add("hidden");
    return;
  }

  if (recurrenceAlertTitle) {
    recurrenceAlertTitle.textContent =
      `近 30 天该场景出现 ${hazards.length} 类复发隐患`;
  }
  if (recurrenceAlertBody) {
    recurrenceAlertBody.innerHTML = "";
    hazards.slice(0, 4).forEach((h) => {
      const pill = document.createElement("span");
      pill.className = "hazard-pill";
      pill.textContent = `${h.hazard_type || "?"} × ${h.count_30d || 0}`;
      pill.title = `7d=${h.count_7d || 0} · 30d=${h.count_30d || 0}\n${h.last_summary || ""}`;
      recurrenceAlertBody.appendChild(pill);
    });
    if (hazards.length > 4) {
      const more = document.createElement("span");
      more.textContent = ` 及其他 ${hazards.length - 4} 项`;
      recurrenceAlertBody.appendChild(more);
    }
  }
  recurrenceAlertEl.classList.remove("hidden");
  recurrenceAlertEl.dataset.signature = sig;
}

if (recurrenceAlertDismiss) {
  recurrenceAlertDismiss.addEventListener("click", () => {
    if (!recurrenceAlertEl) return;
    const sig = recurrenceAlertEl.dataset.signature || "";
    saveDismissedRecurrenceSignature(sig);
    recurrenceAlertEl.classList.add("hidden");
  });
}

function setMemoryTasksStatus(text) {
  if (memoryTasksStatus) memoryTasksStatus.textContent = text || "";
}

function renderMemoryTasksList(tasks) {
  if (!memoryTasksList) return;
  memoryTasksList.innerHTML = "";
  const items = safeArray(tasks);
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "memory-task-empty";
    empty.textContent = "当前场景没有待办整改任务。";
    memoryTasksList.appendChild(empty);
    return;
  }

  items.slice(0, 8).forEach((task) => {
    const li = document.createElement("li");
    const priority = Number(task.priority || 2);
    const priorityCls =
      priority === 1 ? "priority-high" : priority === 2 ? "priority-medium" : "";
    li.className = `memory-task-row ${priorityCls}`.trim();
    li.dataset.taskId = String(task.task_id || "");

    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent = String(task.title || "(no title)");
    if (task.hazard_type) title.title = `hazard: ${task.hazard_type}`;
    li.appendChild(title);

    const prioPill = document.createElement("span");
    prioPill.className = "task-priority";
    prioPill.textContent =
      priority === 1 ? "P1 高危" : priority === 2 ? "P2 中危" : `P${priority}`;
    li.appendChild(prioPill);

    const closeBtn = document.createElement("button");
    closeBtn.className = "task-close";
    closeBtn.type = "button";
    closeBtn.textContent = "标记完成";
    closeBtn.addEventListener("click", () => closeMemoryTask(task.task_id, li));
    li.appendChild(closeBtn);

    memoryTasksList.appendChild(li);
  });
}

async function closeMemoryTask(taskId, rowEl) {
  if (!taskId) return;
  rowEl.classList.add("closing");
  try {
    const resp = await fetch(
      buildApiUrl(`/memory/tasks/${encodeURIComponent(taskId)}/status`),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "done" }),
      },
    );
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    rowEl.remove();
    // Refresh overview so badges / similar inspector counts stay in sync.
    fetchMemoryOverview();
  } catch (err) {
    rowEl.classList.remove("closing");
    setMemoryTasksStatus(`完成失败：${err.message || "未知错误"}`);
  }
}

async function fetchMemoryOverview() {
  const scene = agentSceneSelect ? agentSceneSelect.value : "campus";
  const query = String((agentInput && agentInput.value) || "").slice(0, 200);
  const params = new URLSearchParams({ scene });
  if (query) params.set("query", query);
  setMemoryTasksStatus("加载中...");
  try {
    const resp = await fetch(buildApiUrl(`/memory/overview?${params.toString()}`));
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await resp.json();
    renderRecurrenceAlert(scene, safeArray(data.recurring_hazards));
    renderMemoryTasksList(safeArray(data.open_tasks));
    const count = safeArray(data.open_tasks).length;
    setMemoryTasksStatus(`${count} 项待办 · ${new Date().toLocaleTimeString()}`);
  } catch (err) {
    setMemoryTasksStatus(`拉取失败：${err.message || "未知错误"}`);
  }
}

if (refreshMemoryTasksButton) {
  refreshMemoryTasksButton.addEventListener("click", fetchMemoryOverview);
}

async function submitAgentMessage() {
  if (agentPending) return;
  const text = String(agentInput.value || "").trim();
  if (!text) {
    setAgentStatus("请先输入问题", "输入法规、历史、趋势或整改类问题都可以", "error");
    return;
  }

  agentConversation.push(createAgentMessage("user", text));
  agentPending = true;
  setAgentComposerPending(true);
  renderAgentMessages();
  agentInput.value = "";
  updateAgentCharCount();
  autoResizeAgentInput();
  startAgentThinkingState();

  try {
    const useCurrentRecord = Boolean(
      currentAgentRecordContext &&
        currentAgentRecordContext.record_id &&
        agentUseCurrentRecord &&
        agentUseCurrentRecord.checked
    );
    const result = await askAgent(
      text,
      agentSceneSelect ? agentSceneSelect.value : "campus",
      useCurrentRecord ? currentAgentRecordContext : null
    );
    currentAgentSessionId = result.session_id || currentAgentSessionId || null;
    saveAgentSessionId();
    // Detect task-memory reset BEFORE the assistant bubble so the system
    // notice appears between the user turn and the reply.
    detectAndAnnounceTaskReset(result.memory);
    agentConversation.push(
      createAgentMessage("assistant", result.reply || "暂时没有返回内容。", {
        citations: result.citations || [],
        next_actions: result.next_actions || [],
        used_tools: result.used_tools || [],
      })
    );
    // Refresh the four-layer memory inspector from this turn's snapshot.
    renderMemoryInspector(result.memory, result.tool_outputs);
    // Re-pull overview so the recurrence banner + remediation list reflect
    // any new write triggered by this turn (analyzer may have added a task).
    fetchMemoryOverview();
    stopAgentThinkingState();
    agentPending = false;
    setAgentComposerPending(false);
    renderAgentMessages();
    setAgentStatus(
      "Agent 已完成回答",
      Array.isArray(result.used_tools) && result.used_tools.length
        ? `本轮调用了 ${result.used_tools.join("、")}`
        : "这轮回答没有额外工具痕迹",
      "ready"
    );
    if (useCurrentRecord) {
      agentSubstatus.textContent = "这轮回答已经带上当前识图结果作为上下文";
    }
  } catch (err) {
    stopAgentThinkingState();
    agentPending = false;
    setAgentComposerPending(false);
    agentConversation.push(
      createAgentMessage("assistant", `当前请求失败：${err.message || "未知错误"}`)
    );
    renderAgentMessages();
    setAgentStatus("Agent 请求失败", "你可以直接重试，或者换一个更具体的问题", "error");
  }
}

if (agentForm) {
  agentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitAgentMessage();
  });
}

if (agentSceneSelect) {
  agentSceneSelect.addEventListener("change", () => {
    const nextScene = agentSceneSelect.value;
    fetchSceneGuide(nextScene);

    const lastScene = loadLastAgentSceneNotice();
    if (nextScene && nextScene !== lastScene) {
      pushAgentSystemNotice(buildSceneSwitchNotice(nextScene));
      saveLastAgentSceneNotice(nextScene);
    }

    // Recurrence banner and remediation list are scene-scoped — refresh on
    // every scene change, even before a chat turn is sent. Clearing the
    // dismissed signature ensures alerts surface again for the new scene.
    saveDismissedRecurrenceSignature("");
    fetchMemoryOverview();
  });
}

if (agentSubmit) {
  agentSubmit.addEventListener("click", async () => {
    await submitAgentMessage();
  });

  agentSubmit.addEventListener("keydown", async (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      await submitAgentMessage();
    }
  });
}

if (agentInput) {
  agentInput.addEventListener("input", () => {
    const current = String(agentInput.value || "");
    if (current.length > maxAgentInputLength) {
      agentInput.value = current.slice(0, maxAgentInputLength);
    }
    updateAgentCharCount();
    autoResizeAgentInput();
  });

  agentInput.addEventListener("keydown", async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await submitAgentMessage();
    }
  });
}

if (clearAgentChatButton) {
  clearAgentChatButton.addEventListener("click", () => {
    localStorage.removeItem(agentConversationStorageKey);
    localStorage.removeItem(agentSessionStorageKey);
    currentAgentSessionId = null;
    // Drop the memory-inspector tracking so the next session starts fresh
    // and does not falsely flag a "reset" from a stale goal_version.
    lastMemoryGoalVersion = null;
    lastMemorySessionId = null;
    latestMemorySnapshot = null;
    renderMemoryInspector(null, null, "对话已清空，等待新会话");
    initAgentMessages();
    updateAgentCharCount();
    autoResizeAgentInput();
    setAgentStatus("对话已清空", "新的会话已经开始", "ready");
  });
}

agentQuickPrompts.forEach((button) => {
  button.addEventListener("click", () => {
    if (!agentInput) return;
    agentInput.value = button.dataset.prompt || "";
    updateAgentCharCount();
    autoResizeAgentInput();
    agentInput.focus();
  });
});

agentFollowupPrompts.forEach((button) => {
  button.addEventListener("click", () => {
    if (!agentInput) return;
    agentInput.value = button.dataset.template || "";
    updateAgentCharCount();
    autoResizeAgentInput();
    agentInput.focus();
  });
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    resetProgress();
    uploadStatus.textContent = "请先选择图片";
    return;
  }

  try {
    const scene = sceneSelect.value;
    lastUploadedFile = file;
    lastUploadedScene = scene;
    await runAnalysisRequest(file, scene, false);
    uploadForm.reset();
    updateSelectedFileName();
  } catch (err) {
    // handled in runAnalysisRequest
  }
});

if (fileInput) {
  fileInput.addEventListener("change", updateSelectedFileName);
}

saveConfigButton.addEventListener("click", saveConfig);

openHistoryButton.addEventListener("click", () => {
  if (historyCard) historyCard.scrollIntoView({ behavior: "smooth", block: "start" });
});

refreshHistoryButton.addEventListener("click", () => {
  fetchRemoteHistory();
});

if (rethinkAnalyzeButton) {
  rethinkAnalyzeButton.addEventListener("click", async () => {
    if (!lastUploadedFile) {
      uploadStatus.textContent = "请先上传一张图片后再重新思考";
      return;
    }
    const scene = sceneSelect ? sceneSelect.value : lastUploadedScene || "campus";
    lastUploadedScene = scene;
    try {
      await runAnalysisRequest(lastUploadedFile, scene, true);
    } catch (_) {
      // handled in runAnalysisRequest
    }
  });
}

if (refreshInsightsButton) {
  refreshInsightsButton.addEventListener("click", () => {
    fetchInsights(7);
  });
}

if (toggleInsightsButton) {
  toggleInsightsButton.addEventListener("click", () => {
    toggleInsightsCollapsed();
  });
}

clearRemoteHistoryButton.addEventListener("click", async () => {
  const ok = window.confirm("将清空后端数据库中的历史记录，是否继续？");
  if (!ok) return;
  historyStatus.textContent = "正在清空后端历史...";
  try {
    const result = await clearRemoteHistory();
    remoteHistoryRecords = [];
    renderHistory();
    historyStatus.textContent = `后端已清空：记录 ${result.deleted_records || 0} 条，文件 ${result.deleted_files || 0} 个，缓存 ${result.deleted_cache_files || 0} 个`;
    fetchInsights(7);
  } catch (err) {
    historyStatus.textContent = `清空后端历史失败: ${err.message}`;
  }
});

clearLocalHistoryButton.addEventListener("click", () => {
  const ok = window.confirm("仅清空当前浏览器本地历史，是否继续？");
  if (!ok) return;
  clearLocalHistory();
  renderHistory();
  historyStatus.textContent = "已清空本地历史";
});

loadConfig();
applyPrimaryButtonStyles();
updateSelectedFileName();
ensureAnalyzeButtonText();
loadInsightsCollapseState();
applyInsightsCollapsedState();
resetProgress();
initAgentMessages();
updateAgentCharCount();
autoResizeAgentInput();
renderHistory();
fetchRemoteHistory();
fetchInsights(7);
// Pre-populate the four-layer inspector with the current global state so
// users can see Core rules + recurring profile even before sending a turn.
fetchMemorySnapshot();
// Initial overview pull: surfaces recurrence banner + open task list for
// the scene that's already selected when the page loads.
fetchMemoryOverview();
if (agentSceneSelect) {
  const sceneValue = agentSceneSelect.value;
  fetchSceneGuide(sceneValue);
  if (sceneValue) {
    saveLastAgentSceneNotice(sceneValue);
  }
}
