const state = {
    sessions: [],
    connection: "idle",
    currentRunId: null,
    currentAssistantId: null,
    currentAssistantText: "",
    inlineActivities: new Map(),
    messageCounter: 0,
    userScrolled: false,
};

const messagesEl = document.getElementById("messages");
const runMarkerEl = document.getElementById("runMarker");
const connectionLabelEl = document.getElementById("connectionLabel");
const connectionBadgeEl = document.getElementById("connectionBadge");
const sessionSelectEl = document.getElementById("sessionSelect");
const sessionHintEl = document.getElementById("sessionHint");
const chatFormEl = document.getElementById("chatForm");
const messageInputEl = document.getElementById("messageInput");
const sendButtonEl = document.getElementById("sendButton");
const refreshSessionsButtonEl = document.getElementById("refreshSessionsButton");

function scrollToBottom() {
    if (!state.userScrolled) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }
}

messagesEl.addEventListener("scroll", () => {
    const threshold = 60;
    const atBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < threshold;
    state.userScrolled = !atBottom;
});

async function loadSessions(retries = 3, delay = 2000) {
    setConnection("streaming", "正在读取会话", "会话列表加载中");
    sendButtonEl.disabled = true;

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch("/api/sessions");
            if (!response.ok) {
                throw new Error(`sessions request failed (${response.status})`);
            }

            state.sessions = await response.json();
            renderSessions();
            setConnection("connected", "已连接 Gateway", `${state.sessions.length} 个可用会话`);
            sendButtonEl.disabled = false;
            return;
        } catch (error) {
            if (attempt < retries) {
                setConnection("error", "会话读取失败", `第 ${attempt} 次重试中...`);
                await new Promise((resolve) => setTimeout(resolve, delay));
                continue;
            }
            state.sessions = [];
            renderSessions();
            setConnection("error", "会话读取失败", error.message || "无法连接到后端");
        }
    }
    sendButtonEl.disabled = false;
}

function renderSessions() {
    sessionSelectEl.innerHTML = "";

    if (!state.sessions.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "暂无可用会话";
        sessionSelectEl.appendChild(option);
        sessionHintEl.textContent = "先确认后端能连上 OpenClaw Gateway。";
        return;
    }

    for (const session of state.sessions) {
        const option = document.createElement("option");
        option.value = session.key;
        option.textContent = `${session.label} · ${session.key}`;
        sessionSelectEl.appendChild(option);
    }

    const preferred = state.sessions.find((session) => session.key === "agent:main:main") || state.sessions[0];
    sessionSelectEl.value = preferred.key;
    sessionHintEl.textContent = `默认命中 ${preferred.key}。`;
}

function setConnection(variant, label, badgeText) {
    state.connection = variant;
    connectionLabelEl.textContent = label;
    connectionBadgeEl.textContent = badgeText;
    connectionBadgeEl.className = `status-pill ${variant}`;
}

function addMessage(role, text = "") {
    state.messageCounter += 1;
    const id = `message-${state.messageCounter}`;
    const row = document.createElement("article");
    row.className = `message-row ${role}`;
    row.dataset.messageId = id;

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.innerHTML = `
        <span class="message-role">${role === "user" ? "You" : "Assistant"}</span>
        <span class="message-time">${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</span>
    `;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = text;

    row.append(meta, bubble);
    messagesEl.appendChild(row);
    scrollToBottom();
    return { id, row, bubble };
}

function updateAssistantMessage(delta) {
    if (!state.currentAssistantId) {
        const message = addMessage("assistant", "");
        state.currentAssistantId = message.id;
        state.currentAssistantText = "";
    }

    state.currentAssistantText += delta;

    const bubble = messagesEl.querySelector(`[data-message-id="${state.currentAssistantId}"] .message-bubble`);
    if (!bubble) {
        return;
    }

    bubble.innerHTML = renderMarkdown(state.currentAssistantText);
    scrollToBottom();
}

function typeLabel(event) {
    switch (event.kind || event.type) {
        case "tool_call": return "Tool call";
        case "tool_result": return "Tool output";
        case "command": return "Tool call";
        case "command-output": return "Tool output";
        case "assistant": return "Assistant";
        case "lifecycle": return "Lifecycle";
        default: return event.type || "Event";
    }
}

function typeIcon(event) {
    const kind = event.kind || event.type;
    if (kind === "tool_result" || kind === "command-output") return "◁";
    if (kind === "tool_call" || kind === "command") return "⚡";
    if (kind === "assistant") return "💬";
    if (kind === "lifecycle") return "⟳";
    return "⚡";
}

function chipClass(event) {
    const kind = event.kind || event.type;
    if (kind === "command" || kind === "command-output") return "command";
    if (kind === "assistant" || kind === "assistant-trace") return "assistant";
    return "tool";
}

function upsertInlineActivity(event) {
    const itemKey = event.itemId
        || event.toolCallId
        || `${event.type}:${event.stream || ""}:${event.kind || ""}:${event.name || ""}:${event.phase || ""}:${event.title || ""}`;

    const existing = state.inlineActivities.get(itemKey);
    const merged = {
        ...existing,
        ...event,
        text: event.text || existing?.text || "",
    };

    if (event.type === "command-output") {
        const previous = existing?.text ? `${existing.text}\n` : "";
        merged.text = `${previous}${event.text || ""}`.trim();
    }

    state.inlineActivities.set(itemKey, merged);

    const existingEl = messagesEl.querySelector(`[data-activity-key="${CSS.escape(itemKey)}"]`);
    if (existingEl) {
        updateInlineCard(existingEl, merged);
    } else {
        const card = createInlineCard(itemKey, merged);
        messagesEl.appendChild(card);
    }
    scrollToBottom();
}

function createInlineCard(key, item) {
    const wrapper = document.createElement("div");
    wrapper.className = "inline-activity";
    wrapper.dataset.activityKey = key;

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.className = `inline-activity-summary ${chipClass(item)}`;
    summary.innerHTML = buildSummaryHTML(item);
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "inline-activity-body";
    body.innerHTML = buildBodyHTML(item);
    details.appendChild(body);

    wrapper.appendChild(details);
    return wrapper;
}

function updateInlineCard(el, item) {
    const summary = el.querySelector(".inline-activity-summary");
    if (summary) {
        summary.innerHTML = buildSummaryHTML(item);
    }
    const body = el.querySelector(".inline-activity-body");
    if (body) {
        body.innerHTML = buildBodyHTML(item);
    }
}

function buildSummaryHTML(item) {
    const icon = typeIcon(item);
    const label = typeLabel(item);
    const name = item.name || item.title || "";
    const kindTag = escapeHtml(item.kind || item.stream || item.type || "");
    const statusTag = item.status || item.phase || "";
    return `
        <span class="ia-icon">${icon}</span>
        <span class="ia-label">${escapeHtml(label)}</span>
        <span class="ia-kind">${kindTag}</span>
        ${name ? `<span class="ia-name">${escapeHtml(name)}</span>` : ""}
        ${statusTag ? `<span class="ia-status">${escapeHtml(statusTag)}</span>` : ""}
    `;
}

function buildBodyHTML(item) {
    let html = "";
    if (item.toolCallId) {
        html += `<div class="ia-field"><span class="ia-field-label">toolCallId:</span> ${escapeHtml(item.toolCallId)}</div>`;
    }
    if (item.phase && item.status) {
        html += `<div class="ia-field"><span class="ia-field-label">phase:</span> ${escapeHtml(item.phase)} · <span class="ia-field-label">status:</span> ${escapeHtml(item.status)}</div>`;
    }
    if (item.text) {
        html += `<pre class="ia-log">${escapeHtml(item.text)}</pre>`;
    }
    if (item.raw) {
        html += `<details class="ia-raw-toggle"><summary>raw payload</summary><pre class="ia-log">${escapeHtml(typeof item.raw === "string" ? item.raw : JSON.stringify(item.raw, null, 2))}</pre></details>`;
    }
    if (!html) {
        html = `<div class="ia-field" style="color:var(--text-dim)">暂无详情</div>`;
    }
    return html;
}

function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function renderMarkdown(raw) {
    const escaped = escapeHtml(raw);
    let html = escaped;

    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
        return `<pre class="md-code-block"><code${lang ? ` data-lang="${lang}"` : ""}>${code.trim()}</code></pre>`;
    });

    html = html.replace(/`([^`\n]+)`/g, '<code class="md-inline-code">$1</code>');
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\[ref:([^\]]+)\]/g, '<span class="md-ref">[ref:$1]</span>');

    html = html.replace(/^### (.+)$/gm, '<h4 class="md-h3">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="md-h2">$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2 class="md-h1">$1</h2>');

    html = html.replace(/^[-*] (.+)$/gm, '<li class="md-li">$1</li>');
    html = html.replace(/((?:<li class="md-li">.*<\/li>\n?)+)/g, '<ul class="md-ul">$1</ul>');

    html = html.replace(/^\d+\. (.+)$/gm, '<li class="md-oli">$1</li>');
    html = html.replace(/((?:<li class="md-oli">.*<\/li>\n?)+)/g, '<ol class="md-ol">$1</ol>');

    html = html.replace(/\n{2,}/g, "</p><p>");
    html = `<p>${html}</p>`;
    html = html.replace(/<p>\s*(<(?:h[2-4]|pre|ul|ol))/g, "$1");
    html = html.replace(/(<\/(?:h[2-4]|pre|ul|ol)>)\s*<\/p>/g, "$1");
    html = html.replace(/<p>\s*<\/p>/g, "");

    return html;
}

async function streamChat(message, sessionKey) {
    state.inlineActivities.clear();
    state.currentRunId = null;
    state.currentAssistantId = null;
    state.currentAssistantText = "";
    state.userScrolled = false;
    runMarkerEl.textContent = "连接中";
    setConnection("streaming", "流式处理中", "正在接收");

    addMessage("user", message);

    const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, sessionKey }),
    });

    if (!response.ok || !response.body) {
        throw new Error(`chat stream failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) {
                continue;
            }
            try {
                handleEvent(JSON.parse(trimmed));
            } catch (_parseError) {
                // skip malformed NDJSON lines
            }
        }
    }

    if (buffer.trim()) {
        handleEvent(JSON.parse(buffer.trim()));
    }
}

function handleEvent(event) {
    switch (event.type) {
        case "connected":
            setConnection("connected", "已连上 OpenClaw", "链路在线");
            break;
        case "run-started":
            state.currentRunId = event.runId;
            runMarkerEl.textContent = event.runId || "已启动";
            break;
        case "assistant-delta":
            updateAssistantMessage(event.delta || event.text || "");
            break;
        case "activity":
        case "command-output":
        case "assistant-trace":
        case "lifecycle":
            upsertInlineActivity(event);
            break;
        case "done":
            setConnection("connected", "本轮完成", "已结束");
            runMarkerEl.textContent = event.runId || "已完成";
            break;
        case "error":
            setConnection("error", "流中断", "错误");
            addMessage("assistant", event.text || "请求失败");
            break;
        default:
            break;
    }
}

chatFormEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = messageInputEl.value.trim();
    const sessionKey = sessionSelectEl.value;
    if (!message) {
        return;
    }

    sendButtonEl.disabled = true;
    messageInputEl.disabled = true;

    try {
        await streamChat(message, sessionKey);
        messageInputEl.value = "";
    } catch (error) {
        setConnection("error", "请求失败", "错误");
        addMessage("assistant", error.message || "请求失败");
    } finally {
        sendButtonEl.disabled = false;
        messageInputEl.disabled = false;
        messageInputEl.focus();
    }
});

messageInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatFormEl.requestSubmit();
    }
});

refreshSessionsButtonEl.addEventListener("click", () => {
    loadSessions();
});

loadSessions();
