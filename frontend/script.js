/**
 * script.js
 * Frontend logic for Animatrix:
 * - JWT authentication management & apiFetch wrapper
 * - Chat interface and message stream rendering
 * - Task creation and 2-second interval polling
 * - Secure video asset retrieval via Blob and Object URL
 * - Task history loading and inspection
 * - XSS-safe DOM population
 */

// Application State
const state = {
  token: localStorage.getItem("animatrix_token") || null,
  username: localStorage.getItem("animatrix_username") || null,
  activeTaskId: null,
  pollingIntervalId: null,
  isGenerating: false,
};

// DOM Elements
const authScreen = document.getElementById("auth-screen");
const mainScreen = document.getElementById("main-screen");
const tabLoginBtn = document.getElementById("tab-login-btn");
const tabRegisterBtn = document.getElementById("tab-register-btn");
const authForm = document.getElementById("auth-form");
const authUsernameInput = document.getElementById("auth-username");
const authPasswordInput = document.getElementById("auth-password");
const authSubmitBtn = document.getElementById("auth-submit-btn");
const authErrorBanner = document.getElementById("auth-error");
const googleAuthContainer = document.getElementById("google-auth-container");

const userDisplayName = document.getElementById("user-display-name");
const userAvatarInitial = document.getElementById("user-avatar-initial");
const logoutBtn = document.getElementById("logout-btn");
const newAnimationBtn = document.getElementById("new-animation-btn");
const historyList = document.getElementById("history-list");

const chatMessages = document.getElementById("chat-messages");
const welcomeHero = document.getElementById("welcome-hero");
const chatForm = document.getElementById("chat-form");
const promptInput = document.getElementById("prompt-input");
const sendBtn = document.getElementById("send-btn");

let currentAuthMode = "login"; // "login" | "register"


// ============================================================================
// Secure API Fetch Helper
// ============================================================================

/**
 * apiFetch: Centralized HTTP client wrapper.
 * Automatically injects the JWT Bearer token from localStorage.
 * Catches 401 Unauthorized errors to clear credentials and redirect to login.
 */
async function apiFetch(url, options = {}) {
  const headers = { ...options.headers };

  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  // Set default JSON Content-Type if sending a body
  if (options.body && typeof options.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    console.warn("[Auth] Session expired or invalid token. Redirecting to login.");
    handleLogout();
    throw new Error("Unauthorized. Please log in again.");
  }

  return response;
}


// ============================================================================
// Authentication UI & Actions
// ============================================================================

function switchAuthTab(mode) {
  currentAuthMode = mode;
  authErrorBanner.classList.add("hidden");
  authErrorBanner.textContent = "";

  if (mode === "login") {
    tabLoginBtn.classList.add("active");
    tabRegisterBtn.classList.remove("active");
    authSubmitBtn.textContent = "Log In";
  } else {
    tabRegisterBtn.classList.add("active");
    tabLoginBtn.classList.remove("active");
    authSubmitBtn.textContent = "Create Account";
  }
}

tabLoginBtn.addEventListener("click", () => switchAuthTab("login"));
tabRegisterBtn.addEventListener("click", () => switchAuthTab("register"));

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  authErrorBanner.classList.add("hidden");
  authErrorBanner.textContent = "";

  const username = authUsernameInput.value.trim();
  const password = authPasswordInput.value;

  if (!username || !password) {
    showAuthError("Please provide both username and password.");
    return;
  }

  if (currentAuthMode === "register" && password.length < 6) {
    showAuthError("Password must be at least 6 characters long.");
    return;
  }

  const endpoint = currentAuthMode === "login" ? "/api/login" : "/api/register";

  try {
    authSubmitBtn.disabled = true;
    authSubmitBtn.textContent = "Authenticating...";

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Authentication failed.");
    }

    // Success: Save token & username
    saveAuthSession(data.access_token, data.username);
  } catch (err) {
    showAuthError(err.message);
  } finally {
    authSubmitBtn.disabled = false;
    authSubmitBtn.textContent = currentAuthMode === "login" ? "Log In" : "Create Account";
  }
});

function showAuthError(msg) {
  authErrorBanner.textContent = msg;
  authErrorBanner.classList.remove("hidden");
}

function saveAuthSession(token, username) {
  state.token = token;
  state.username = username;
  localStorage.setItem("animatrix_token", token);
  localStorage.setItem("animatrix_username", username);

  authUsernameInput.value = "";
  authPasswordInput.value = "";
  authScreen.classList.add("hidden");
  mainScreen.classList.remove("hidden");

  updateUserProfileUI();
  loadHistory();
}

function handleLogout() {
  if (state.pollingIntervalId) {
    clearInterval(state.pollingIntervalId);
    state.pollingIntervalId = null;
  }
  state.token = null;
  state.username = null;
  state.activeTaskId = null;
  state.isGenerating = false;
  localStorage.removeItem("animatrix_token");
  localStorage.removeItem("animatrix_username");

  mainScreen.classList.add("hidden");
  authScreen.classList.remove("hidden");
  resetChatToWelcome();
}

logoutBtn.addEventListener("click", handleLogout);

function updateUserProfileUI() {
  const name = state.username || "User";
  userDisplayName.textContent = name;
  userAvatarInitial.textContent = name.charAt(0).toUpperCase();
}


// ============================================================================
// Google SSO Integration (Optional)
// ============================================================================

async function checkHealthAndInitGoogle() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return;
    const data = await res.json();

    if (data.google_auth_enabled && window.google) {
      googleAuthContainer.classList.remove("hidden");
      // Render Google Sign-in button if Google library loaded
      /* global google */
      if (typeof google !== "undefined" && google.accounts && google.accounts.id) {
        google.accounts.id.initialize({
          client_id: data.google_client_id || "",
          callback: handleGoogleCredentialResponse,
        });
        google.accounts.id.renderButton(
          document.getElementById("google-signin-btn-wrapper"),
          { theme: "outline", size: "large", width: 340 }
        );
      }
    }
  } catch (err) {
    console.log("[Health] Could not reach health endpoint:", err);
  }
}

async function handleGoogleCredentialResponse(response) {
  try {
    const res = await fetch("/api/google-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Google login failed");
    saveAuthSession(data.access_token, data.username);
  } catch (err) {
    showAuthError(err.message);
  }
}


// ============================================================================
// Chat Stream & UI Helpers
// ============================================================================

function resetChatToWelcome() {
  chatMessages.innerHTML = "";
  if (welcomeHero) {
    chatMessages.appendChild(welcomeHero);
    welcomeHero.classList.remove("hidden");
  }
  state.activeTaskId = null;
}

newAnimationBtn.addEventListener("click", () => {
  if (state.isGenerating) {
    alert("Please wait for the current animation to finish rendering.");
    return;
  }
  resetChatToWelcome();
  promptInput.focus();
});

// Setup example suggestion chips
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    promptInput.value = chip.textContent;
    promptInput.focus();
  });
});

/**
 * Creates an XSS-safe user or assistant chat row.
 */
function createMessageRow(sender, initialContent = "") {
  if (welcomeHero && !welcomeHero.classList.contains("hidden")) {
    welcomeHero.classList.add("hidden");
  }

  const row = document.createElement("div");
  row.className = `message-row ${sender}`;

  const avatar = document.createElement("div");
  avatar.className = `message-avatar ${sender}`;
  avatar.textContent = sender === "user" ? (state.username ? state.username[0].toUpperCase() : "U") : "⚡";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (initialContent) {
    const textNode = document.createElement("p");
    textNode.textContent = initialContent;
    bubble.appendChild(textNode);
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return { row, bubble };
}


// ============================================================================
// Task Generation & Polling Flow
// ============================================================================

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt || state.isGenerating) return;

  await triggerGeneration(prompt);
});

// Handle Enter to submit, Shift+Enter for newline
promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

async function triggerGeneration(prompt) {
  state.isGenerating = true;
  sendBtn.disabled = true;
  promptInput.value = "";

  // 1. Render User Message
  createMessageRow("user", prompt);

  // 2. Render Assistant Message with Loading Spinner
  const { bubble } = createMessageRow("assistant");
  const statusContainer = document.createElement("div");
  statusContainer.className = "processing-status";

  const spinner = document.createElement("div");
  spinner.className = "spinner";

  const statusText = document.createElement("span");
  statusText.textContent = "Consulting Gemini & compiling Manim animation...";

  statusContainer.appendChild(spinner);
  statusContainer.appendChild(statusText);
  bubble.appendChild(statusContainer);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    // 3. Dispatch POST /api/generate
    const res = await apiFetch("/api/generate", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to initiate generation.");
    }

    const taskId = data.task_id;
    state.activeTaskId = taskId;

    // Refresh history sidebar to show pending/processing item
    loadHistory();

    // 4. Poll /api/tasks/{task_id} every 2 seconds
    pollTaskStatus(taskId, bubble, statusText);
  } catch (err) {
    console.error("[Generation Error]", err);
    bubble.innerHTML = "";
    const errBox = document.createElement("div");
    errBox.className = "error-message";
    errBox.textContent = `Error: ${err.message}`;
    bubble.appendChild(errBox);

    state.isGenerating = false;
    sendBtn.disabled = false;
  }
}

/**
 * Polls the task status endpoint every 2 seconds until completion or failure.
 */
function pollTaskStatus(taskId, bubble, statusText) {
  if (state.pollingIntervalId) {
    clearInterval(state.pollingIntervalId);
  }

  let pollCount = 0;

  state.pollingIntervalId = setInterval(async () => {
    pollCount++;
    try {
      const res = await apiFetch(`/api/tasks/${taskId}`);
      if (!res.ok) {
        throw new Error("Failed to query task status.");
      }

      const task = await res.json();

      if (task.status === "completed") {
        clearInterval(state.pollingIntervalId);
        state.pollingIntervalId = null;
        state.isGenerating = false;
        sendBtn.disabled = false;

        // Render finished video and code block
        await renderCompletedTask(bubble, task);
        loadHistory();
      } else if (task.status === "failed") {
        clearInterval(state.pollingIntervalId);
        state.pollingIntervalId = null;
        state.isGenerating = false;
        sendBtn.disabled = false;

        renderFailedTask(bubble, task);
        loadHistory();
      } else {
        // Still processing
        if (pollCount % 3 === 0) {
          statusText.textContent = "Rendering frames with Manim engine (verifying mathematical output)...";
        }
      }
    } catch (err) {
      console.error("[Polling Error]", err);
      clearInterval(state.pollingIntervalId);
      state.pollingIntervalId = null;
      state.isGenerating = false;
      sendBtn.disabled = false;

      bubble.innerHTML = "";
      const errBox = document.createElement("div");
      errBox.className = "error-message";
      errBox.textContent = `Polling failed: ${err.message}`;
      bubble.appendChild(errBox);
    }
  }, 2000);
}

/**
 * Fetches the MP4 video securely as an authenticated Blob and mounts it in the DOM.
 */
async function renderCompletedTask(bubble, task) {
  bubble.innerHTML = "";

  const desc = document.createElement("p");
  desc.textContent = "Your animation has been generated and rendered successfully:";
  bubble.appendChild(desc);

  // Fetch video as Blob with Authorization Bearer header
  try {
    const videoRes = await apiFetch(`/api/videos/${task.id}`);
    if (!videoRes.ok) {
      throw new Error("Unable to stream video asset.");
    }

    const videoBlob = await videoRes.blob();
    const videoObjectUrl = URL.createObjectURL(videoBlob);

    const videoContainer = document.createElement("div");
    videoContainer.className = "video-container";

    const videoEl = document.createElement("video");
    videoEl.controls = true;
    videoEl.autoplay = false;
    videoEl.src = videoObjectUrl;

    videoContainer.appendChild(videoEl);
    bubble.appendChild(videoContainer);
  } catch (vErr) {
    const vErrBox = document.createElement("div");
    vErrBox.className = "error-message";
    vErrBox.textContent = `Video load error: ${vErr.message}`;
    bubble.appendChild(vErrBox);
  }

  // Collapsible Code Block
  if (task.code) {
    const details = document.createElement("details");
    details.className = "code-collapsible";

    const summary = document.createElement("summary");
    summary.className = "code-summary";
    summary.textContent = "View Generated Manim Code";

    const pre = document.createElement("pre");
    pre.className = "code-pre";
    const codeEl = document.createElement("code");
    codeEl.textContent = task.code;

    pre.appendChild(codeEl);
    details.appendChild(summary);
    details.appendChild(pre);
    bubble.appendChild(details);
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderFailedTask(bubble, task) {
  bubble.innerHTML = "";

  const errBox = document.createElement("div");
  errBox.className = "error-message";
  errBox.textContent = `Animation rendering failed: ${task.error || "Unknown error"}`;
  bubble.appendChild(errBox);

  if (task.code) {
    const details = document.createElement("details");
    details.className = "code-collapsible";

    const summary = document.createElement("summary");
    summary.className = "code-summary";
    summary.textContent = "View Attempted Manim Code";

    const pre = document.createElement("pre");
    pre.className = "code-pre";
    const codeEl = document.createElement("code");
    codeEl.textContent = task.code;

    pre.appendChild(codeEl);
    details.appendChild(summary);
    details.appendChild(pre);
    bubble.appendChild(details);
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}


// ============================================================================
// History Loading & Navigation
// ============================================================================

async function loadHistory() {
  if (!state.token) return;

  try {
    const res = await apiFetch("/api/history");
    if (!res.ok) return;

    const tasks = await res.json();
    historyList.innerHTML = "";

    if (tasks.length === 0) {
      const empty = document.createElement("div");
      empty.className = "history-empty";
      empty.textContent = "No animations yet. Try creating one!";
      historyList.appendChild(empty);
      return;
    }

    tasks.forEach((task) => {
      const item = document.createElement("div");
      item.className = "history-item";
      if (task.id === state.activeTaskId) {
        item.classList.add("active");
      }

      const title = document.createElement("div");
      title.className = "history-item-title";
      title.textContent = task.prompt;

      const meta = document.createElement("div");
      meta.className = "history-item-meta";

      const badge = document.createElement("span");
      badge.className = `status-badge ${task.status}`;
      badge.textContent = task.status;

      const timeSpan = document.createElement("span");
      const date = new Date(task.created_at);
      timeSpan.textContent = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      meta.appendChild(badge);
      meta.appendChild(timeSpan);

      item.appendChild(title);
      item.appendChild(meta);

      item.addEventListener("click", () => inspectHistoryItem(task));
      historyList.appendChild(item);
    });
  } catch (err) {
    console.warn("[History] Failed to load history:", err);
  }
}

/**
 * Loads an existing task from history directly into the conversation view.
 */
async function inspectHistoryItem(task) {
  if (state.isGenerating) {
    alert("Please wait for current generation to finish.");
    return;
  }

  state.activeTaskId = task.id;

  // Highlight active item in history list
  document.querySelectorAll(".history-item").forEach((el) => el.classList.remove("active"));
  // Reset chat view
  chatMessages.innerHTML = "";

  // 1. Show user prompt
  createMessageRow("user", task.prompt);

  // 2. Show assistant result
  const { bubble } = createMessageRow("assistant");

  if (task.status === "completed") {
    await renderCompletedTask(bubble, task);
  } else if (task.status === "failed") {
    renderFailedTask(bubble, task);
  } else {
    // If still pending or processing, show spinner and resume polling
    const statusContainer = document.createElement("div");
    statusContainer.className = "processing-status";
    const spinner = document.createElement("div");
    spinner.className = "spinner";
    const statusText = document.createElement("span");
    statusText.textContent = "Task is currently processing...";
    statusContainer.appendChild(spinner);
    statusContainer.appendChild(statusText);
    bubble.appendChild(statusContainer);

    state.isGenerating = true;
    sendBtn.disabled = true;
    pollTaskStatus(task.id, bubble, statusText);
  }
}


// ============================================================================
// Application Bootstrapping
// ============================================================================

window.addEventListener("DOMContentLoaded", () => {
  checkHealthAndInitGoogle();

  if (state.token && state.username) {
    // Already authenticated
    authScreen.classList.add("hidden");
    mainScreen.classList.remove("hidden");
    updateUserProfileUI();
    loadHistory();
  } else {
    // Show auth modal
    authScreen.classList.remove("hidden");
    mainScreen.classList.add("hidden");
  }
});

