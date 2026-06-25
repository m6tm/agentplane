import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-shell";

let apiBase = "http://127.0.0.1:3400";
let ws: WebSocket | null = null;
let reconnectInterval: number = 3000;
let reconnectAttempts: number = 0;
let maxReconnectAttempts: number = 10;

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

interface LogEntry {
  level: string;
  message: string;
  agent_id: string | null;
  timestamp: number;
}

// State
let agents: Agent[] = [];
let signals: Signal[] = [];
let positions: Position[] = [];
let logs: LogEntry[] = [];

// Neural network visualization
class NeuralNetwork {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private nodes: Array<{ x: number; y: number; vx: number; vy: number; size: number; pulse: number; agent?: Agent }> = [];
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

  updateAgents(newAgents: Agent[]) {
    // Update nodes based on agents
    const targetCount = Math.max(newAgents.length, 5);
    
    if (this.nodes.length < targetCount) {
      for (let i = this.nodes.length; i < targetCount; i++) {
        this.nodes.push({
          x: Math.random() * this.canvas.width,
          y: Math.random() * this.canvas.height,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          size: 4 + Math.random() * 4,
          pulse: Math.random() * Math.PI * 2,
        });
      }
    }

    // Update agent data on nodes
    newAgents.forEach((agent, i) => {
      if (i < this.nodes.length) {
        this.nodes[i].agent = agent;
      }
    });
  }

  initNodes() {
    const count = 15;
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
      const isAgent = !!node.agent;
      const isScanning = node.agent?.status === "scanning";
      const isTrading = node.agent?.status === "trading";

      // Color based on status
      let color = "#00d4ff"; // Default cyan
      let glowColor = "rgba(0, 212, 255, 0.3)";
      
      if (isScanning) {
        color = "#ffaa00"; // Orange for scanning
        glowColor = "rgba(255, 170, 0, 0.4)";
      } else if (isTrading) {
        color = "#8844ff"; // Purple for trading
        glowColor = "rgba(136, 68, 255, 0.4)";
      } else if (isAgent) {
        color = "#00ff88"; // Green for active agent
        glowColor = "rgba(0, 255, 136, 0.3)";
      }

      // Glow
      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, pulseSize * 3
      );
      gradient.addColorStop(0, glowColor);
      gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(node.x, node.y, pulseSize * 3, 0, Math.PI * 2);
      ctx.fill();

      // Core
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
      ctx.fill();

      // Agent name label
      if (node.agent && node.size > 5) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
        ctx.font = "10px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(node.agent.name, node.x, node.y - pulseSize - 5);
      }
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

// WebSocket connection
function connectWebSocket() {
  const wsUrl = apiBase.replace("http://", "ws://").replace("https://", "wss://") + "/api/ws/ws";
  
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("WebSocket connected");
    reconnectAttempts = 0;
    setStatus(true);
    addLogEntry("success", "Real-time connection established");
  };

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    handleWebSocketMessage(message);
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
    setStatus(false);
    
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      addLogEntry("warning", `Connection lost. Reconnecting... (${reconnectAttempts}/${maxReconnectAttempts})`);
      setTimeout(connectWebSocket, reconnectInterval);
    } else {
      addLogEntry("error", "Max reconnection attempts reached. Please refresh.");
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
    addLogEntry("error", "Connection error");
  };
}

function handleWebSocketMessage(message: any) {
  switch (message.type) {
    case "initial":
      agents = message.data.agents || [];
      signals = message.data.signals || [];
      positions = message.data.positions || [];
      updateAllViews();
      break;

    case "agent_update":
      updateAgent(message.data);
      break;

    case "signal":
      addSignal(message.data);
      break;

    case "position_update":
      updatePosition(message.data);
      break;

    case "log":
      addLogEntry(message.data.level, message.data.message, message.data.agent_id);
      break;

    case "heartbeat":
      updateHeartbeat(message.data);
      break;

    case "pong":
      break;
  }
}

function updateAgent(data: any) {
  const index = agents.findIndex(a => a.id === data.id);
  if (index >= 0) {
    agents[index] = { ...agents[index], ...data };
  } else {
    agents.push(data as Agent);
  }
  updateAgentsView();
  updateMetrics();
}

function addSignal(data: any) {
  signals.unshift(data as Signal);
  if (signals.length > 100) signals.pop();
  updateSignalsView();
  updateMetrics();
  addLogEntry("success", `Signal: ${data.symbol} ${data.direction}`, data.agent_id);
}

function updatePosition(data: any) {
  const index = positions.findIndex(p => p.id === data.id);
  if (index >= 0) {
    positions[index] = { ...positions[index], ...data };
  } else {
    positions.push(data as Position);
  }
  updatePositionsView();
  updateMetrics();
}

function updateHeartbeat(data: any) {
  // Update agent status based on heartbeat
  const agent = agents.find(a => a.id === data.agent_id);
  if (agent) {
    agent.status = data.status;
    updateAgentsView();
  }
}

function updateAllViews() {
  updateMetrics();
  updateAgentsView();
  updateSignalsView();
  updatePositionsView();
  updateNeuralViz();
}

function updateMetrics() {
  document.getElementById("metric-agents")!.textContent = String(agents.length);
  document.getElementById("metric-signals")!.textContent = String(signals.length);
  document.getElementById("metric-positions")!.textContent = String(positions.length);

  // Calculate P&L
  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl_usd || 0), 0);
  document.getElementById("metric-pnl")!.textContent = `$${totalPnl.toFixed(2)}`;

  const pnlChange = document.getElementById("metric-pnl-change")!;
  if (totalPnl >= 0) {
    pnlChange.className = "metric-change";
    pnlChange.textContent = "+Profit today";
  } else {
    pnlChange.className = "metric-change negative";
    pnlChange.textContent = "-Loss today";
  }
}

function updateAgentsView() {
  const recentEl = document.getElementById("recent-agents")!;
  const allEl = document.getElementById("all-agents")!;

  renderAgentList(recentEl, agents.slice(0, 6));
  renderAgentList(allEl, agents);
}

function renderAgentList(el: HTMLElement, agentList: Agent[]) {
  if (agentList.length === 0) {
    el.innerHTML = `<li class="muted">No neural agents active</li>`;
    return;
  }

  el.innerHTML = agentList
    .map((a) => {
      const statusClass = a.status === "idle" ? "active" : a.status === "scanning" ? "scanning" : a.status === "trading" ? "trading" : "";
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

function updateSignalsView() {
  const el = document.getElementById("signals-list")!;
  if (signals.length === 0) {
    el.innerHTML = `<div class="muted">No signals detected yet</div>`;
    return;
  }

  el.innerHTML = signals
    .slice(0, 20)
    .map((s) => {
      const directionColor = s.direction === "long" ? "text-success" : "text-error";
      const agent = agents.find(a => a.id === s.agent_id);
      const agentName = agent ? agent.name : "Unknown";
      return `
        <div class="list-item">
          <div class="list-item-info">
            <span class="list-item-title">${s.symbol}</span>
            <span class="list-item-subtitle">${agentName} • Confidence: ${(s.confidence * 100).toFixed(0)}%</span>
          </div>
          <span class="badge ${directionColor}">${s.direction.toUpperCase()}</span>
        </div>
      `;
    })
    .join("");
}

function updatePositionsView() {
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
      const agent = agents.find(a => a.id === p.agent_id);
      const agentName = agent ? agent.name : "Unknown";
      return `
        <div class="list-item">
          <div class="list-item-info">
            <span class="list-item-title">${p.symbol}</span>
            <span class="list-item-subtitle">${agentName} • Entry: ${p.entry_price} • Size: ${p.quantity}</span>
          </div>
          <span class="${pnlClass}">${pnlSign}$${pnl.toFixed(2)}</span>
        </div>
      `;
    })
    .join("");
}

function updateNeuralViz() {
  if (neuralNet) {
    neuralNet.updateAgents(agents);
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

function addLogEntry(level: string, message: string, agentId?: string) {
  const entry: LogEntry = {
    level,
    message,
    agent_id: agentId || null,
    timestamp: Date.now(),
  };
  logs.unshift(entry);
  if (logs.length > 100) logs.pop();

  renderLogs();
}

function renderLogs() {
  const containers = ["activity-log", "full-log"];
  
  containers.forEach(containerId => {
    const container = document.getElementById(containerId);
    if (!container) return;

    const displayLogs = containerId === "activity-log" ? logs.slice(0, 20) : logs;

    container.innerHTML = displayLogs
      .map((log) => {
        const time = new Date(log.timestamp).toLocaleTimeString();
        const agentLabel = log.agent_id ? `[${log.agent_id.slice(0, 8)}] ` : "";
        return `
          <div class="log-entry">
            <span class="log-time">${time}</span>
            <span class="log-level ${log.level}">${log.level.toUpperCase()}</span>
            <span class="log-message">${agentLabel}${log.message}</span>
          </div>
        `;
      })
      .join("");

    container.scrollTop = 0;
  });
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

// Neural network instance
let neuralNet: NeuralNetwork;

async function init() {
  apiBase = await getApiBase();
  document.getElementById("backend-url")!.textContent = apiBase;
  document.getElementById("error-url")!.textContent = apiBase;

  // Initialize neural network visualization
  neuralNet = new NeuralNetwork("neural-canvas");

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
    
    // Connect WebSocket for real-time data
    connectWebSocket();
    
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
    });
  });

  // Actions
  document.getElementById("refresh-btn")!.addEventListener("click", () => {
    // Request fresh data via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "ping" }));
    }
    addLogEntry("info", "Manual refresh triggered");
  });

  document.getElementById("open-api-btn")!.addEventListener("click", () => {
    open(`${apiBase}/docs`);
  });

  // Cleanup on unload
  window.addEventListener("beforeunload", () => {
    if (ws) {
      ws.close();
    }
    neuralNet.destroy();
  });
}

init();
