/**
 * YokoNex Cloud — WebSocket Relay Server
 *
 * Two connection roles:
 *   Agent  — local Python yokonex server registers here, handles BLE
 *   Client — Flutter / mobile app subscribes to an agent and sends commands
 *
 * Protocol additions on top of the existing yokonex JSON protocol:
 *
 *   Agent → Server (first message):
 *     { "type": "agent_hello", "token": "...", "agent_id": "home-pc", "meta": {} }
 *
 *   Client → Server (first message):
 *     { "type": "client_hello", "token": "..." }
 *
 *   Client → Server:
 *     { "type": "list_agents", "id": "r1" }
 *     { "type": "subscribe",   "id": "r2", "agent_id": "home-pc" }
 *     { "id": "r3", "type": "scan",    "params": { "duration": 5 } }
 *     { "id": "r4", "type": "connect", "params": { ... } }
 *     ...all other messages are forwarded to subscribed agent unchanged
 *
 *   Server → Client:
 *     { "type": "hello",  "ok": true, "role": "client", "client_id": "..." }
 *     { "id": "r1", "ok": true,  "agents": [...] }
 *     { "id": "r2", "ok": true,  "agent_id": "home-pc" }
 *     ...forwarded agent responses and events
 *
 *   Server → Agent (forwarded from client, with injected _src):
 *     { "id": "r3", "type": "scan", "params": {...}, "_src": "<clientId>" }
 *
 *   Agent → Server (forwarded to originating client):
 *     { "id": "r3", "ok": true, "devices": [...] }
 *     { "type": "event", "address": "...", "event": "connected", "data": {...} }
 */

require("dotenv").config();
const { WebSocketServer, WebSocket } = require("ws");
const { randomUUID } = require("crypto");

const PORT         = parseInt(process.env.PORT         || "8080", 10);
const HOST         = process.env.HOST         || "0.0.0.0";
const AGENT_TOKEN  = process.env.AGENT_TOKEN  || "yokonex-agent-dev";
const CLIENT_TOKEN = process.env.CLIENT_TOKEN || "yokonex-client-dev";

// ── State ─────────────────────────────────────────────────────────────────────

/** @type {Map<string, { ws: WebSocket, meta: object, clients: Set<string> }>} */
const agents = new Map();

/** @type {Map<string, { ws: WebSocket, agentId: string|null }>} */
const clients = new Map();

/**
 * Pending requests: reqKey = `${agentId}:${reqId}` → clientId
 * Allows routing agent responses back to the originating client.
 */
const pending = new Map();

// ── Server ────────────────────────────────────────────────────────────────────

const wss = new WebSocketServer({ host: HOST, port: PORT });

wss.on("connection", (ws) => {
  let role   = null;   // "agent" | "client"
  let selfId = null;

  ws.on("message", (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch {
      send(ws, { type: "error", message: "invalid JSON" });
      return;
    }

    // ── Auth phase (first message must authenticate) ───────────────────────
    if (!role) {
      if (msg.type === "agent_hello") {
        if (msg.token !== AGENT_TOKEN) {
          send(ws, { type: "error", message: "unauthorized" });
          ws.close(1008, "unauthorized");
          return;
        }
        const agentId = (msg.agent_id || "").trim() || randomUUID().slice(0, 8);
        role   = "agent";
        selfId = agentId;
        agents.set(agentId, { ws, meta: msg.meta || {}, clients: new Set() });
        send(ws, { type: "hello", ok: true, role: "agent", agent_id: agentId });
        console.log(`[agent+] ${agentId}  total=${agents.size}`);
        return;
      }

      if (msg.type === "client_hello") {
        if (msg.token !== CLIENT_TOKEN) {
          send(ws, { type: "error", message: "unauthorized" });
          ws.close(1008, "unauthorized");
          return;
        }
        const clientId = randomUUID();
        role   = "client";
        selfId = clientId;
        clients.set(clientId, { ws, agentId: null });
        send(ws, { type: "hello", ok: true, role: "client", client_id: clientId });
        console.log(`[client+] ${clientId.slice(0, 8)}  total=${clients.size}`);
        return;
      }

      send(ws, { type: "error", message: "send agent_hello or client_hello first" });
      return;
    }

    // ── Client messages ───────────────────────────────────────────────────
    if (role === "client") {
      // List registered agents
      if (msg.type === "list_agents") {
        const list = [...agents.entries()].map(([id, a]) => ({
          id,
          meta:    a.meta,
          clients: a.clients.size,
        }));
        send(ws, { id: msg.id, ok: true, agents: list });
        return;
      }

      // Subscribe to an agent
      if (msg.type === "subscribe") {
        const target = agents.get(msg.agent_id);
        if (!target) {
          send(ws, { id: msg.id, ok: false, error: `agent '${msg.agent_id}' not found` });
          return;
        }
        const state = clients.get(selfId);
        // Unsubscribe from previous agent
        if (state.agentId) {
          const prev = agents.get(state.agentId);
          if (prev) prev.clients.delete(selfId);
        }
        state.agentId = msg.agent_id;
        target.clients.add(selfId);
        send(ws, { id: msg.id, ok: true, agent_id: msg.agent_id });
        console.log(`[route] client ${selfId.slice(0, 8)} → agent ${msg.agent_id}`);
        return;
      }

      // Forward command to subscribed agent
      const state = clients.get(selfId);
      if (!state.agentId) {
        send(ws, { id: msg.id, ok: false, error: "not subscribed to any agent" });
        return;
      }
      const agent = agents.get(state.agentId);
      if (!agent || agent.ws.readyState !== WebSocket.OPEN) {
        send(ws, { id: msg.id, ok: false, error: "agent unavailable" });
        return;
      }
      // Track pending so we can route the response back
      if (msg.id) {
        pending.set(`${state.agentId}:${msg.id}`, selfId);
      }
      send(agent.ws, { ...msg, _src: selfId });
      return;
    }

    // ── Agent messages ────────────────────────────────────────────────────
    if (role === "agent") {
      const agent = agents.get(selfId);
      if (!agent) return;

      // Events (unsolicited): broadcast to all subscribed clients
      if (msg.type === "event") {
        for (const cid of agent.clients) {
          const c = clients.get(cid);
          if (c && c.ws.readyState === WebSocket.OPEN) send(c.ws, msg);
        }
        return;
      }

      // Response to a specific request: route back to originating client
      if (msg.id) {
        const key      = `${selfId}:${msg.id}`;
        const clientId = pending.get(key);
        pending.delete(key);
        if (clientId) {
          const c = clients.get(clientId);
          if (c && c.ws.readyState === WebSocket.OPEN) send(c.ws, msg);
        }
        return;
      }
    }
  });

  ws.on("close", () => {
    if (role === "agent") {
      const agent = agents.get(selfId);
      if (agent) {
        // Notify all subscribed clients that agent is gone
        for (const cid of agent.clients) {
          const c = clients.get(cid);
          if (c) {
            if (c.ws.readyState === WebSocket.OPEN) {
              send(c.ws, { type: "error", message: `agent '${selfId}' disconnected` });
            }
            c.agentId = null;
          }
        }
        agents.delete(selfId);
      }
      console.log(`[agent-] ${selfId}  total=${agents.size}`);
    } else if (role === "client") {
      const state = clients.get(selfId);
      if (state?.agentId) {
        const agent = agents.get(state.agentId);
        if (agent) agent.clients.delete(selfId);
      }
      clients.delete(selfId);
      console.log(`[client-] ${selfId.slice(0, 8)}  total=${clients.size}`);
    }
  });

  ws.on("error", (err) => console.error("[ws]", err.message));
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function send(ws, data) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

// ── Start ─────────────────────────────────────────────────────────────────────

console.log(`YokoNex Cloud  ws://${HOST}:${PORT}`);
console.log(`  AGENT_TOKEN  = ${AGENT_TOKEN}`);
console.log(`  CLIENT_TOKEN = ${CLIENT_TOKEN}`);
