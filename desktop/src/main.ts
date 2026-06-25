import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-shell";

let apiBase = "http://127.0.0.1:3400";

interface Agent {
  id: string;
  name: string;
  role: string;
  adapter_type: string;
  status: string;
  created_at: string;
  watchlist?: Array<{ symbol: string; interval: string }>;
}

interface Signal {
  id: string;
  agent_id: string;
  symbol: string;
  direction: string;
  confidence: number;
  created_at: string;
}

interface Position {
  id: string;
  agent_id: string;
  symbol: string;
  direction: string;
  quantity: number;
  entry_price: number;
  unrealized_pnl_usd: number | null;
}

// Neural network visualization
class NeuralNetwork {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private nodes: Array<{ x: number; y: number; vx: number; vy: number; size: number; pulse: number }> = [];
  private connections: Array<{ from: number; to: number; strength: number }> = [];
  private animationId: number = 0;

  constructor(canvasId: string) {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement;
    this.ctx = this.canvas.getContext("2d")!;
    this.resize();
    this.initNodes();
    this.animate();
    window.addEventListener("resize", () => this.resize());
  }

  resize() {
    const parent = this.canvas.parentElement!;
    this.canvas.width = parent.clientWidth;
    this.canvas.height = parent.clientHeight;
  }

  initNodes() {
    const count = 20;
    this.nodes = [];
    for (let i = 0; i < count; i++) {
      this.nodes.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: 3 + Math.random() * 4,
        pulse: Math.random() * Math.PI * 2,
      });
    }

    // Create connections
    this.connections = [];
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        if (Math.random() < 0.15) {
          this.connections.push({ from: i, to: j, strength: Math.random() });
        }
      }
    }
  }

  animate() {
    const ctx = this.ctx;
    const width = this.canvas.width;
    const height = this.canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Update nodes
    this.nodes.forEach((node) => {
      node.x += node.vx;
      node.y += node.vy;
      node.pulse += 0.02;

      if (node.x < 0 || node.x > width) node.vx *= -1;
      if (node.y < 0 || node.y > height) node.vy *= -1;
    });

    // Draw connections
    this.connections.forEach((conn) => {
      const from = this.nodes[conn.from];
      const to = this.nodes[conn.to];
      const dist = Math.hypot(to.x - from.x, to.y - from.y);

      if (dist < 150) {
        const alpha = (1 - dist / 150) * conn.strength * 0.3;
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });

    // Draw nodes
    this.nodes.forEach((node) => {
      const pulseSize = node.size + Math.sin(node.pulse) * 2;

      // Glow
      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, pulseSize * 3
      );
      gradient.addColorStop(0, "rgba(0, 212, 255, 0.3)");
      gradient.addColorStop(1, "rgba(0, 212, 255, 0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(node.x, node.y, pulseSize * 3, 0, Math.PI * 2);
      ctx.fill();

      // Core
      ctx.fillStyle = "#00d4ff";
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
      ctx.fill();
    });

    this.animationId = requestAnimationFrame(() => this.animate());
  }

  destroy() {
    cancelAnimationFrame(this.animationId);
  }
}

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
  try {
    const res = await fetch(`${apiBase}/api/agents`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

async function fetchSignals(): Promise<Signal[]> {
  try {
    const res = await fetch(`${apiBase}/api/agents`);
    if (!res.ok) return [];
    const agents = await res.json();
    const allSignals: Signal[] = [];
    for (const agent of agents) {
      const sigRes = await fetch(`${apiBase}/api/agents/${agent.id}/signals`);
      if (sigRes.ok) {
        const signals = await sigRes.json();
        allSignals.push(...signals);
      }
    }
    return allSignals;
  } catch {
    return [];
  }
}

async function fetchPositions(): Promise<Position[]> {
  try {
    const res = await fetch(`${apiBase}/api/agents`);
    if (!res.ok) return [];
    const agents = await res.json();
    const allPositions: Position[] = [];
    for (const agent of agents) {
      const posRes = await fetch(`${apiBase}/api/agents/${agent.id}/positions`);
      if (posRes.ok) {
        const positions = await posRes.json();
        allPositions.push(...positions);
      }
    }
    return allPositions;
  } catch {
    return [];
  }
}

function setStatus(online: boolean) {
  const dot = document.getElementById("status-dot")!;
  const text = document.getElementById("status-text")!;
  if (online) {
    dot.className = "dot online";
    text.textContent = "Neural Network Online";
  } else {
    dot.className = "dot error";
    text.textContent = "Network Offline";
  }
}

function addLogEntry(level: string, message: string, containerId: string = "activity-log") {
  const container = document.getElementById(containerId);
  if (!container) return;

  const now = new Date();
  const time = now.toLocaleTimeString();

  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `
    <span class="log-time">${time}</span>
    <span class="log-level ${level}">${level.toUpperCase()}</span>
    <span class="log-message">${message}</span>
  `;

  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;

  // Keep only last 50 entries
  while (container.children.length > 50) {
    container.removeChild(container.firstChild!);
  }
}

function renderAgentList(id: string, agents: Agent[]) {
  const el = document.getElementById(id)!;
  if (agents.length === 0) {
    el.innerHTML = `<li class="muted">No neural agents active</li>`;
    return;
  }

  el.innerHTML = agents
    .map((a) => {
      const statusClass = a.status === "idle" ? "active" : a.status === "scanning" ? "scanning" : "trading";
      const statusText = a.status.toUpperCase();
      const watchlistCount = a.watchlist?.length || 0;
      return `
        <li class="list-item">
          <div class="list-item-info">
            <span class="list-item-title">${a.name}</span>
            <span class="list-item-subtitle">${a.role} • ${watchlistCount} pairs monitored</span>
          </div>
          <span class="badge ${statusClass}">${statusText}</span>
        </li>
      `;
    })
    .join("");
}

function renderSignals(signals: Signal[]) {
  const el = document.getElementById("signals-list")!;
  if (signals.length === 0) {
    el.innerHTML = `<div class="muted">No signals detected yet</div>`;
    return;
  }

  el.innerHTML = signals
    .slice(0, 20)
    .map((s) => {
      const directionColor = s.direction === "long" ? "text-success" : "text-error";
      return `
        <div class="list-item">
          <div class="list-item-info">
            <span class="list-item-title">${s.symbol}</span>
            <span class="list-item-subtitle">Confidence: ${(s.confidence * 100).toFixed(0)}%</span>
          </div>
          <span class="badge ${directionColor}">${s.direction.toUpperCase()}</span>
        </div>
      `;
    })
    .join("");
}

function renderPositions(positions: Position[]) {
  const el = document.getElementById("positions-list")!;
  if (positions.length === 0) {
    el.innerHTML = `<div class="muted">No open positions</div>`;
    return;
  }

  el.innerHTML = positions
    .map((p) => {
      const pnl = p.unrealized_pnl_usd || 0;
      const pnlClass = pnl >= 0 ? "text-success" : "text-error";
      const pnlSign = pnl >= 0 ? "+" : "";
      return `
        <div class="list-item">
          <div class="list-item-info">
            <span class="list-item-title">${p.symbol}</span>
            <span class="list-item-subtitle">Entry: ${p.entry_price} • Size: ${p.quantity}</span>
          </div>
          <span class="${pnlClass}">${pnlSign}$${pnl.toFixed(2)}</span>
        </div>
      `;
    })
    .join("");
}

async function loadDashboard() {
  const agents = await fetchAgents();
  const signals = await fetchSignals();
  const positions = await fetchPositions();

  // Calculate P&L
  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl_usd || 0), 0);

  document.getElementById("metric-agents")!.textContent = String(agents.length);
  document.getElementById("metric-signals")!.textContent = String(signals.length);
  document.getElementById("metric-positions")!.textContent = String(positions.length);
  document.getElementById("metric-pnl")!.textContent = `$${totalPnl.toFixed(2)}`;

  const pnlChange = document.getElementById("metric-pnl-change")!;
  if (totalPnl >= 0) {
    pnlChange.className = "metric-change";
    pnlChange.textContent = "+Profit today";
  } else {
    pnlChange.className = "metric-change negative";
    pnlChange.textContent = "-Loss today";
  }

  const recent = agents.slice(0, 6);
  renderAgentList("recent-agents", recent);
  renderSignals(signals);
  renderPositions(positions);

  // Add log entry
  if (signals.length > 0) {
    addLogEntry("success", `${signals.length} signals detected in network`);
  }
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
    dashboard: "Neural Dashboard",
    agents: "Neural Agents",
    signals: "Trading Signals",
    positions: "Open Positions",
    strategies: "Agent Strategies",
    logs: "Live Log Stream",
    settings: "Network Settings",
  };
  document.getElementById("page-title")!.textContent = titles[name] || name;
}

// Auto-refresh interval
let refreshInterval: number = 0;

function startAutoRefresh() {
  refreshInterval = window.setInterval(async () => {
    const isOnline = await healthCheck();
    if (isOnline) {
      await loadDashboard();
    }
  }, 5000);
}

async function init() {
  apiBase = await getApiBase();
  document.getElementById("backend-url")!.textContent = apiBase;
  document.getElementById("error-url")!.textContent = apiBase;

  // Initialize neural network visualization
  const neuralNet = new NeuralNetwork("neural-canvas");

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
    startAutoRefresh();
    addLogEntry("success", "Neural network initialized successfully");
  } else {
    setStatus(false);
    loading.classList.add("hidden");
    error.classList.remove("hidden");
    addLogEntry("error", "Failed to connect to backend");
  }

  // Navigation
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const section = (el as HTMLElement).dataset.section!;
      showSection(section);
      if (section === "agents") loadAgents();
      if (section === "dashboard") loadDashboard();
    });
  });

  // Actions
  document.getElementById("refresh-btn")!.addEventListener("click", () => {
    loadDashboard();
    addLogEntry("info", "Manual refresh triggered");
  });

  document.getElementById("open-api-btn")!.addEventListener("click", () => {
    open(`${apiBase}/docs`);
  });

  // Cleanup on unload
  window.addEventListener("beforeunload", () => {
    clearInterval(refreshInterval);
    neuralNet.destroy();
  });
}

init();
