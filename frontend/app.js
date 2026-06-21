const sessionListEl = document.getElementById("session-list");
const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const searchModeCheckbox = document.getElementById("search-mode-checkbox");
const newChatBtn = document.getElementById("new-chat-btn");
const memoryToggleBtn = document.getElementById("memory-toggle-btn");
const memoryPanel = document.getElementById("memory-panel");
const memoryListEl = document.getElementById("memory-list");
const memoryStatusEl = document.getElementById("memory-status");
const memoryAddForm = document.getElementById("memory-add-form");
const memoryAddInput = document.getElementById("memory-add-input");
const profileToggleBtn = document.getElementById("profile-toggle-btn");
const profilePanel = document.getElementById("profile-panel");
const profileBasicForm = document.getElementById("profile-basic-form");
const profileNameInput = document.getElementById("profile-name");
const profileBirthDateInput = document.getElementById("profile-birth-date");
const profileCurrentCompanyInput = document.getElementById("profile-current-company");
const profileCurrentPositionInput = document.getElementById("profile-current-position");
const profileCurrentSalaryInput = document.getElementById("profile-current-salary");
const profileGenderInput = document.getElementById("profile-gender");
const profileReligionInput = document.getElementById("profile-religion");
const profileSexualOrientationInput = document.getElementById("profile-sexual-orientation");
const profileRaceInput = document.getElementById("profile-race");
const profileHometownInput = document.getElementById("profile-hometown");
const profileResidenceCountryInput = document.getElementById("profile-residence-country");
const profileNationalityInput = document.getElementById("profile-nationality");
const residenceListEl = document.getElementById("residence-list");
const residenceAddToggleBtn = document.getElementById("residence-add-toggle-btn");
const residenceAddForm = document.getElementById("residence-add-form");
const residencePlaceInput = document.getElementById("residence-place");
const residencePeriodInput = document.getElementById("residence-period");
const residenceNoteInput = document.getElementById("residence-note");
const careerListEl = document.getElementById("career-list");
const educationListEl = document.getElementById("education-list");
const careerAddToggleBtn = document.getElementById("career-add-toggle-btn");
const careerAddForm = document.getElementById("career-add-form");
const careerCompanyInput = document.getElementById("career-company");
const careerPositionInput = document.getElementById("career-position");
const careerStartDateInput = document.getElementById("career-start-date");
const careerEndDateInput = document.getElementById("career-end-date");
const careerSalaryInput = document.getElementById("career-salary");
const careerReasonJoiningInput = document.getElementById("career-reason-joining");
const careerReasonLeavingInput = document.getElementById("career-reason-leaving");
const careerNoteInput = document.getElementById("career-note");
const educationAddToggleBtn = document.getElementById("education-add-toggle-btn");
const educationAddForm = document.getElementById("education-add-form");
const educationDegreeInput = document.getElementById("education-degree");
const educationFieldInput = document.getElementById("education-field");
const educationSchoolInput = document.getElementById("education-school");
const educationGraduatedYearInput = document.getElementById("education-graduated-year");
const educationNoteInput = document.getElementById("education-note");
const profileImportForm = document.getElementById("profile-import-form");
const profileImportInput = document.getElementById("profile-import-input");
const profileImportFileForm = document.getElementById("profile-import-file-form");
const profileImportFileInput = document.getElementById("profile-import-file-input");
const langSelect = document.getElementById("lang-select");
const modelSelect = document.getElementById("model-select");
const modelStatus = document.getElementById("model-status");
const memoryCloseBtn = document.getElementById("memory-close-btn");
const memoryResizeHandle = document.getElementById("memory-resize-handle");
const profileCloseBtn = document.getElementById("profile-close-btn");
const profileResizeHandle = document.getElementById("profile-resize-handle");
const progressToggleBtn = document.getElementById("progress-toggle-btn");
const progressPanel = document.getElementById("progress-panel");
const progressListEl = document.getElementById("progress-list");
const progressCloseBtn = document.getElementById("progress-close-btn");
const progressResizeHandle = document.getElementById("progress-resize-handle");

const t = window.I18N ? window.I18N.t : (key) => key;

let currentSessionId = null;
let activeController = null;

if (window.I18N && langSelect) {
  langSelect.value = window.I18N.getLangSetting();
  window.I18N.applyTranslations();
  langSelect.addEventListener("change", () => {
    window.I18N.setLangSetting(langSelect.value);
    window.I18N.applyTranslations();
  });
} else if (window.I18N) {
  window.I18N.applyTranslations();
}

const MODEL_STORAGE_KEY = "guchirin-model";

// tool calling対応が確認済みのモデル候補。未ダウンロードでも選択肢として出し、選んだら自動取得する
const MODEL_SUGGESTIONS = [
  "llama3.1:8b", "llama3.2:3b", "llama3.2:1b", "llama3.3:70b",
  "qwen2.5:7b", "qwen2.5-coder:7b", "qwen3:4b", "qwen3:8b", "qwen3:14b",
  "gemma4:e2b", "gemma4:e4b", "gemma4:12b", "gemma4:26b",
  "mistral:7b", "mistral-nemo:12b", "mistral-small:24b",
  "command-r:35b", "hermes3:8b", "devstral:24b",
];

let installedModels = [];
let defaultModel = "";

function renderModelOptions(selectedValue) {
  modelSelect.innerHTML = "";
  const names = [...new Set([...installedModels, ...MODEL_SUGGESTIONS])];
  for (const name of names) {
    const opt = document.createElement("option");
    opt.value = name;
    const installed = installedModels.includes(name);
    opt.textContent = installed ? name : `${name}${t("model_not_downloaded_suffix")}`;
    opt.dataset.installed = installed ? "1" : "0";
    modelSelect.appendChild(opt);
  }
  modelSelect.value = names.includes(selectedValue) ? selectedValue : defaultModel;
}

async function loadModels(selectedValue) {
  const res = await fetch("/models");
  const data = await res.json();
  installedModels = data.models;
  defaultModel = data.default;
  renderModelOptions(selectedValue ?? localStorage.getItem(MODEL_STORAGE_KEY) ?? defaultModel);
  modelSelect.disabled = false;
}

async function downloadModel(model) {
  modelSelect.disabled = true;
  modelStatus.classList.remove("error");
  try {
    const res = await fetch("/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let failed = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line) continue;
        const data = JSON.parse(line);
        if (data.type === "error") {
          failed = true;
          modelStatus.classList.add("error");
          modelStatus.textContent = t("model_download_error", { error: data.text });
        } else {
          let status = data.status || "";
          if (data.total && data.completed) {
            status += ` ${Math.floor((data.completed / data.total) * 100)}%`;
          }
          modelStatus.textContent = t("model_download_progress", { model, status });
        }
      }
    }
    if (failed) {
      renderModelOptions(localStorage.getItem(MODEL_STORAGE_KEY) ?? defaultModel);
      return;
    }
    modelStatus.textContent = t("model_download_done", { model });
    await loadModels(model);
    localStorage.setItem(MODEL_STORAGE_KEY, model);
  } finally {
    modelSelect.disabled = false;
  }
}

modelSelect.addEventListener("change", () => {
  const model = modelSelect.value;
  const opt = modelSelect.selectedOptions[0];
  if (opt && opt.dataset.installed === "1") {
    localStorage.setItem(MODEL_STORAGE_KEY, model);
    modelStatus.textContent = "";
    modelStatus.classList.remove("error");
  } else {
    downloadModel(model);
  }
});

loadModels();

async function loadSessions() {
  const res = await fetch("/sessions");
  const sessions = await res.json();
  sessionListEl.innerHTML = "";
  for (const s of sessions) {
    const li = document.createElement("li");
    li.textContent = s.title;
    li.dataset.id = s.id;
    if (s.id === currentSessionId) li.classList.add("active");
    li.addEventListener("click", () => loadSession(s.id));

    const delBtn = document.createElement("button");
    delBtn.textContent = "×";
    delBtn.className = "delete-btn";
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await fetch(`/sessions/${s.id}`, { method: "DELETE" });
      if (currentSessionId === s.id) {
        currentSessionId = null;
        messagesEl.innerHTML = "";
      }
      loadSessions();
    });
    li.appendChild(delBtn);
    sessionListEl.appendChild(li);
  }
  if (sessions.length === 0) {
    await createSession();
  } else if (!currentSessionId) {
    await loadSession(sessions[0].id);
  }
}

async function createSession() {
  const res = await fetch("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: t("default_session_title") }),
  });
  const session = await res.json();
  currentSessionId = session.id;
  messagesEl.innerHTML = "";
  await loadSessions();
}

async function loadSession(sessionId) {
  currentSessionId = sessionId;
  const res = await fetch(`/sessions/${sessionId}`);
  const msgs = await res.json();
  messagesEl.innerHTML = "";
  for (const m of msgs) appendMessage(m.role, m.content);
  await loadSessions();
}

function appendMessage(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = content;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (activeController) {
    activeController.abort();
    return;
  }
  if (modelSelect.disabled) return;
  const text = messageInput.value.trim();
  if (!text || !currentSessionId) return;
  messageInput.value = "";
  appendMessage("user", text);
  const assistantDiv = appendMessage("assistant", "");
  assistantDiv.classList.add("thinking");
  progressListEl.innerHTML = "";
  let progressThinkingLi = null;

  activeController = new AbortController();
  sendBtn.textContent = "■";
  sendBtn.classList.add("stop-mode");

  let full = "";
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        message: text,
        search_mode: searchModeCheckbox.checked,
        model: modelSelect.value,
      }),
      signal: activeController.signal,
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line) continue;
        const data = JSON.parse(line);
        if (data.type === "status") {
          assistantDiv.classList.add("thinking");
          assistantDiv.textContent = data.text;
        } else if (data.type === "content") {
          assistantDiv.classList.remove("thinking");
          full += data.text;
          assistantDiv.textContent = full;
        } else if (data.type === "thinking") {
          if (!progressThinkingLi) {
            progressThinkingLi = appendProgressEntry(t("progress_thinking_label"), "", { thinking: true });
          }
          progressThinkingLi.querySelector(".progress-detail").textContent += data.text;
        } else if (data.type === "tool_call") {
          progressThinkingLi = null;
          const labelKey = PROGRESS_TOOL_LABEL_KEYS[data.name];
          const label = labelKey ? t(labelKey) : data.name;
          const detail = Array.isArray(data.detail) ? data.detail.join("、") : data.detail || "";
          appendProgressEntry(label, detail);
        }
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") throw err;
    if (!full) assistantDiv.textContent = t("stopped_message");
  } finally {
    assistantDiv.classList.remove("thinking");
    activeController = null;
    sendBtn.textContent = t("send_btn");
    sendBtn.classList.remove("stop-mode");
  }
  loadSessions();
});

newChatBtn.addEventListener("click", createSession);

function makeResizable(handle, panel, storageKey) {
  const savedWidth = localStorage.getItem(storageKey);
  if (savedWidth) panel.style.width = `${savedWidth}px`;

  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = panel.getBoundingClientRect().width;
    handle.classList.add("dragging");
    document.body.style.cursor = "ew-resize";

    function onMouseMove(moveEvent) {
      const newWidth = startWidth - (moveEvent.clientX - startX);
      panel.style.width = `${newWidth}px`;
    }
    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      handle.classList.remove("dragging");
      document.body.style.cursor = "";
      localStorage.setItem(storageKey, Math.round(panel.getBoundingClientRect().width));
    }
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  });
}

makeResizable(memoryResizeHandle, memoryPanel, "guchirin-memory-panel-width");
makeResizable(profileResizeHandle, profilePanel, "guchirin-profile-panel-width");
makeResizable(progressResizeHandle, progressPanel, "guchirin-progress-panel-width");

memoryCloseBtn.addEventListener("click", () => {
  memoryPanel.classList.add("hidden");
});

profileCloseBtn.addEventListener("click", () => {
  profilePanel.classList.add("hidden");
});

progressCloseBtn.addEventListener("click", () => {
  progressPanel.classList.add("hidden");
});

progressToggleBtn.addEventListener("click", () => {
  progressPanel.classList.toggle("hidden");
});

const PROGRESS_TOOL_LABEL_KEYS = {
  web_search: "progress_tool_web_search",
  retrieve_memory: "progress_tool_retrieve_memory",
  retrieve_profile: "progress_tool_retrieve_profile",
};

function appendProgressEntry(label, detail, { thinking = false } = {}) {
  const li = document.createElement("li");
  if (thinking) li.classList.add("progress-thinking");
  const labelSpan = document.createElement("span");
  labelSpan.className = "progress-label";
  labelSpan.textContent = label;
  const detailSpan = document.createElement("span");
  detailSpan.className = "progress-detail";
  detailSpan.textContent = detail;
  li.appendChild(labelSpan);
  li.appendChild(detailSpan);
  progressListEl.appendChild(li);
  return li;
}

memoryToggleBtn.addEventListener("click", () => {
  memoryPanel.classList.toggle("hidden");
  if (!memoryPanel.classList.contains("hidden")) loadMemory();
});

async function loadMemory() {
  const [statusRes, listRes] = await Promise.all([fetch("/memory/status"), fetch("/memory")]);
  const status = await statusRes.json();
  const items = await listRes.json();

  memoryStatusEl.textContent = t("memory_status_count", { count: status.count, max: status.max_entries });
  memoryStatusEl.classList.toggle("warning", status.warning);
  if (status.full) memoryStatusEl.textContent += t("memory_status_full");
  else if (status.warning) memoryStatusEl.textContent += t("memory_status_warning");

  memoryListEl.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = item.text;
    li.appendChild(span);

    const delBtn = document.createElement("button");
    delBtn.textContent = "×";
    delBtn.className = "delete-btn";
    delBtn.addEventListener("click", async () => {
      await fetch(`/memory/${item.id}`, { method: "DELETE" });
      loadMemory();
    });
    li.appendChild(delBtn);
    memoryListEl.appendChild(li);
  }
}

memoryAddForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = memoryAddInput.value.trim();
  if (!text) return;
  memoryAddInput.value = "";
  const res = await fetch("/memory", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) alert(t("memory_full_alert"));
  loadMemory();
});

profileToggleBtn.addEventListener("click", () => {
  profilePanel.classList.toggle("hidden");
  if (!profilePanel.classList.contains("hidden")) loadProfile();
});

async function loadProfile() {
  await Promise.all([loadBasicInfo(), loadCareer(), loadEducation(), loadResidence()]);
}

async function loadBasicInfo() {
  const res = await fetch("/profile/basic");
  const basic = await res.json();
  profileNameInput.value = basic.name || "";
  profileBirthDateInput.value = basic.birth_date || "";
  profileCurrentCompanyInput.value = basic.current_company || "";
  profileCurrentPositionInput.value = basic.current_position || "";
  profileCurrentSalaryInput.value = basic.current_salary || "";
  profileGenderInput.value = basic.gender || "";
  profileReligionInput.value = basic.religion || "";
  profileSexualOrientationInput.value = basic.sexual_orientation || "";
  profileRaceInput.value = basic.race || "";
  profileHometownInput.value = basic.hometown || "";
  profileResidenceCountryInput.value = basic.residence_country || "";
  profileNationalityInput.value = basic.nationality || "";
}

function makeFieldInput(value, placeholder) {
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.placeholder = placeholder;
  return input;
}

async function loadCareer() {
  const res = await fetch("/profile/career");
  const items = await res.json();
  careerListEl.innerHTML = "";
  items.forEach((c, idx) => {
    const li = document.createElement("li");

    const fields = document.createElement("div");
    fields.className = "entry-fields";
    const companyInput = makeFieldInput(c.company, t("ph_company"));
    const positionInput = makeFieldInput(c.position, t("ph_position"));
    const startInput = makeFieldInput(c.start_date, t("ph_start_date"));
    const endInput = makeFieldInput(c.end_date, t("ph_end_date"));
    const salaryInput = makeFieldInput(c.salary, t("ph_salary"));
    const joiningInput = makeFieldInput(c.reason_for_joining, t("ph_reason_joining"));
    const leavingInput = makeFieldInput(c.reason_for_leaving, t("ph_reason_leaving"));
    [companyInput, positionInput, startInput, endInput, salaryInput, joiningInput, leavingInput].forEach((i) =>
      fields.appendChild(i)
    );
    li.appendChild(fields);

    const noteInput = document.createElement("textarea");
    noteInput.rows = 2;
    noteInput.placeholder = t("ph_note");
    noteInput.value = c.note || "";
    li.appendChild(noteInput);

    const actions = document.createElement("div");
    actions.className = "entry-actions";

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.textContent = "↑";
    upBtn.disabled = idx === 0;
    upBtn.addEventListener("click", async () => {
      await fetch(`/profile/career/${c.id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction: "up" }),
      });
      loadCareer();
    });

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.textContent = "↓";
    downBtn.disabled = idx === items.length - 1;
    downBtn.addEventListener("click", async () => {
      await fetch(`/profile/career/${c.id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction: "down" }),
      });
      loadCareer();
    });

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = t("save_btn");
    saveBtn.addEventListener("click", async () => {
      await fetch(`/profile/career/${c.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: companyInput.value.trim(),
          position: positionInput.value.trim(),
          start_date: startInput.value.trim(),
          end_date: endInput.value.trim(),
          salary: salaryInput.value.trim(),
          reason_for_joining: joiningInput.value.trim(),
          reason_for_leaving: leavingInput.value.trim(),
          note: noteInput.value.trim(),
        }),
      });
      loadCareer();
    });

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "×";
    delBtn.className = "delete-btn";
    delBtn.addEventListener("click", async () => {
      await fetch(`/profile/career/${c.id}`, { method: "DELETE" });
      loadCareer();
    });

    actions.appendChild(upBtn);
    actions.appendChild(downBtn);
    actions.appendChild(saveBtn);
    actions.appendChild(delBtn);
    li.appendChild(actions);

    careerListEl.appendChild(li);
  });
}

async function loadEducation() {
  const res = await fetch("/profile/education");
  const items = await res.json();
  educationListEl.innerHTML = "";
  for (const e of items) {
    const li = document.createElement("li");

    const fields = document.createElement("div");
    fields.className = "entry-fields";
    const degreeInput = makeFieldInput(e.degree, t("ph_degree"));
    const fieldInput = makeFieldInput(e.field, t("ph_field"));
    const schoolInput = makeFieldInput(e.school, t("ph_school"));
    const yearInput = makeFieldInput(e.graduated_year, t("ph_graduated_year"));
    [degreeInput, fieldInput, schoolInput, yearInput].forEach((i) => fields.appendChild(i));
    li.appendChild(fields);

    const noteInput = document.createElement("textarea");
    noteInput.rows = 2;
    noteInput.placeholder = t("ph_note");
    noteInput.value = e.note || "";
    li.appendChild(noteInput);

    const actions = document.createElement("div");
    actions.className = "entry-actions";

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = t("save_btn");
    saveBtn.addEventListener("click", async () => {
      await fetch(`/profile/education/${e.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          degree: degreeInput.value.trim(),
          field: fieldInput.value.trim(),
          school: schoolInput.value.trim(),
          graduated_year: yearInput.value.trim(),
          note: noteInput.value.trim(),
        }),
      });
      loadEducation();
    });

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "×";
    delBtn.className = "delete-btn";
    delBtn.addEventListener("click", async () => {
      await fetch(`/profile/education/${e.id}`, { method: "DELETE" });
      loadEducation();
    });

    actions.appendChild(saveBtn);
    actions.appendChild(delBtn);
    li.appendChild(actions);

    educationListEl.appendChild(li);
  }
}

async function loadResidence() {
  const res = await fetch("/profile/residence");
  const items = await res.json();
  residenceListEl.innerHTML = "";
  for (const r of items) {
    const li = document.createElement("li");

    const fields = document.createElement("div");
    fields.className = "entry-fields";
    const placeInput = makeFieldInput(r.place, t("ph_residence_place"));
    const periodInput = makeFieldInput(r.period, t("ph_residence_period"));
    [placeInput, periodInput].forEach((i) => fields.appendChild(i));
    li.appendChild(fields);

    const noteInput = document.createElement("textarea");
    noteInput.rows = 2;
    noteInput.placeholder = t("ph_note");
    noteInput.value = r.note || "";
    li.appendChild(noteInput);

    const actions = document.createElement("div");
    actions.className = "entry-actions";

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = t("save_btn");
    saveBtn.addEventListener("click", async () => {
      await fetch(`/profile/residence/${r.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          place: placeInput.value.trim(),
          period: periodInput.value.trim(),
          note: noteInput.value.trim(),
        }),
      });
      loadResidence();
    });

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "×";
    delBtn.className = "delete-btn";
    delBtn.addEventListener("click", async () => {
      await fetch(`/profile/residence/${r.id}`, { method: "DELETE" });
      loadResidence();
    });

    actions.appendChild(saveBtn);
    actions.appendChild(delBtn);
    li.appendChild(actions);

    residenceListEl.appendChild(li);
  }
}

residenceAddToggleBtn.addEventListener("click", () => {
  residenceAddForm.classList.toggle("hidden");
});

residenceAddForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetch("/profile/residence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      place: residencePlaceInput.value.trim(),
      period: residencePeriodInput.value.trim(),
      note: residenceNoteInput.value.trim(),
    }),
  });
  residenceAddForm.reset();
  residenceAddForm.classList.add("hidden");
  loadResidence();
});

careerAddToggleBtn.addEventListener("click", () => {
  careerAddForm.classList.toggle("hidden");
});

careerAddForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetch("/profile/career", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company: careerCompanyInput.value.trim(),
      position: careerPositionInput.value.trim(),
      start_date: careerStartDateInput.value.trim(),
      end_date: careerEndDateInput.value.trim(),
      salary: careerSalaryInput.value.trim(),
      reason_for_joining: careerReasonJoiningInput.value.trim(),
      reason_for_leaving: careerReasonLeavingInput.value.trim(),
      note: careerNoteInput.value.trim(),
    }),
  });
  careerAddForm.reset();
  careerAddForm.classList.add("hidden");
  loadCareer();
});

educationAddToggleBtn.addEventListener("click", () => {
  educationAddForm.classList.toggle("hidden");
});

educationAddForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetch("/profile/education", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      degree: educationDegreeInput.value.trim(),
      field: educationFieldInput.value.trim(),
      school: educationSchoolInput.value.trim(),
      graduated_year: educationGraduatedYearInput.value.trim(),
      note: educationNoteInput.value.trim(),
    }),
  });
  educationAddForm.reset();
  educationAddForm.classList.add("hidden");
  loadEducation();
});

profileBasicForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetch("/profile/basic", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: profileNameInput.value.trim(),
      birth_date: profileBirthDateInput.value.trim(),
      current_company: profileCurrentCompanyInput.value.trim(),
      current_position: profileCurrentPositionInput.value.trim(),
      current_salary: profileCurrentSalaryInput.value.trim(),
      gender: profileGenderInput.value.trim(),
      religion: profileReligionInput.value.trim(),
      sexual_orientation: profileSexualOrientationInput.value.trim(),
      race: profileRaceInput.value.trim(),
      hometown: profileHometownInput.value.trim(),
      residence_country: profileResidenceCountryInput.value.trim(),
      nationality: profileNationalityInput.value.trim(),
    }),
  });
});

profileImportForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = profileImportInput.value.trim();
  if (!text) return;
  const btn = profileImportForm.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = t("import_submit_loading");
  try {
    await fetch("/profile/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    profileImportInput.value = "";
    await loadProfile();
  } finally {
    btn.disabled = false;
    btn.textContent = t("import_submit");
  }
});

profileImportFileForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = profileImportFileInput.files[0];
  if (!file) return;
  const btn = profileImportFileForm.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = t("import_submit_loading");
  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/profile/import/file", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || t("import_file_failed"));
      return;
    }
    profileImportFileInput.value = "";
    await loadProfile();
  } finally {
    btn.disabled = false;
    btn.textContent = t("import_file_submit");
  }
});

loadSessions();
