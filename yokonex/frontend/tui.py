"""YokoNex TUI — terminal frontend using prompt_toolkit.

Layout (full-screen):
  ┌─ YokoNex Control ──────────── F5:Scan  F2:Connect  F3:Disconnect  q:Quit ─┐
  │ DEVICES                       │ LOG                                        │
  │ [1] YCY-FJB-03  toy  ✓        │ 00:14:35  Connected YCY-FJB-03             │
  │                               │ 00:14:36  battery: 80%                     │
  ├───────────────────────────────┴────────────────────────────────────────────┤
  │ ▶ _                                                                        │
  │ scan | connect <n> | disconnect <n> | mode/speed/stop/info (toy)           │
  │ ems <n> <ch> <intensity> [mode] [freq] [pulse] | stop <n> | info <n>       │
  └────────────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

from prompt_toolkit.document import Document

import websockets
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.text import Text

log = logging.getLogger("yokonex.tui")

WS_URL = "ws://127.0.0.1:8765"
_req_counter = 0
_console = Console()

STYLE = Style.from_dict({
    "header":      "bg:#1a1a2e #e0e0e0 bold",
    "footer":      "bg:#16213e #a0a0c0",
    "panel-title": "#00d4ff bold",
    "device-ok":   "#00ff88",
    "device-off":  "#888888",
    "device-addr": "#888888",
    "log-time":    "#888888",
    "log-event":   "#00d4ff",
    "log-error":   "#ff4444",
    "log-ok":      "#00ff88",
    "log-warn":    "#ffaa00",
    "divider":     "#334455",
    "prompt":      "#00d4ff bold",
    "hint":        "#556677 italic",
})


def _req_id() -> str:
    global _req_counter
    _req_counter += 1
    return f"tui-{_req_counter}"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── WSClient (fixed) ───────────────────────────────────────────────────────

class WSClient:
    """Async WS client with proper task lifecycle management."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._ws = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._event_cb = None
        self._recv_task: asyncio.Task | None = None   # keep strong reference

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.url)
        loop = asyncio.get_running_loop()
        self._recv_task = loop.create_task(self._recv_loop(), name="wsclient-recv")

    async def close(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            await self._ws.close()
        # cancel all pending futures so callers don't hang
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if msg.get("type") == "event":
                    if self._event_cb:
                        await self._event_cb(msg)
                else:
                    fut = self._pending.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(msg)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("recv_loop error: %s", exc)
        finally:
            # connection lost — cancel all pending requests
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    async def send(self, kind: str, params: dict) -> dict:
        loop = asyncio.get_running_loop()
        rid = _req_id()
        fut: asyncio.Future = loop.create_future()
        self._pending[rid] = fut
        await self._ws.send(json.dumps({"id": rid, "type": kind, "params": params}))
        return await asyncio.wait_for(fut, timeout=15)

    def on_event(self, callback) -> None:
        self._event_cb = callback


# ── App ────────────────────────────────────────────────────────────────────

class YokoNexApp:
    MAX_LOG = 200

    def __init__(self, ws_url: str = WS_URL) -> None:
        self._ws_url = ws_url
        self._ws: Optional[WSClient] = None
        self._scan_results: List[dict] = []
        self._devices: Dict[str, dict] = {}           # address → device dict
        self._log_lines: deque[tuple] = deque(maxlen=self.MAX_LOG)  # (style, text)
        self._app: Optional[Application] = None
        self._input_buf = Buffer(
            name="main-input",
            multiline=False,
            accept_handler=self._on_enter,
        )
        self._scanning = False
        self._history:      List[str] = []   # command history
        self._history_pos:  int = -1          # -1 = not browsing
        self._history_draft: str = ""         # saved draft before browsing up

    # ── Build layout ───────────────────────────────────────────────────────

    def _build_app(self) -> Application:
        kb = KeyBindings()

        @kb.add("f5")
        def _(event):
            asyncio.get_event_loop().create_task(self._cmd_scan())

        @kb.add("f2")
        def _(event):
            asyncio.get_event_loop().create_task(self._quick_connect())

        @kb.add("f3")
        def _(event):
            asyncio.get_event_loop().create_task(self._quick_disconnect())

        @kb.add("up")
        def _(event):
            self._history_up()

        @kb.add("down")
        def _(event):
            self._history_down()

        @kb.add("c-c")
        @kb.add("q", filter=Condition(lambda: not self._input_focused()))
        def _(event):
            event.app.exit()

        layout = Layout(
            HSplit([
                # header bar
                Window(
                    height=1,
                    content=FormattedTextControl(self._header_text),
                    style="class:header",
                ),
                # main area: devices (left) | log (right)
                VSplit([
                    Window(
                        content=FormattedTextControl(self._devices_text),
                        width=42,
                    ),
                    Window(width=1, char="│", style="class:divider"),
                    Window(
                        content=FormattedTextControl(self._log_text),
                    ),
                ]),
                # divider
                Window(height=1, char="─", style="class:divider"),
                # command input
                Window(
                    height=1,
                    content=BufferControl(
                        buffer=self._input_buf,
                        focusable=True,
                    ),
                    get_line_prefix=lambda _ln, _wrap: [("class:prompt", " ▶ ")],
                ),
                # hint bar
                Window(
                    height=1,
                    content=FormattedTextControl(self._hint_text),
                    style="class:footer",
                ),
            ]),
            focused_element=self._input_buf,
        )

        return Application(
            layout=layout,
            key_bindings=kb,
            style=STYLE,
            full_screen=True,
            mouse_support=False,
        )

    # ── Formatted text providers ───────────────────────────────────────────

    def _header_text(self) -> FormattedText:
        status = " [scanning…]" if self._scanning else ""
        return FormattedText([
            ("class:header", f"  YokoNex Control{status}"),
            ("class:header", "   F5:Scan  F2:Connect  F3:Disconnect  q:Quit  "),
        ])

    def _hint_text(self) -> FormattedText:
        return FormattedText([
            ("class:hint",
             "  scan | connect <n> | disconnect <n> | stop <n> | info <n> | list"
             "  │  ems <n> <A|B|AB> <intensity|off> [mode] [freq] [pulse]"
             "  │  help"),
        ])

    def _devices_text(self) -> FormattedText:
        items: list = [("class:panel-title", " DEVICES\n"), ("", " " + "─" * 39 + "\n")]
        if not self._scan_results and not self._devices:
            items.append(("class:device-off", "  (press F5 to scan)\n"))
        else:
            for i, d in enumerate(self._scan_results, 1):
                addr  = d["address"]
                name  = d["name"] or addr[-8:]
                dtype = d["device_type"]
                conn  = addr in self._devices and self._devices[addr].get("connected")
                dot   = ("class:device-ok",  " ✓") if conn else ("class:device-off", " ○")
                items.append(dot)
                items.append(("", f" [{i}] "))
                items.append(("class:device-ok" if conn else "", f"{name}"))
                items.append(("class:device-off", f"  {dtype}\n"))
            # show connected devices not in scan results (continue numbering)
            next_idx = len(self._scan_results) + 1
            for addr, d in self._devices.items():
                if not any(r["address"] == addr for r in self._scan_results):
                    name  = d.get("name") or addr[-8:]
                    dtype = d.get("type", "")
                    items.append(("class:device-ok", f" ✓ [{next_idx}] "))
                    items.append(("class:device-ok", f"{name}"))
                    items.append(("class:device-off", f"  {dtype}\n"))
                    next_idx += 1
        return FormattedText(items)

    def _log_text(self) -> FormattedText:
        items: list = [("class:panel-title", " LOG\n"), ("", " " + "─" * 39 + "\n")]
        # Determine how many lines fit so we always show the tail (auto-scroll).
        # Fixed chrome: header(1) + divider(1) + input(1) + hint(1) = 4 rows,
        # plus the two panel-header rows above = 6 total overhead.
        try:
            from prompt_toolkit.application import get_app
            rows = get_app().output.get_size().rows
            available = max(1, rows - 6)
        except Exception:
            available = 40
        for style, text in list(self._log_lines)[-available:]:
            items.append((style, f" {text}\n"))
        return FormattedText(items)

    def _input_focused(self) -> bool:
        if self._app is None:
            return False
        try:
            return self._app.layout.has_focus(self._input_buf)
        except Exception:
            return False

    def _history_up(self) -> None:
        if not self._history:
            return
        if self._history_pos == -1:
            self._history_draft = self._input_buf.text
            self._history_pos   = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        text = self._history[self._history_pos]
        self._input_buf.set_document(Document(text, len(text)))

    def _history_down(self) -> None:
        if self._history_pos == -1:
            return
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            text = self._history[self._history_pos]
        else:
            self._history_pos = -1
            text = self._history_draft
        self._input_buf.set_document(Document(text, len(text)))

    # ── Logging helpers ────────────────────────────────────────────────────

    def _log(self, text: str, style: str = "") -> None:
        self._log_lines.append((style, f"{_now()}  {text}"))
        if self._app:
            self._app.invalidate()

    def _logi(self, t: str) -> None: self._log(t, "class:log-event")
    def _logok(self, t: str) -> None: self._log(t, "class:log-ok")
    def _logw(self, t: str) -> None: self._log(t, "class:log-warn")
    def _loge(self, t: str) -> None: self._log(t, "class:log-error")

    # ── Commands ───────────────────────────────────────────────────────────

    def _on_enter(self, buf: Buffer) -> None:
        line = buf.text.strip()
        buf.reset()
        self._history_pos  = -1
        self._history_draft = ""
        if line:
            if not self._history or self._history[-1] != line:
                self._history.append(line)
            asyncio.get_event_loop().create_task(self._dispatch_cmd(line))

    async def _dispatch_cmd(self, line: str) -> None:
        parts = line.split()
        cmd   = parts[0].lower() if parts else ""

        match cmd:
            case "scan" | "s":
                dur = float(parts[1]) if len(parts) > 1 else 5.0
                await self._cmd_scan(dur)

            case "connect" | "c":
                idx = int(parts[1]) - 1 if len(parts) > 1 else 0
                await self._cmd_connect(idx)

            case "disconnect" | "d":
                addr = self._resolve_addr(parts[1] if len(parts) > 1 else "1")
                await self._cmd_disconnect(addr)

            case "mode" | "m":
                addr   = self._resolve_addr(parts[1] if len(parts) > 1 else "1")
                motors = parts[2] if len(parts) > 2 else "A"
                mode   = int(parts[3]) if len(parts) > 3 else 1
                await self._cmd(addr, "set_mode", {"motors": motors, "mode": mode})

            case "speed":
                addr = self._resolve_addr(parts[1] if len(parts) > 1 else "1")
                a = int(parts[2]) if len(parts) > 2 else 0
                b = int(parts[3]) if len(parts) > 3 else 0
                c = int(parts[4]) if len(parts) > 4 else 0
                await self._cmd(addr, "set_speed", {"motor_a": a, "motor_b": b, "motor_c": c})

            case "stop":
                addr = self._resolve_addr(parts[1] if len(parts) > 1 else "1")
                await self._cmd(addr, "stop", {})

            case "ems" | "estim" | "e":
                # ems <n> <channel> <intensity|off> [mode=1] [freq=0] [pulse=0]
                # channel: A / B / AB
                # intensity: 1-276, or "off" to disable
                # mode: 1-16 fixed, 17 = custom
                # freq: 1-100 Hz (custom mode only)
                # pulse: 0-100 µs (custom mode only)
                if len(parts) < 4:
                    self._logw("usage: ems <n> <A|B|AB> <intensity|off> [mode] [freq] [pulse]")
                    return
                addr    = self._resolve_addr(parts[1])
                channel = parts[2].upper()
                raw_int = parts[3].lower()
                if raw_int == "off":
                    await self._cmd(addr, "set_channel",
                                    {"channel": channel, "enabled": False})
                else:
                    intensity = max(1, int(raw_int))   # clamp: 0 is invalid on device
                    mode      = int(parts[4]) if len(parts) > 4 else 1
                    freq      = int(parts[5]) if len(parts) > 5 else 0
                    pulse_us  = int(parts[6]) if len(parts) > 6 else 0
                    await self._cmd(addr, "set_channel", {
                        "channel":   channel,
                        "enabled":   True,
                        "intensity": intensity,
                        "mode":      mode,
                        "freq":      freq,
                        "pulse_us":  pulse_us,
                    })

            case "info" | "i":
                addr = self._resolve_addr(parts[1] if len(parts) > 1 else "1")
                await self._cmd(addr, "get_info", {})
                # also query battery for estim
                dev = self._devices.get(addr or "")
                if dev and dev.get("type") == "estim":
                    await self._cmd(addr, "get_battery", {})

            case "list" | "l":
                if self._devices:
                    for a, d in self._devices.items():
                        self._logi(f"  {d.get('name')}  {a}  {d.get('type')}")
                else:
                    self._logw("No connected devices")

            case "help" | "h" | "?":
                self._logi("── General ──────────────────────────────────")
                self._logi("scan [sec]  connect <n>  disconnect <n>")
                self._logi("stop <n>  info <n>  list")
                self._logi("── Toy (飞机杯/跳蛋) ────────────────────────")
                self._logi("mode <n> <motors> <mode>  (motors: A/B/C/AB/ABC, mode: 1-4)")
                self._logi("speed <n> <a> <b> <c>  (0–20 each)")
                self._logi("── Estim (二代电击器) ────────────────────────")
                self._logi("ems <n> <ch> <intensity> [mode] [freq] [pulse]")
                self._logi("  ch: A / B / AB  intensity: 1-276")
                self._logi("  mode: 1-16 fixed, 17=custom  freq: 1-100Hz  pulse: 0-100µs")
                self._logi("  ems 1 A off  → disable channel A")

            case "quit" | "q" | "exit":
                if self._app:
                    self._app.exit()

            case "":
                pass

            case _:
                self._logw(f"Unknown command: {cmd!r}  (type 'help')")

    async def _cmd_scan(self, duration: float = 5.0) -> None:
        if not self._ws:
            self._loge("Not connected to server")
            return
        self._scanning = True
        if self._app:
            self._app.invalidate()
        self._logi(f"Scanning {duration:.0f}s…")
        try:
            resp = await self._ws.send("scan", {"duration": duration})
            self._scan_results = resp.get("devices", [])
            self._logi(f"Found {len(self._scan_results)} device(s)")
            for d in self._scan_results:
                self._log(f"  [{self._scan_results.index(d)+1}] {d['name'] or d['address']}  {d['device_type']}  rssi={d.get('rssi')}")
        except Exception as exc:
            self._loge(f"Scan error: {exc}")
        finally:
            self._scanning = False
            if self._app:
                self._app.invalidate()

    async def _cmd_connect(self, idx: int) -> None:
        if not self._scan_results:
            self._logw("Run scan first")
            return
        if idx < 0 or idx >= len(self._scan_results):
            self._logw(f"Index {idx+1} out of range (1–{len(self._scan_results)})")
            return
        d = self._scan_results[idx]
        self._logi(f"Connecting {d['name'] or d['address']}…")
        try:
            resp = await self._ws.send("connect", {
                "address": d["address"],
                "name": d["name"],
                "device_type": d["device_type"],
            })
            if resp.get("ok"):
                self._logok(f"Connected {d['name']}")
            else:
                self._loge(f"Connect failed: {resp.get('error')}")
        except Exception as exc:
            self._loge(f"Connect error: {exc}")

    async def _cmd_disconnect(self, addr: str | None) -> None:
        if not addr:
            self._logw("No device (run 'list' to see connected)")
            return
        try:
            resp = await self._ws.send("disconnect", {"address": addr})
            if resp.get("ok"):
                self._logw(f"Disconnected {addr}")
                self._devices.pop(addr, None)
            else:
                self._loge(f"Disconnect error: {resp.get('error')}")
        except Exception as exc:
            self._loge(f"Disconnect error: {exc}")

    async def _quick_connect(self) -> None:
        await self._cmd_connect(0)

    async def _quick_disconnect(self) -> None:
        if self._devices:
            addr = next(iter(self._devices))
            await self._cmd_disconnect(addr)

    async def _cmd(self, addr: str | None, action: str, data: dict) -> None:
        if not addr:
            self._logw("No device selected")
            return
        try:
            resp = await self._ws.send("command", {
                "address": addr, "action": action, "data": data,
            })
            if resp.get("ok"):
                extra = ""
                if action == "get_info":
                    # toy
                    if "motor_a_modes" in resp:
                        extra = (f"  A:{resp.get('motor_a_modes')} "
                                 f"B:{resp.get('motor_b_modes')} "
                                 f"C:{resp.get('motor_c_modes')} modes  "
                                 f"battery:{resp.get('battery')}%")
                    # estim
                    elif "channels" in resp:
                        chs = resp["channels"]
                        parts = []
                        for ch, s in chs.items():
                            if s.get("enabled"):
                                parts.append(
                                    f"{ch}:on intensity={s.get('intensity')} mode={s.get('mode')}"
                                )
                            else:
                                parts.append(f"{ch}:off")
                        extra = "  " + "  ".join(parts)
                        if resp.get("battery") is not None:
                            extra += f"  battery:{resp['battery']}%"
                self._logok(f"✓ {action}{extra}")
            else:
                self._loge(f"✗ {action}: {resp.get('error')}")
        except Exception as exc:
            self._loge(f"✗ {action}: {exc}")

    def _resolve_addr(self, token: str) -> str | None:
        """Accept device index (1-based) or partial address."""
        try:
            idx = int(token) - 1
            if 0 <= idx < len(self._scan_results):
                return self._scan_results[idx]["address"]
            # indices beyond scan_results map to non-scan connected devices
            extra = [a for a in self._devices
                     if not any(r["address"] == a for r in self._scan_results)]
            extra_idx = idx - len(self._scan_results)
            if 0 <= extra_idx < len(extra):
                return extra[extra_idx]
        except ValueError:
            pass
        # partial address match
        token_up = token.upper()
        for addr in self._devices:
            if token_up in addr.upper():
                return addr
        for d in self._scan_results:
            if token_up in d["address"].upper():
                return d["address"]
        return None

    # ── WS event handler ───────────────────────────────────────────────────

    async def _handle_event(self, msg: dict) -> None:
        addr  = msg.get("address", "?")
        event = msg.get("event", "?")
        data  = msg.get("data", {})
        short = (data.get("name") or addr[-8:]).strip()

        match event:
            case "connected":
                self._devices[addr] = {**data, "connected": True}
                self._logok(f"● Connected  {short}")
            case "disconnected":
                self._devices.pop(addr, None)
                self._logw(f"○ Disconnected  {short}")
            case "battery":
                self._logi(f"🔋 {short}  {data.get('level')}%")
            case "device_info":
                self._logi(
                    f"ℹ {short}  "
                    f"A:{data.get('motor_a_modes')} "
                    f"B:{data.get('motor_b_modes')} "
                    f"C:{data.get('motor_c_modes')} modes"
                )
            case "channel_status":
                ch   = data.get("channel", "?")
                conn = data.get("connection", "?")
                if data.get("enabled"):
                    self._logi(
                        f"⚡ {short}  ch-{ch} on  "
                        f"intensity={data.get('intensity')}  "
                        f"mode={data.get('mode')}  [{conn}]"
                    )
                else:
                    self._logi(f"⚡ {short}  ch-{ch} off  [{conn}]")
            case "step":
                self._logi(f"👣 {short}  steps={data.get('count')}")
            case "angle":
                acc = data.get("accel", {})
                gyr = data.get("gyro",  {})
                self._logi(
                    f"📐 {short}  "
                    f"accel=({acc.get('x')},{acc.get('y')},{acc.get('z')})  "
                    f"gyro=({gyr.get('x')},{gyr.get('y')},{gyr.get('z')})"
                )
            case "device_error":
                self._loge(f"⚠ {short}  {data.get('code')}")
            case "error":
                self._loge(f"⚠ {short}  {data.get('message')}")
            case _:
                self._log(f"{event}  {short}  {data}")

        if self._app:
            self._app.invalidate()

    # ── Entry point ────────────────────────────────────────────────────────

    async def run_async(self) -> None:
        # Connect to WS server
        try:
            self._ws = WSClient(self._ws_url)
            self._ws.on_event(self._handle_event)
            await self._ws.connect()
            self._logok(f"Connected to WS server  {self._ws_url}")
            # load already-connected devices
            resp = await self._ws.send("list_devices", {})
            for d in resp.get("devices", []):
                if d.get("connected"):
                    self._devices[d["address"]] = d
        except Exception as exc:
            self._loge(f"Cannot reach server: {exc}")
            self._logw("Start server first:  python main.py server")

        # Run prompt_toolkit application
        self._app = self._build_app()
        try:
            await self._app.run_async()
        finally:
            if self._ws:
                await self._ws.close()


def run_tui(ws_url: str = WS_URL) -> None:
    asyncio.run(YokoNexApp(ws_url).run_async())
