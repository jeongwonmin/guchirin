const sessionListEl = document.getElementById("session-list");
const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const searchModeCheckbox = document.getElementById("search-mode-checkbox");
const newChatBtn = document.getElementById("new-chat-btn");
const memoryToggleBtn = document.getElementById("memory-toggle-btn");
const memoryPanel = document.getElementById("memory-panel");
const memoryListEl = document.getElementById("memory-list");
const memoryStatusEl = document.getElementById("memory-status");
const memoryAddForm = document.getElementById("memory-add-form");
const memoryAddInput = document.getElementById("memory-add-input");

let currentSessionId = null;

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
  const text = messageInput.value.trim();
  if (!text || !currentSessionId) return;
  messageInput.value = "";
  appendMessage("user", text);
  const assistantDiv = appendMessage("assistant", "");
  assistantDiv.classList.add("thinking");

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: currentSessionId,
      message: text,
      search_mode: searchModeCheckbox.checked,
    }),
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";
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
  assistantDiv.classList.remove("thinking");
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

loadSessions();
