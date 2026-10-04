// TickerPing Client Application

const state = {
  alarms: [],
  settings: {},
  pollTimer: null
};

// DOM Elements
const formAddAlarm = document.getElementById("form-add-alarm");
const inputTicker = document.getElementById("input-ticker");
const inputDirection = document.getElementById("input-direction");
const inputTarget = document.getElementById("input-target");
const inputNote = document.getElementById("input-note");
const btnSubmitAlarm = document.getElementById("btn-submit-alarm");

const alarmsGrid = document.getElementById("alarms-grid");
const alarmsEmpty = document.getElementById("alarms-empty");
const alarmCountBadge = document.getElementById("alarm-count-badge");
const btnRefresh = document.getElementById("btn-refresh");

const modalSettings = document.getElementById("modal-settings");
const btnOpenSettings = document.getElementById("btn-open-settings");
const formSettings = document.getElementById("form-settings");
const settingsToken = document.getElementById("settings-token");
const settingsChatid = document.getElementById("settings-chatid");
const btnDetectChat = document.getElementById("btn-detect-chat");
const btnTestTelegram = document.getElementById("btn-test-telegram");
const testResultMsg = document.getElementById("test-result-msg");
const alertsWarning = document.getElementById("alerts-warning");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  fetchSettings();
  fetchAlarms();
  setupEventListeners();

  // Auto-refresh every 30s
  state.pollTimer = setInterval(fetchAlarms, 30000);
});

function setupEventListeners() {
  btnRefresh.addEventListener("click", () => {
    btnRefresh.classList.add("opacity-50");
    fetchAlarms().finally(() => btnRefresh.classList.remove("opacity-50"));
  });

  btnOpenSettings.addEventListener("click", openSettingsModal);

  formAddAlarm.addEventListener("submit", async (e) => {
    e.preventDefault();
    await handleAddAlarm();
  });

  formSettings.addEventListener("submit", async (e) => {
    e.preventDefault();
    await handleSaveSettings();
  });

  btnDetectChat.addEventListener("click", handleDetectChatId);
  btnTestTelegram.addEventListener("click", handleTestTelegram);
}

// Modal Handlers
function openSettingsModal() {
  modalSettings.classList.remove("hidden");
}

function closeSettingsModal() {
  modalSettings.classList.add("hidden");
  testResultMsg.classList.add("hidden");
}

// API Calls
async function fetchSettings() {
  try {
    const res = await fetch("/api/settings");
    if (!res.ok) return;
    state.settings = await res.json();

    if (state.settings.telegram_chat_id) {
      settingsChatid.value = state.settings.telegram_chat_id;
    }
    if (state.settings.telegram_bot_token_masked) {
      settingsToken.placeholder = state.settings.telegram_bot_token_masked;
    }

    if (!state.settings.is_configured) {
      alertsWarning.classList.remove("hidden");
    } else {
      alertsWarning.classList.add("hidden");
    }
  } catch (err) {
    console.error("Failed to fetch settings:", err);
  }
}

async function handleDetectChatId() {
  const token = settingsToken.value.trim();
  if (!token) {
    alert("Please paste your Telegram Bot Token first!");
    return;
  }

  btnDetectChat.textContent = "Detecting...";
  try {
    const res = await fetch("/api/telegram/detect-chat-id", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token: token })
    });
    const data = await res.json();
    if (res.ok && data.chat_id) {
      settingsChatid.value = data.chat_id;
      alert(`Found your chat ID: ${data.chat_id} (${data.first_name || data.username})`);
    } else {
      alert(data.detail || "Make sure you opened your bot in Telegram and tapped /start, then try again.");
    }
  } catch (err) {
    alert("Error detecting chat ID: " + err.message);
  } finally {
    btnDetectChat.textContent = "Detect Automatically";
  }
}

async function handleSaveSettings() {
  const token = settingsToken.value.trim();
  const chatid = settingsChatid.value.trim();

  if (!chatid) {
    alert("Please provide your Telegram Chat ID.");
    return;
  }

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chatid })
    });

    if (res.ok) {
      alert("Settings saved successfully!");
      closeSettingsModal();
      fetchSettings();
    } else {
      const err = await res.json();
      alert("Failed to save settings: " + (err.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Error saving settings: " + err.message);
  }
}

async function handleTestTelegram() {
  const token = settingsToken.value.trim();
  const chatid = settingsChatid.value.trim();

  if (!chatid) {
    alert("Please enter or detect your Chat ID first.");
    return;
  }

  testResultMsg.className = "text-xs text-center p-2 rounded-lg bg-slate-800 text-slate-300 block";
  testResultMsg.textContent = "Sending test message to Telegram...";

  try {
    const res = await fetch("/api/test-telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token: token, chat_id: chatid })
    });

    const data = await res.json();
    if (res.ok) {
      testResultMsg.className = "text-xs text-center p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 block font-semibold";
      testResultMsg.textContent = "✅ Message sent! Check your Telegram app.";
    } else {
      testResultMsg.className = "text-xs text-center p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 block";
      testResultMsg.textContent = "❌ " + (data.detail || "Failed to send message. Please verify your Bot Token & Chat ID.");
    }
  } catch (err) {
    testResultMsg.className = "text-xs text-center p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 block";
    testResultMsg.textContent = "❌ Error: " + err.message;
  }
}

async function fetchAlarms() {
  try {
    const res = await fetch("/api/alarms");
    if (!res.ok) return;
    state.alarms = await res.json();
    renderAlarms();
  } catch (err) {
    console.error("Failed to fetch alarms:", err);
  }
}

async function handleAddAlarm() {
  const ticker = inputTicker.value.trim().toUpperCase();
  const direction = inputDirection.value;
  const target = parseFloat(inputTarget.value);
  const note = inputNote.value.trim();

  if (!ticker || isNaN(target) || target <= 0) {
    alert("Please enter a valid ticker and target price.");
    return;
  }

  btnSubmitAlarm.disabled = true;
  btnSubmitAlarm.innerHTML = `<span>Checking ${ticker}...</span>`;

  try {
    const res = await fetch("/api/alarms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, target_price: target, direction, note })
    });

    if (res.ok) {
      inputTicker.value = "";
      inputTarget.value = "";
      inputNote.value = "";
      await fetchAlarms();
    } else {
      const err = await res.json();
      alert("Error: " + (err.detail || "Could not add alarm."));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  } finally {
    btnSubmitAlarm.disabled = false;
    btnSubmitAlarm.innerHTML = `<span>Set Alarm</span>`;
  }
}

async function handleDeleteAlarm(id) {
  if (!confirm("Are you sure you want to delete this alarm?")) return;
  try {
    const res = await fetch(`/api/alarms/${id}`, { method: "DELETE" });
    if (res.ok) fetchAlarms();
  } catch (err) {
    console.error("Delete failed:", err);
  }
}

async function handleToggleAlarm(id) {
  try {
    const res = await fetch(`/api/alarms/${id}/toggle`, { method: "POST" });
    if (res.ok) fetchAlarms();
  } catch (err) {
    console.error("Toggle failed:", err);
  }
}

async function handleResetAlarm(id) {
  try {
    const res = await fetch(`/api/alarms/${id}/reset`, { method: "POST" });
    if (res.ok) fetchAlarms();
  } catch (err) {
    console.error("Reset failed:", err);
  }
}

function renderAlarms() {
  alarmCountBadge.textContent = state.alarms.length;

  if (state.alarms.length === 0) {
    alarmsEmpty.classList.remove("hidden");
    alarmsGrid.innerHTML = "";
    return;
  }

  alarmsEmpty.classList.add("hidden");
  alarmsGrid.innerHTML = state.alarms.map(alarm => {
    const isTriggered = alarm.triggered;
    const isActive = alarm.active;
    const priceText = alarm.current_price !== null ? `$${alarm.current_price.toFixed(2)}` : "Fetching...";
    const changePct = alarm.change_percent !== null ? (alarm.change_percent >= 0 ? `+${alarm.change_percent}%` : `${alarm.change_percent}%`) : "";
    const changeColor = (alarm.change_percent || 0) >= 0 ? "text-emerald-400" : "text-rose-400";
    
    let statusBadge = "";
    if (isTriggered) {
      statusBadge = `<span class="bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">🚨 Triggered</span>`;
    } else if (!isActive) {
      statusBadge = `<span class="bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-bold px-2 py-0.5 rounded-full">⏸️ Paused</span>`;
    } else {
      statusBadge = `<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold px-2 py-0.5 rounded-full">Active</span>`;
    }

    const directionIcon = alarm.direction === "ABOVE" ? "▲ Above" : "▼ Below";
    const diffText = alarm.diff_percent !== null ? `${Math.abs(alarm.diff_percent)}% away` : "";

    return `
      <div class="bg-slate-900 border ${isTriggered ? 'border-rose-500/40 shadow-rose-950/20' : 'border-slate-800'} rounded-2xl p-5 shadow-lg relative flex flex-col justify-between space-y-4 transition hover:border-slate-700">
        <div>
          <div class="flex items-start justify-between">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-xl font-bold tracking-tight text-white font-mono">${alarm.ticker}</span>
                <span class="text-[10px] text-slate-400 px-1.5 py-0.5 bg-slate-800 rounded font-mono">${alarm.currency || 'USD'}</span>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">${alarm.note || 'No note'}</p>
            </div>
            ${statusBadge}
          </div>

          <div class="mt-4 grid grid-cols-2 gap-2 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
            <div>
              <span class="text-[10px] text-slate-500 uppercase font-semibold block">Market Price</span>
              <div class="text-base font-bold text-white font-mono">${priceText}</div>
              <span class="text-[11px] ${changeColor} font-mono">${changePct}</span>
            </div>

            <div>
              <span class="text-[10px] text-slate-500 uppercase font-semibold block">Target Price</span>
              <div class="text-base font-bold text-slate-200 font-mono">${directionIcon} $${alarm.target_price.toFixed(2)}</div>
              <span class="text-[11px] text-slate-400 font-mono">${diffText}</span>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
          <div class="flex items-center gap-1.5">
            ${isTriggered ? `
              <button onclick="handleResetAlarm('${alarm.id}')" class="text-emerald-400 hover:text-emerald-300 font-medium px-2 py-1 bg-emerald-500/10 rounded-lg border border-emerald-500/20 transition">
                🔄 Re-arm
              </button>
            ` : `
              <button onclick="handleToggleAlarm('${alarm.id}')" class="text-slate-400 hover:text-slate-200 px-2 py-1 bg-slate-800 rounded-lg transition">
                ${isActive ? 'Pause' : 'Resume'}
              </button>
            `}
          </div>

          <button onclick="handleDeleteAlarm('${alarm.id}')" class="text-rose-400 hover:text-rose-300 px-2 py-1 rounded-lg transition flex items-center gap-1">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            Delete
          </button>
        </div>
      </div>
    `;
  }).join("");
}
