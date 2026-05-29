import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-shell";

let apiBase = "http://127.0.0.1:3400";

type Agent = {
  id: string;
  name: string;
  adapter_type: string;
  created_at: string;
};

type AdapterInfo = {
  type: string;
  label: string;
};

async function getApiBase(): Promise<string> {
  try {
    const url: string = await invoke("get_api_base");
    return url;
  } catch {
    return apiBase;
  }
}

async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${apiBase}/api/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function fetchAgents(): Promise<Agent[]> {
  const res = await fetch(`${apiBase}/api/agents`);
  if (!res.ok) return [];
  return res.json();
}

async function fetchAdapters(): Promise<AdapterInfo[]> {
  const res = await fetch(`${apiBase}/api/adapters`);
  if (!res.ok) return [];
  return res.json();
}

function setStatus(online: boolean) {
  const dot = document.getElementById("status-dot")!;
  const text = document.getElementById("status-text")!;
  if (online) {
    dot.className = "dot online";
    text.textContent = "Backend online";
  } else {
    dot.className = "dot error";
    text.textContent = "Backend offline";
  }
}

function renderAgentList(id: string, agents: Agent[]) {
  const el = document.getElementById(id)!;
  if (agents.length === 0) {
    el.innerHTML = `<li class="muted">No agents yet</li>`;
    return;
  }
  el.innerHTML = agents
    .map(
      (a) =>
        `<li><span>${a.name}</span><span class="badge">${a.adapter_type}</span></li>`
    )
    .join("");
}

async function loadDashboard() {
  const agents = await fetchAgents();
  const adapters = await fetchAdapters();

  document.getElementById("metric-agents")!.textContent = String(agents.length);
  document.getElementById("metric-adapters")!.textContent = String(adapters.length);
  document.getElementById("metric-runs")!.textContent = "—";

  const recent = agents.slice(0, 6);
  renderAgentList("recent-agents", recent);
}

async function loadAgents() {
  const agents = await fetchAgents();
  renderAgentList("all-agents", agents);
}

function showSection(name: string) {
  document.querySelectorAll(".section-panel").forEach((el) => el.classList.add("hidden"));
  document.getElementById(`${name}-section`)?.classList.remove("hidden");
  if (name === "dashboard") {
    document.getElementById("dashboard")?.classList.remove("hidden");
  }

  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  document.querySelector(`.nav-item[data-section="${name}"]`)?.classList.add("active");

  const titles: Record<string, string> = {
    dashboard: "Dashboard",
    agents: "Agents",
    runs: "Runs",
    settings: "Settings",
  };
  document.getElementById("page-title")!.textContent = titles[name] || name;
}

async function init() {
  apiBase = await getApiBase();
  document.getElementById("backend-url")!.textContent = apiBase;
  document.getElementById("error-url")!.textContent = apiBase;

  let ready = false;
  for (let i = 0; i < 120; i++) {
    ready = await healthCheck();
    if (ready) break;
    await new Promise((r) => setTimeout(r, 500));
  }

  const loading = document.getElementById("loading")!;
  const error = document.getElementById("error")!;
  const content = document.getElementById("content")!;

  if (ready) {
    setStatus(true);
    loading.classList.add("hidden");
    content.classList.remove("hidden");
    await loadDashboard();
  } else {
    setStatus(false);
    loading.classList.add("hidden");
    error.classList.remove("hidden");
  }

  // Navigation
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const section = (el as HTMLElement).dataset.section!;
      showSection(section);
      if (section === "agents") loadAgents();
    });
  });

  // Actions
  document.getElementById("refresh-btn")!.addEventListener("click", () => {
    loadDashboard();
  });

  document.getElementById("open-api-btn")!.addEventListener("click", () => {
    open(`${apiBase}/docs`);
  });
}

init();
