const HISTORY_KEY_PREFIX = "company-qa-system.chat-history";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("question-input");
const sendButtonEl = document.getElementById("send-button");
const statusTextEl = document.getElementById("status-text");
const welcomeTemplate = document.getElementById("welcome-template");
const logoutButtonEl = document.getElementById("logout-button");
const currentUserNameEl = document.getElementById("current-user-name");
const adminLinkEl = document.getElementById("admin-link");

let isSending = false;
let typingTimer = null;
let typingQueue = [];
let activeAssistantMessage = null;
let activeAssistantContent = "";
let currentUser = null;

function storageKey() {
  return `${HISTORY_KEY_PREFIX}.${currentUser?.username || "anonymous"}`;
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setStatus(message, isError = false) {
  statusTextEl.textContent = message;
  statusTextEl.classList.toggle("error", isError);
}

function autosize() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function readMessages() {
  try {
    const raw = localStorage.getItem(storageKey());
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveMessages(messages) {
  localStorage.setItem(storageKey(), JSON.stringify(messages));
}

function createReferencesElement(references) {
  const details = document.createElement("details");
  details.className = "references";
  const summary = document.createElement("summary");
  summary.textContent = "查看来源";
  const list = document.createElement("ul");
  for (const reference of references) {
    const item = document.createElement("li");
    item.textContent = reference;
    list.appendChild(item);
  }
  details.append(summary, list);
  return details;
}

function createMessageElement(message) {
  const article = document.createElement("article");
  article.className = `message ${message.role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const role = document.createElement("p");
  role.className = "message-role";
  role.textContent = message.role === "user" ? "你" : "助手";

  const content = document.createElement("p");
  content.className = "message-content";
  content.textContent = message.content;

  const time = document.createElement("time");
  time.className = "message-time";
  time.dateTime = message.timestamp;
  time.textContent = formatTime(message.timestamp);

  bubble.append(role, content);
  if (message.role === "assistant" && Array.isArray(message.references) && message.references.length > 0) {
    bubble.appendChild(createReferencesElement(message.references));
  }
  bubble.appendChild(time);
  article.appendChild(bubble);
  return article;
}

function renderMessages(messages) {
  messagesEl.innerHTML = "";
  if (messages.length === 0) {
    messagesEl.appendChild(welcomeTemplate.content.cloneNode(true));
    return;
  }
  for (const message of messages) {
    messagesEl.appendChild(createMessageElement(message));
  }
  scrollToBottom();
}

function appendMessage(message) {
  const messages = readMessages();
  messages.push(message);
  saveMessages(messages);
  renderMessages(messages);
}

function setSendingState(sending) {
  isSending = sending;
  inputEl.disabled = sending;
  sendButtonEl.disabled = sending;
  sendButtonEl.textContent = sending ? "思考中..." : "发送";
}

function queueTyping(text) {
  typingQueue.push(...text.split(""));
  if (!typingTimer) {
    typingTimer = window.setInterval(() => {
      if (!activeAssistantMessage) {
        clearInterval(typingTimer);
        typingTimer = null;
        return;
      }
      const contentEl = activeAssistantMessage.querySelector(".message-content");
      const bubbleEl = activeAssistantMessage.querySelector(".bubble");
      if (typingQueue.length === 0) {
        if (!isSending) {
          bubbleEl.classList.remove("streaming");
          clearInterval(typingTimer);
          typingTimer = null;
        }
        return;
      }
      activeAssistantContent += typingQueue.shift();
      contentEl.textContent = activeAssistantContent;
      bubbleEl.classList.remove("loading");
      bubbleEl.classList.add("streaming");
      scrollToBottom();
    }, 18);
  }
}

function buildLoadingMessage() {
  const article = document.createElement("article");
  article.className = "message assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble loading";

  const role = document.createElement("p");
  role.className = "message-role";
  role.textContent = "助手";

  const content = document.createElement("div");
  content.className = "message-content skeleton-lines";
  content.innerHTML = `
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
    <div class="skeleton-line short"></div>
  `;

  const time = document.createElement("time");
  time.className = "message-time";
  time.dateTime = new Date().toISOString();
  time.textContent = "正在生成回答";

  bubble.append(role, content, time);
  article.appendChild(bubble);
  return article;
}

function startAssistantStream() {
  activeAssistantContent = "";
  typingQueue = [];
  activeAssistantMessage = buildLoadingMessage();
  messagesEl.appendChild(activeAssistantMessage);
  scrollToBottom();
}

function finalizeAssistantMessage(references) {
  if (!activeAssistantMessage) {
    return;
  }
  const bubbleEl = activeAssistantMessage.querySelector(".bubble");
  const contentEl = activeAssistantMessage.querySelector(".message-content");
  const timeEl = activeAssistantMessage.querySelector(".message-time");
  bubbleEl.classList.remove("loading", "streaming");
  contentEl.textContent = activeAssistantContent || "未生成回答。";
  timeEl.dateTime = new Date().toISOString();
  timeEl.textContent = formatTime(timeEl.dateTime);
  if (Array.isArray(references) && references.length > 0) {
    bubbleEl.appendChild(createReferencesElement(references));
  }

  appendMessage({
    role: "assistant",
    content: activeAssistantContent || "未生成回答。",
    references: Array.isArray(references) ? references : [],
    timestamp: timeEl.dateTime,
  });
  activeAssistantMessage = null;
  activeAssistantContent = "";
}

function abortAssistantMessage(errorMessage) {
  const content = `当前无法完成回答：${errorMessage}`;
  if (activeAssistantMessage) {
    const bubbleEl = activeAssistantMessage.querySelector(".bubble");
    const contentEl = activeAssistantMessage.querySelector(".message-content");
    const timeEl = activeAssistantMessage.querySelector(".message-time");
    bubbleEl.classList.remove("loading", "streaming");
    contentEl.textContent = content;
    timeEl.dateTime = new Date().toISOString();
    timeEl.textContent = formatTime(timeEl.dateTime);
    activeAssistantMessage = null;
    activeAssistantContent = "";
  }
  appendMessage({
    role: "assistant",
    content,
    references: [],
    timestamp: new Date().toISOString(),
  });
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    localStorage.removeItem(storageKey());
    window.location.href = "/login";
    throw new Error("登录已失效，请重新登录。");
  }
  if (response.status === 403) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : "没有权限执行该操作。");
  }
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : "请求失败，请稍后重试。");
  }
  return payload;
}

async function streamQuestion(question) {
  const response = await fetch("/api/v1/qa/stream", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("登录已失效，请重新登录。");
  }
  if (response.status === 403) {
    throw new Error("没有权限访问问答接口。");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(typeof payload.detail === "string" ? payload.detail : "请求失败，请稍后重试。");
  }
  if (!response.body) {
    throw new Error("当前环境不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let references = [];

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const rawEvent of events) {
      if (!rawEvent.trim()) {
        continue;
      }
      let eventName = "message";
      let dataText = "";
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        }
        if (line.startsWith("data:")) {
          dataText += line.slice(5).trim();
        }
      }
      const payload = dataText ? JSON.parse(dataText) : null;
      if (eventName === "token" && typeof payload === "string") {
        queueTyping(payload);
      } else if (eventName === "references" && Array.isArray(payload)) {
        references = payload;
      } else if (eventName === "error" && typeof payload === "string") {
        throw new Error(payload);
      } else if (eventName === "done") {
        while (typingQueue.length > 0) {
          await new Promise((resolve) => window.setTimeout(resolve, 16));
        }
        return references;
      }
    }
    if (done) {
      break;
    }
  }
  return references;
}

async function submitQuestion(question) {
  if (isSending) {
    return;
  }
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion) {
    setStatus("请输入问题后再发送。", true);
    inputEl.focus();
    return;
  }

  appendMessage({
    role: "user",
    content: trimmedQuestion,
    references: [],
    timestamp: new Date().toISOString(),
  });
  inputEl.value = "";
  autosize();
  setStatus("正在查询知识库并生成回答...");
  setSendingState(true);
  startAssistantStream();
  try {
    const references = await streamQuestion(trimmedQuestion);
    finalizeAssistantMessage(references);
    setStatus("回答完成。");
  } catch (error) {
    abortAssistantMessage(error.message);
    setStatus(error.message, true);
  } finally {
    setSendingState(false);
    inputEl.focus();
  }
}

async function loadCurrentUser() {
  const user = await requestJson("/api/v1/auth/me", { method: "GET", headers: {} });
  currentUser = user;
  currentUserNameEl.textContent = `${user.display_name} (${user.username})`;
  adminLinkEl.classList.toggle("hidden", user.role !== "admin");
  renderMessages(readMessages());
}

async function logout() {
  try {
    await requestJson("/api/v1/auth/logout", { method: "POST" });
  } catch {
    // ignore logout issues
  }
  localStorage.removeItem(storageKey());
  window.location.href = "/login";
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitQuestion(inputEl.value);
});

inputEl.addEventListener("input", autosize);
inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-question]");
  if (!button) {
    return;
  }
  const question = button.getAttribute("data-question") || "";
  inputEl.value = question;
  autosize();
  await submitQuestion(question);
});

logoutButtonEl.addEventListener("click", logout);

loadCurrentUser().catch((error) => {
  setStatus(error.message, true);
});
autosize();
