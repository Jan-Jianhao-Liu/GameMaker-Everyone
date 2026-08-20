const ROLES = [
  {id: "designer", label: "策划", icon: "📋"},
  {id: "supervisor", label: "监理", icon: "🔍"},
  {id: "artist3d", label: "3D美术", icon: "🎨"},
  {id: "artist2d", label: "2D美术", icon: "🖌"},
  {id: "coder", label: "程序", icon: "💻"},
  {id: "qa", label: "测试", icon: "🧪"},
];

const PROVIDERS = [
  {id: "deepseek", icon: "🐳", name: "DeepSeek", baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat"},
  {id: "glm",      icon: "🔮", name: "智谱 GLM",  baseUrl: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-air"},
  {id: "qwen",     icon: "🌐", name: "通义千问",  baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus"},
  {id: "custom",   icon: "⚙",  name: "自定义",    baseUrl: "", model: ""},
];

let ws = null;
let currentTaskId = null;

function init() {
  renderRoles();
  connect();
  document.getElementById("make-btn").onclick = startMake;
  document.getElementById("settings-btn").onclick = openSettings;
  document.getElementById("settings-close").onclick = closeSettings;
  document.getElementById("ollama-refresh").onclick = requestOllamaStatus;
  document.getElementById("msg-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleEnter(); }
  });
}

function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onopen = () => {
    setConn("connected", "已连接");
    loadSettingsFromStorage();
    requestOllamaStatus();
  };
  ws.onclose = () => { setConn("disconnected", "已断开"); setTimeout(connect, 3000); };
  ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
}

function setConn(status, text) {
  document.getElementById("conn-dot").className = "dot " + status;
  document.getElementById("conn-text").textContent = text;
}

function renderRoles() {
  const container = document.getElementById("roles");
  container.innerHTML = "";
  for (const r of ROLES) {
    const card = document.createElement("div");
    card.className = "role-card";
    card.id = `role-${r.id}`;
    card.innerHTML = `
      <span class="indicator"></span>
      <div class="info">
        <div class="name">${r.icon} ${r.label}</div>
        <div class="detail">待命</div>
      </div>`;
    container.appendChild(card);
  }
}

function handleEnter() {
  const input = document.getElementById("msg-input");
  const text = input.value.trim();
  if (!text) return;
  if (text.startsWith("/")) {
    sendMessage();
  } else {
    startMake();
  }
}

function sendMessage() {
  const input = document.getElementById("msg-input");
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({type: "chat", text: text.replace(/^\//, "")}));
  addMessage("user", text);
  input.value = "";
}

function startMake() {
  const input = document.getElementById("msg-input");
  const request = input.value.trim();
  if (!request) {
    addSystem("请先在输入框描述游戏需求，再启动开发。");
    input.focus();
    return;
  }
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({type: "make_game", request}));
  addMessage("user", `🚀 ${request}`);
  input.value = "";
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  document.getElementById("messages").appendChild(div);
  scrollDown();
}

function addSystem(text) {
  const div = document.createElement("div");
  div.className = "msg system";
  div.textContent = text;
  document.getElementById("messages").appendChild(div);
  scrollDown();
}

function scrollDown() {
  const m = document.getElementById("messages");
  m.scrollTop = m.scrollHeight;
}

function handleEvent(ev) {
  switch (ev.type) {
    case "team_reply": addMessage("team", ev.text); break;
    case "role_status": updateRole(ev.role, ev.status, ev.detail); break;
    case "progress": handleProgress(ev.node, ev.update); break;
    case "checkpoint": showCheckpoint(ev.task_id, ev.message); break;
    case "complete": handleComplete(ev.task_id, ev.summary); break;
    case "error": addSystem(`✗ ${ev.message}`); break;
    case "history": ev.messages.forEach(m => addMessage(m.role, m.text)); break;
    case "config_saved": handleConfigSaved(ev); break;
    case "connection_test": handleConnectionTest(ev); break;
    case "ollama_status": handleOllamaStatus(ev); break;
  }
}

function updateRole(role, status, detail) {
  const card = document.getElementById(`role-${role}`);
  if (!card) return;
  const ind = card.querySelector(".indicator");
  ind.className = "indicator " + status;
  card.querySelector(".detail").textContent = detail || (status === "idle" ? "待命" : status);
}

function handleProgress(node, update) {
  if (update.produced_assets) updateAssets(update.produced_assets);
  if (update.build_result) updateBuild(update.build_result);
  if (update.defects) updateDefects(update.defects);
  if (update.status === "paused_human") addSystem("⏸ 等待人工确认...");
}

function showCheckpoint(taskId, message) {
  currentTaskId = taskId;
  const card = document.createElement("div");
  card.className = "checkpoint-card";
  card.innerHTML = `
    <h3>⚠ 人工卡点</h3>
    <p class="checkpoint-msg"></p>
    <div class="actions">
      <input type="text" placeholder="修改意见（可选）..." data-feedback>
      <button class="accept">确认</button>
      <button class="reject">拒绝</button>
    </div>`;
  card.querySelector(".checkpoint-msg").textContent = message;
  card.querySelector(".accept").onclick = () => {
    const fb = card.querySelector("[data-feedback]").value;
    ws.send(JSON.stringify({type: "checkpoint_response", task_id: taskId, accept: true, feedback: fb}));
    card.remove();
  };
  card.querySelector(".reject").onclick = () => {
    const fb = card.querySelector("[data-feedback]").value;
    ws.send(JSON.stringify({type: "checkpoint_response", task_id: taskId, accept: false, feedback: fb}));
    card.remove();
  };
  document.getElementById("messages").appendChild(card);
  scrollDown();
}

function handleComplete(taskId, summary) {
  addSystem(`✓ 任务 ${taskId} 完成`);
  if (summary.produced_assets) updateAssets(summary.produced_assets);
  if (summary.build_result) updateBuild(summary.build_result);
  if (summary.defects) updateDefects(summary.defects);
  ROLES.forEach(r => updateRole(r.id, "idle"));
}

function updateAssets(assets) {
  const tbody = document.querySelector("#assets-table tbody");
  tbody.innerHTML = "";
  for (const a of assets) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${a.asset_id||""}</td><td>${a.type||""}</td><td>${a.producer||""}</td><td>${a.path||""}</td>`;
    tbody.appendChild(tr);
  }
}

function updateBuild(build) {
  const el = document.getElementById("build-info");
  if (build && build.path) {
    el.innerHTML = `路径: <code>${build.path}</code> | 状态: <strong>${build.status||""}</strong>`;
  } else {
    el.textContent = "未产出";
  }
}

function updateDefects(defects) {
  const list = document.getElementById("defects-list");
  list.innerHTML = "";
  for (const d of defects) {
    const li = document.createElement("li");
    li.textContent = typeof d === "string" ? d : JSON.stringify(d);
    list.appendChild(li);
  }
}

/* ---------- 设置面板 ---------- */

function openSettings() {
  renderProviderCards();
  document.getElementById("settings-modal").style.display = "flex";
  requestOllamaStatus();
  loadTeamConfig();
  loadPluginsConfig();
  document.querySelectorAll(".settings-tab").forEach(tab => {
    tab.onclick = () => switchSettingsTab(tab.dataset.tab);
  });
}

function switchSettingsTab(name) {
  document.querySelectorAll(".settings-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".settings-tab-content").forEach(c => c.classList.remove("active"));
  document.querySelector(`.settings-tab[data-tab="${name}"]`).classList.add("active");
  document.getElementById(`tab-${name}`).classList.add("active");
}

function closeSettings() {
  document.getElementById("settings-modal").style.display = "none";
}

/* ---------- 团队配置 ---------- */

let _teamRoles = [];

async function loadTeamConfig() {
  try {
    const r = await fetch("/api/config/team");
    const data = await r.json();
    _teamRoles = data.roles || [];
    renderTeamRoles();
  } catch (e) { console.error("加载团队配置失败:", e); }
}

function renderTeamRoles() {
  const container = document.getElementById("team-roles-list");
  container.innerHTML = "";
  for (const role of _teamRoles) {
    const card = document.createElement("div");
    card.className = "config-card";
    card.innerHTML = `
      <div class="config-card-header">
        <span class="config-icon">${role.icon || "🤖"}</span>
        <span class="config-name">${role.label || role.id}</span>
        <span class="config-type">${role.kind || ""} → ${role.next || role.next_on_pass || "END"}</span>
      </div>
      <div class="config-card-body">
        <div class="config-field"><label>ID</label><input type="text" data-key="id" value="${role.id}"></div>
        <div class="config-field"><label>显示名</label><input type="text" data-key="label" value="${role.label || ""}"></div>
        <div class="config-field"><label>图标</label><input type="text" data-key="icon" value="${role.icon || ""}"></div>
        <div class="config-field"><label>LLM</label>
          <select data-key="llm">
            <option value="cloud"${role.llm==="cloud"?" selected":""}>云端</option>
            <option value="local"${role.llm==="local"?" selected":""}>本地</option>
            <option value="none"${role.llm==="none"?" selected":""}>不用</option>
          </select></div>
        <div class="config-field"><label>类型</label><input type="text" data-key="kind" value="${role.kind || ""}"></div>
        <div class="config-field"><label>下一个角色</label><input type="text" data-key="next" value="${role.next || ""}"></div>
        <div class="config-field"><label>插件</label><input type="text" data-key="plugin" value="${role.plugin || ""}"></div>
        <div class="config-field"><label>工具链</label><input type="text" data-key="chain" value="${role.chain || ""}"></div>
      </div>
      <div class="config-card-actions">
        <button class="btn-save-config" data-save-role="${role.id}">保存</button>
        <button class="btn-toggle off" data-del-role="${role.id}">删除</button>
      </div>`;
    container.appendChild(card);
  }
  container.querySelectorAll("[data-save-role]").forEach(btn => {
    btn.onclick = () => saveRole(btn.dataset.saveRole);
  });
  container.querySelectorAll("[data-del-role]").forEach(btn => {
    btn.onclick = () => deleteRole(btn.dataset.delRole);
  });
  document.getElementById("add-role-btn").onclick = addRole;
}

function readRoleForm(card) {
  const role = {};
  card.querySelectorAll("[data-key]").forEach(el => { role[el.dataset.key] = el.value; });
  return role;
}

async function saveRole(roleId) {
  const card = document.querySelector(`[data-save-role="${roleId}"]`).closest(".config-card");
  const updated = readRoleForm(card);
  const idx = _teamRoles.findIndex(r => r.id === roleId);
  if (idx >= 0) _teamRoles[idx] = { ..._teamRoles[idx], ...updated };
  await fetch("/api/config/team", {
    method: "PUT", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({roles: _teamRoles}),
  });
  addSystem(`✓ 角色 ${roleId} 已保存`);
}

async function deleteRole(roleId) {
  _teamRoles = _teamRoles.filter(r => r.id !== roleId);
  await fetch("/api/config/team", {
    method: "PUT", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({roles: _teamRoles}),
  });
  renderTeamRoles();
  addSystem(`✓ 角色 ${roleId} 已删除`);
}

async function addRole() {
  const newRole = {id: `role_${Date.now().toString(36)}`, label: "新角色", icon: "🤖", llm: "local", kind: "custom", next: ""};
  _teamRoles.push(newRole);
  await fetch("/api/config/team", {
    method: "PUT", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({roles: _teamRoles}),
  });
  renderTeamRoles();
}

/* ---------- 插件管理 ---------- */

let _plugins = [];

async function loadPluginsConfig() {
  try {
    const r = await fetch("/api/config/plugins");
    const data = await r.json();
    _plugins = data.plugins || [];
    renderPlugins();
  } catch (e) { console.error("加载插件配置失败:", e); }
}

function renderPlugins() {
  const container = document.getElementById("plugins-list");
  container.innerHTML = "";
  for (const p of _plugins) {
    const card = document.createElement("div");
    card.className = "config-card";
    card.innerHTML = `
      <div class="config-card-header">
        <span class="config-icon">🔌</span>
        <span class="config-name">${p.name || p.id}</span>
        <span class="config-type">${p.type || ""} :${p.port || ""}</span>
        <button class="btn-toggle ${p.enabled ? "on" : "off"}" data-toggle-plugin="${p.id}">${p.enabled ? "已启用" : "已禁用"}</button>
      </div>
      <div class="config-card-body">
        <div class="config-field"><label>ID</label><input type="text" data-key="id" value="${p.id}"></div>
        <div class="config-field"><label>名称</label><input type="text" data-key="name" value="${p.name || ""}"></div>
        <div class="config-field"><label>类型</label>
          <select data-key="type">
            ${["3d_editor","2d_editor","game_engine","vcs","custom"].map(t =>
              `<option value="${t}"${p.type===t?" selected":""}>${t}</option>`).join("")}
          </select></div>
        <div class="config-field"><label>端口</label><input type="number" data-key="port" value="${p.port || ""}"></div>
      </div>`;
    container.appendChild(card);
  }
  container.querySelectorAll("[data-toggle-plugin]").forEach(btn => {
    btn.onclick = () => togglePlugin(btn.dataset.togglePlugin);
  });
}

async function togglePlugin(pluginId) {
  const p = _plugins.find(x => x.id === pluginId);
  if (!p) return;
  p.enabled = !p.enabled;
  await fetch("/api/config/plugins", {
    method: "PUT", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({plugins: _plugins}),
  });
  renderPlugins();
  addSystem(`✓ 插件 ${pluginId} 已${p.enabled ? "启用" : "禁用"}`);
}

function maskKey(key) {
  if (!key) return "";
  if (key.length <= 8) return "****";
  return key.slice(0, 3) + "****" + key.slice(-4);
}

function getProviderConfig(id) {
  return {
    apiKey: localStorage.getItem(`gaf_key_${id}`) || "",
    baseUrl: localStorage.getItem(`gaf_url_${id}`) || "",
    model:   localStorage.getItem(`gaf_model_${id}`) || "",
    active:  localStorage.getItem("gaf_active_provider") === id,
  };
}

function renderProviderCards() {
  const container = document.getElementById("provider-cards");
  container.innerHTML = "";
  for (const p of PROVIDERS) {
    const cfg = getProviderConfig(p.id);
    const card = document.createElement("div");
    card.className = "provider-card" + (cfg.active ? " active" : "");
    card.id = `provider-${p.id}`;
    card.innerHTML = `
      <div class="provider-header" data-toggle="${p.id}">
        <span class="provider-icon">${p.icon}</span>
        <span class="provider-name">${p.name}</span>
        <span class="provider-status">${cfg.active ? "● 已启用" : (cfg.apiKey ? "已配置" : "未配置")}</span>
        <span class="status-dot ${cfg.apiKey ? "connected" : "unknown"}"></span>
      </div>
      <div class="provider-body hidden">
        <div class="field-row">
          <label>Base URL</label>
          <input type="text" data-field="baseUrl" value="${cfg.baseUrl || p.baseUrl}" placeholder="${p.baseUrl || 'https://...'}">
        </div>
        <div class="field-row">
          <label>API Key</label>
          ${cfg.apiKey
            ? `<div class="key-redacted"><span>${maskKey(cfg.apiKey)}</span><button class="reedit" data-reedit="${p.id}">重新输入</button></div>`
            : `<input type="password" data-field="apiKey" placeholder="sk-...">`}
        </div>
        <div class="field-row">
          <label>模型名</label>
          <input type="text" data-field="model" value="${cfg.model || p.model}" placeholder="${p.model || 'model-name'}">
        </div>
        <div class="provider-actions">
          <button class="btn-test" data-test="${p.id}">测试连接</button>
          <button class="btn-save" data-save="${p.id}">保存并启用</button>
          <span class="test-result" data-result="${p.id}"></span>
        </div>
      </div>`;
    container.appendChild(card);
  }
  container.querySelectorAll("[data-toggle]").forEach(el => {
    el.onclick = () => {
      const body = el.nextElementSibling;
      body.classList.toggle("hidden");
    };
  });
  container.querySelectorAll("[data-reedit]").forEach(el => {
    el.onclick = () => {
      const row = el.closest(".field-row");
      row.innerHTML = `<label>API Key</label><input type="password" data-field="apiKey" placeholder="sk-...">`;
    };
  });
  container.querySelectorAll("[data-test]").forEach(el => {
    el.onclick = () => testConnection(el.dataset.test);
  });
  container.querySelectorAll("[data-save]").forEach(el => {
    el.onclick = () => saveProvider(el.dataset.save);
  });
}

function readProviderForm(id) {
  const card = document.getElementById(`provider-${id}`);
  const baseUrl = card.querySelector('[data-field="baseUrl"]').value.trim();
  const model   = card.querySelector('[data-field="model"]').value.trim();
  const keyEl   = card.querySelector('[data-field="apiKey"]');
  const apiKey  = keyEl ? keyEl.value.trim() : "";
  return {baseUrl, model, apiKey};
}

function testConnection(id) {
  const p = PROVIDERS.find(x => x.id === id);
  const form = readProviderForm(id);
  const baseUrl = form.baseUrl || p.baseUrl;
  const apiKey  = form.apiKey || getProviderConfig(id).apiKey;
  if (!baseUrl || !apiKey) {
    setTestResult(id, false, "请填写 Base URL 和 API Key");
    return;
  }
  const btn = document.querySelector(`[data-test="${id}"]`);
  btn.disabled = true;
  setTestResult(id, null, "测试中...");
  ws.send(JSON.stringify({
    type: "test_connection", provider_id: id, base_url: baseUrl, api_key: apiKey,
  }));
}

function setTestResult(id, ok, text) {
  const el = document.querySelector(`[data-result="${id}"]`);
  if (!el) return;
  el.textContent = text;
  el.className = "test-result" + (ok === true ? " ok" : (ok === false ? " fail" : ""));
  const btn = document.querySelector(`[data-test="${id}"]`);
  if (btn) btn.disabled = false;
}

function handleConnectionTest(ev) {
  const id = ev.provider_id;
  if (ev.success) {
    const n = ev.models.length;
    setTestResult(id, true, `✓ 连接成功（${n} 个模型）`);
    if (n > 0) {
      const card = document.getElementById(`provider-${id}`);
      let tagsEl = card.querySelector(".model-tags");
      if (!tagsEl) {
        tagsEl = document.createElement("div");
        tagsEl.className = "model-tags";
        card.querySelector(".provider-body").appendChild(tagsEl);
      }
      tagsEl.innerHTML = ev.models.slice(0, 12).map(m => `<span class="model-tag">${m}</span>`).join("");
    }
  } else {
    setTestResult(id, false, `✗ ${ev.error || "连接失败"}`);
  }
}

function saveProvider(id) {
  const p = PROVIDERS.find(x => x.id === id);
  const form = readProviderForm(id);
  const baseUrl = form.baseUrl || p.baseUrl;
  const model   = form.model   || p.model;
  const apiKeyNew = form.apiKey;
  const apiKeyOld = getProviderConfig(id).apiKey;
  const apiKey = apiKeyNew || apiKeyOld;

  if (!apiKey) {
    setTestResult(id, false, "请先填写 API Key");
    return;
  }
  localStorage.setItem(`gaf_url_${id}`, baseUrl);
  localStorage.setItem(`gaf_model_${id}`, model);
  if (apiKeyNew) localStorage.setItem(`gaf_key_${id}`, apiKeyNew);
  localStorage.setItem("gaf_active_provider", id);

  ws.send(JSON.stringify({
    type: "set_config",
    cloud_provider: id, base_url: baseUrl, api_key: apiKey, model,
  }));
  setTestResult(id, true, "✓ 已保存并启用");
  renderProviderCards();
}

function loadSettingsFromStorage() {
  const activeId = localStorage.getItem("gaf_active_provider");
  if (!activeId) return;
  const cfg = getProviderConfig(activeId);
  const p = PROVIDERS.find(x => x.id === activeId);
  if (!p) return;
  const baseUrl = cfg.baseUrl || p.baseUrl;
  const model   = cfg.model   || p.model;
  if (cfg.apiKey && ws && ws.readyState === 1) {
    ws.send(JSON.stringify({
      type: "set_config",
      cloud_provider: activeId, base_url: baseUrl, api_key: cfg.apiKey, model,
    }));
  }
}

function handleConfigSaved(ev) {
  if (ev.api_key_set) {
    addSystem(`✓ LLM 配置已生效（服务商: ${ev.cloud_provider || "默认"}）`);
  }
}

/* ---------- Ollama 状态 ---------- */

function requestOllamaStatus() {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({type: "get_ollama_status"}));
  }
}

function handleOllamaStatus(ev) {
  const dot = document.getElementById("ollama-dot");
  const txt = document.getElementById("ollama-status-text");
  const tags = document.getElementById("ollama-models");
  if (!dot) return;
  if (ev.connected) {
    dot.className = "status-dot connected";
    txt.textContent = `已连接（127.0.0.1:11434）`;
    tags.innerHTML = (ev.models || []).map(m => `<span class="model-tag">${m}</span>`).join("");
  } else {
    dot.className = "status-dot disconnected";
    txt.textContent = "未连接（请启动 Ollama 服务）";
    tags.innerHTML = "";
  }
}

init();
