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

let currentSessionId = null;
let activeController = null;

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
    body: JSON.stringify({ title: "新しいチャット" }),
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
  const text = messageInput.value.trim();
  if (!text || !currentSessionId) return;
  messageInput.value = "";
  appendMessage("user", text);
  const assistantDiv = appendMessage("assistant", "");
  assistantDiv.classList.add("thinking");

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
        }
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") throw err;
    if (!full) assistantDiv.textContent = "（停止しました）";
  } finally {
    assistantDiv.classList.remove("thinking");
    activeController = null;
    sendBtn.textContent = "送信";
    sendBtn.classList.remove("stop-mode");
  }
  loadSessions();
});

newChatBtn.addEventListener("click", createSession);

memoryToggleBtn.addEventListener("click", () => {
  memoryPanel.classList.toggle("hidden");
  if (!memoryPanel.classList.contains("hidden")) loadMemory();
});

async function loadMemory() {
  const [statusRes, listRes] = await Promise.all([fetch("/memory/status"), fetch("/memory")]);
  const status = await statusRes.json();
  const items = await listRes.json();

  memoryStatusEl.textContent = `${status.count} / ${status.max_entries} 件`;
  memoryStatusEl.classList.toggle("warning", status.warning);
  if (status.full) memoryStatusEl.textContent += "（容量満杯：新規追加不可、更新のみ）";
  else if (status.warning) memoryStatusEl.textContent += "（容量警告）";

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
  if (!res.ok) alert("記憶の容量が満杯のため追加できません");
  loadMemory();
});

profileToggleBtn.addEventListener("click", () => {
  profilePanel.classList.toggle("hidden");
  if (!profilePanel.classList.contains("hidden")) loadProfile();
});

async function loadProfile() {
  await Promise.all([loadBasicInfo(), loadCareer(), loadEducation()]);
}

async function loadBasicInfo() {
  const res = await fetch("/profile/basic");
  const basic = await res.json();
  profileNameInput.value = basic.name || "";
  profileBirthDateInput.value = basic.birth_date || "";
  profileCurrentCompanyInput.value = basic.current_company || "";
  profileCurrentPositionInput.value = basic.current_position || "";
  profileCurrentSalaryInput.value = basic.current_salary || "";
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
    const companyInput = makeFieldInput(c.company, "会社名");
    const positionInput = makeFieldInput(c.position, "職位");
    const startInput = makeFieldInput(c.start_date, "開始(YYYY-MM)");
    const endInput = makeFieldInput(c.end_date, "終了(YYYY-MM、在籍中は空欄)");
    const salaryInput = makeFieldInput(c.salary, "収入");
    const joiningInput = makeFieldInput(c.reason_for_joining, "入社理由");
    const leavingInput = makeFieldInput(c.reason_for_leaving, "退職理由");
    [companyInput, positionInput, startInput, endInput, salaryInput, joiningInput, leavingInput].forEach((i) =>
      fields.appendChild(i)
    );
    li.appendChild(fields);

    const noteInput = document.createElement("textarea");
    noteInput.rows = 2;
    noteInput.placeholder = "自由記述（その他のエピソードなど）";
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
    saveBtn.textContent = "保存";
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
    const degreeInput = makeFieldInput(e.degree, "学位（学士/修士/博士など）");
    const fieldInput = makeFieldInput(e.field, "専攻");
    const schoolInput = makeFieldInput(e.school, "学校名");
    const yearInput = makeFieldInput(e.graduated_year, "卒業年（YYYY）");
    [degreeInput, fieldInput, schoolInput, yearInput].forEach((i) => fields.appendChild(i));
    li.appendChild(fields);

    const noteInput = document.createElement("textarea");
    noteInput.rows = 2;
    noteInput.placeholder = "自由記述（その他のエピソードなど）";
    noteInput.value = e.note || "";
    li.appendChild(noteInput);

    const actions = document.createElement("div");
    actions.className = "entry-actions";

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = "保存";
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
    }),
  });
});

profileImportForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = profileImportInput.value.trim();
  if (!text) return;
  const btn = profileImportForm.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = "読み込み中...";
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
    btn.textContent = "読み込んで登録";
  }
});

profileImportFileForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = profileImportFileInput.files[0];
  if (!file) return;
  const btn = profileImportFileForm.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = "読み込み中...";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/profile/import/file", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "読み込みに失敗しました");
      return;
    }
    profileImportFileInput.value = "";
    await loadProfile();
  } finally {
    btn.disabled = false;
    btn.textContent = "ファイルから読み込んで登録";
  }
});

loadSessions();
