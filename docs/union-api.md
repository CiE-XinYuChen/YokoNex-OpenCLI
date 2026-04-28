# YokoNex Union API

> 统一 WebSocket 接口规范 / Unified WebSocket Interface Specification  
> Version: 1.0  
> 适用版本 / Applicable: YokoNex OpenCLI ≥ 1.0

---

> 🇨🇳 [中文](#中文) | 🇬🇧 [English](#english)

---

## 中文

### 概述

YokoNex OpenCLI 以 **WebSocket** 为核心通信层，服务端负责管理 BLE 连接，任意数量的客户端（TUI、Web、脚本）可同时连接同一服务端，共享设备状态与事件流。

```
Client A ──┐
Client B ──┼── WebSocket ── WS Server ── BLE ── Device 1
Client C ──┘                         └── BLE ── Device 2
```

### 1. 连接参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| Host | `127.0.0.1` | 服务端监听地址，`--host` 参数可修改 |
| Port | `8765` | 服务端监听端口，`--port` 参数可修改 |
| 协议 | `ws://` | 标准 WebSocket，暂不支持 wss |
| 编码 | UTF-8 JSON | 所有消息均为 JSON 字符串 |

连接地址示例：`ws://127.0.0.1:8765`

---

### 2. 消息格式

#### 2.1 请求（Client → Server）

```json
{
  "id":     "req-001",
  "type":   "<消息类型>",
  "params": { ... }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 否 | 请求 ID，服务端原样返回，用于请求/响应匹配 |
| `type` | string | 是 | 消息类型，见下表 |
| `params` | object | 否 | 消息参数，不同类型有不同结构 |

#### 2.2 响应（Server → Client）

```json
{
  "id":    "req-001",
  "ok":    true,
  ...
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string\|null | 对应请求的 `id` |
| `ok` | boolean | `true` 成功，`false` 失败 |
| `error` | string | 仅 `ok=false` 时存在，错误原因 |
| 其他字段 | any | 各接口的业务数据 |

#### 2.3 事件推送（Server → All Clients）

设备状态变更时，服务端主动向所有已连接的 WS 客户端广播：

```json
{
  "type":    "event",
  "address": "<BLE 地址>",
  "event":   "<事件名>",
  "data":    { ... }
}
```

---

### 3. 请求接口

#### 3.1 `scan` — 扫描设备

扫描周边 BLE 设备，返回所有匹配 YokoNex 协议的设备列表。

**请求**

```json
{
  "id":     "req-001",
  "type":   "scan",
  "params": {
    "duration": 5.0
  }
}
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `duration` | float | 否 | `5.0` | 扫描持续时间（秒），建议 3–10 |

**响应**

```json
{
  "id":  "req-001",
  "ok":  true,
  "devices": [
    {
      "address":     "B4:88:8E:48:76:63",
      "name":        "YCY-FJB-03",
      "device_type": "toy",
      "rssi":        -65
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `devices` | array | 发现的设备列表 |
| `devices[].address` | string | BLE MAC 地址（macOS 为 UUID 格式） |
| `devices[].name` | string | 设备广播名 |
| `devices[].device_type` | string | 设备类型，如 `toy`、`estim` |
| `devices[].rssi` | integer\|null | 信号强度（dBm），越接近 0 越强 |

**设备发现策略**（按优先级）：
1. **Service UUID 匹配** — 广播包中包含对应 UUID
2. **名称前缀匹配** — 广播名以 `NAME_PREFIXES` 中的前缀开头（解决部分设备不广播 UUID 的问题）

---

#### 3.2 `connect` — 连接设备

建立 BLE 连接。连接成功后会自动查询设备信息并开始接收通知。

**请求**

```json
{
  "id":     "req-002",
  "type":   "connect",
  "params": {
    "address":     "B4:88:8E:48:76:63",
    "name":        "YCY-FJB-03",
    "device_type": "toy"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `address` | string | 是 | 设备 BLE 地址 |
| `name` | string | 否 | 设备名（用于日志和展示） |
| `device_type` | string | 否 | 设备类型，默认 `toy` |

**响应**

```json
{ "id": "req-002", "ok": true, "address": "B4:88:8E:48:76:63", "device_type": "toy" }
```

```json
{ "id": "req-002", "ok": false, "error": "already connected" }
```

**连接后自动触发的事件**：
- `connected` — 连接成功
- `device_info` — 设备信息（马达数量等）
- `battery` — 电池电量

---

#### 3.3 `disconnect` — 断开设备

**请求**

```json
{
  "id":     "req-003",
  "type":   "disconnect",
  "params": {
    "address": "B4:88:8E:48:76:63"
  }
}
```

**响应**

```json
{ "id": "req-003", "ok": true, "address": "B4:88:8E:48:76:63" }
```

```json
{ "id": "req-003", "ok": false, "error": "device not found" }
```

---

#### 3.4 `list_devices` — 列出已连接设备

**请求**

```json
{ "id": "req-004", "type": "list_devices", "params": {} }
```

**响应**

```json
{
  "id": "req-004",
  "ok": true,
  "devices": [
    {
      "address":   "B4:88:8E:48:76:63",
      "name":      "YCY-FJB-03",
      "type":      "toy",
      "connected": true
    }
  ]
}
```

---

#### 3.5 `command` — 设备控制命令

向指定设备发送控制命令。

**请求结构**

```json
{
  "id":   "req-005",
  "type": "command",
  "params": {
    "address": "B4:88:8E:48:76:63",
    "action":  "<动作名>",
    "data":    { ... }
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `address` | string | 是 | 目标设备地址 |
| `action` | string | 是 | 动作名，见各设备命令表 |
| `data` | object | 否 | 动作参数 |

---

### 4. 设备命令（Actions）

#### 4.1 ToyDevice — 飞机杯 / 跳蛋（`device_type: toy`）

##### `set_mode` — 固定模式

选择预设的固定震动模式。

```json
{
  "action": "set_mode",
  "data": {
    "motors": "A",
    "mode":   3
  }
}
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `motors` | string \| int | 否 | `"A"` | 马达选择，见下表 |
| `mode` | int | 是 | — | 模式编号，`0` 关闭；`1–N` 固定模式（N 由设备 `device_info` 返回） |

**`motors` 参数值**

| 值 | BLE 字节 | 说明 |
|----|---------|------|
| `"A"` 或 `1` | `0x01` | 仅 A 马达 |
| `"B"` 或 `2` | `0x02` | 仅 B 马达 |
| `"AB"` 或 `3` | `0x03` | A + B 马达同步 |
| `"C"` 或 `4` | `0x04` | 仅 C 马达 |
| `"ABC"` 或 `7` | `0x07` | A + B + C 马达同步 |

**响应**

```json
{ "id": "req-005", "ok": true }
```

---

##### `set_speed` — 实时速率控制

适用于手势模式、语音模式、自定义模式等实时下发场景。最快 **100ms** 一次。

```json
{
  "action": "set_speed",
  "data": {
    "motor_a": 10,
    "motor_b": 0,
    "motor_c": 0
  }
}
```

| 参数 | 类型 | 必填 | 范围 | 说明 |
|------|------|------|------|------|
| `motor_a` | int | 否 | `0–20` | A 马达力度，`0` 关闭 |
| `motor_b` | int | 否 | `0–20` | B 马达力度，`0` 关闭 |
| `motor_c` | int | 否 | `0–20` | C 马达力度，`0` 关闭 |

> **注意**：只有数值发生变化时才需要下发，避免无效流量。

---

##### `stop` — 停止所有马达

```json
{ "action": "stop", "data": {} }
```

等价于 `set_mode` 所有马达 `mode=0`。

**响应**

```json
{ "id": "req-005", "ok": true }
```

---

##### `get_info` — 查询设备信息

```json
{ "action": "get_info", "data": {} }
```

**响应**

```json
{
  "id":             "req-005",
  "ok":             true,
  "address":        "B4:88:8E:48:76:63",
  "name":           "YCY-FJB-03",
  "type":           "toy",
  "connected":      true,
  "motor_a_modes":  8,
  "motor_b_modes":  0,
  "motor_c_modes":  0,
  "battery":        70
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `motor_a_modes` | int | A 马达固定模式数量，`0` 表示无此马达 |
| `motor_b_modes` | int | B 马达固定模式数量 |
| `motor_c_modes` | int | C 马达固定模式数量 |
| `battery` | int\|null | 电池百分比，`null` 表示尚未收到数据 |

---

#### 4.2 EStimDevice — 二代电击器（`device_type: estim`，规划中）

> 文档见 [二代电击器蓝牙协议](二代电击器蓝牙协议.md)，API 接入后补充。

---

### 5. 事件（Events）

服务端在以下情况向所有 WS 客户端广播事件：
- 设备状态改变
- 设备主动上报数据（电量、传感器等）
- 异常发生

#### 5.1 `connected` — 设备已连接

```json
{
  "type":    "event",
  "address": "B4:88:8E:48:76:63",
  "event":   "connected",
  "data": {
    "address":   "B4:88:8E:48:76:63",
    "name":      "YCY-FJB-03",
    "type":      "toy",
    "connected": true
  }
}
```

#### 5.2 `disconnected` — 设备已断开

```json
{
  "type":    "event",
  "address": "B4:88:8E:48:76:63",
  "event":   "disconnected",
  "data":    { "address": "B4:88:8E:48:76:63" }
}
```

#### 5.3 `battery` — 电池电量上报

```json
{
  "type":    "event",
  "address": "B4:88:8E:48:76:63",
  "event":   "battery",
  "data":    { "type": "battery", "level": 70 }
}
```

#### 5.4 `device_info` — 设备信息上报

连接后由设备自动推送，包含马达数量等硬件信息。

```json
{
  "type":    "event",
  "address": "B4:88:8E:48:76:63",
  "event":   "device_info",
  "data": {
    "type":           "device_info",
    "product_id":     1,
    "version":        1,
    "motor_a_modes":  8,
    "motor_b_modes":  0,
    "motor_c_modes":  0
  }
}
```

#### 5.5 `error` — 设备异常

```json
{
  "type":    "event",
  "address": "B4:88:8E:48:76:63",
  "event":   "error",
  "data":    { "message": "connect timeout" }
}
```

---

### 6. 错误码

| `error` 内容 | 触发条件 |
|-------------|---------|
| `"invalid JSON"` | 请求体不是合法 JSON |
| `"unknown type: ..."` | `type` 字段值不被识别 |
| `"unknown device type: ..."` | `device_type` 未注册 |
| `"already connected"` | 目标设备已经连接中 |
| `"device not found"` | `address` 未在管理器中 |
| `"not connected"` | 对未连接设备发送命令 |
| `"unknown action: ..."` | `action` 不被该设备支持 |

---

### 7. 命令行参考

#### `main.py` 参数

```
用法: python main.py [mode] [选项]

位置参数:
  mode              运行模式：server（默认）或 tui

选项:
  --tui             与 server 模式同用，额外启动 TUI
  --host HOST       监听 / 连接地址，默认 127.0.0.1
  --port PORT       监听 / 连接端口，默认 8765
  -h, --help        显示帮助
```

**示例**

```bash
# 仅启动服务端（适合远程控制或脚本调用）
python main.py server

# 启动服务端，绑定所有网卡，供局域网内其他设备连接
python main.py server --host 0.0.0.0 --port 8765

# 仅启动 TUI，连接到已在运行的服务端
python main.py tui --host 192.168.1.100 --port 8765

# 服务端 + TUI 一键启动（最常用）
python main.py server --tui

# 自定义端口一键启动
python main.py server --tui --port 9999
```

#### TUI 命令（底部输入框）

| 命令 | 缩写 | 参数 | 说明 |
|------|------|------|------|
| `scan` | `s` | `[秒数]` | 扫描设备，默认 5s |
| `connect` | `c` | `<编号>` | 连接扫描列表中第 n 个设备（从 1 开始） |
| `disconnect` | `d` | `<编号\|地址>` | 断开设备 |
| `mode` | `m` | `<编号> <马达> <模式>` | 设置固定模式 |
| `speed` | — | `<编号> <A> <B> <C>` | 实时速率控制（0–20） |
| `stop` | — | `<编号>` | 停止所有马达 |
| `info` | `i` | `<编号>` | 查询设备信息 |
| `list` | `l` | — | 列出所有已连接设备 |
| `help` | `h` `?` | — | 显示帮助 |
| `quit` | `q` `exit` | — | 退出 |

`<编号>` 接受：
- 扫描列表中的序号（`1`、`2`……）
- BLE 地址的任意部分（如 `159E8`，大小写不敏感）

#### TUI 键盘快捷键

| 按键 | 功能 |
|------|------|
| `F5` | 扫描设备（5 秒） |
| `F2` | 连接扫描列表中第一个设备 |
| `F3` | 断开第一个已连接设备 |
| `Ctrl+C` | 退出 |
| `q`（非输入状态） | 退出 |

---

### 8. 扩展指南

#### 8.1 添加新设备类型

以添加「二代电击器」为例：

**Step 1 — 创建目录和协议模块**

```python
# devices/estim/protocol.py
HEADER       = 0x35
CMD_CHANNEL  = 0x11
SERVICE_UUID = "0000ff30-0000-1000-8000-00805f9b34fb"
WRITE_UUID   = "0000ff31-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID  = "0000ff32-0000-1000-8000-00805f9b34fb"

def build_channel_control(channel, enabled, strength, mode, freq, pulse): ...
def parse_notify(data: bytes) -> dict: ...
```

**Step 2 — 实现设备类**

```python
# devices/estim/device.py
from core.base_device import BaseDevice
from devices.registry import register
from . import protocol as proto

@register
class EStimDevice(BaseDevice):
    DEVICE_TYPE  = "estim"
    SERVICE_UUID = proto.SERVICE_UUID
    WRITE_UUID   = proto.WRITE_UUID
    NOTIFY_UUID  = proto.NOTIFY_UUID
    NAME_PREFIXES = ["YCY-EMS", "YCY-DJQ"]

    @classmethod
    def matches(cls, service_uuids):
        return proto.SERVICE_UUID.lower() in [u.lower() for u in service_uuids]

    async def connect(self): ...
    async def disconnect(self): ...

    async def handle_command(self, action, params):
        match action:
            case "set_channel": ...
            case "stop":        ...
            case "get_info":    ...
            case _:
                return {"ok": False, "error": f"unknown action: {action}"}
```

**Step 3 — 注册到入口**

```python
# main.py 顶部添加一行
import devices.estim.device  # noqa: F401
```

完成。WS 服务端、DeviceManager、TUI 均无需修改。

#### 8.2 自定义名称匹配

若设备名规律特殊，可覆写 `matches_name()`：

```python
@classmethod
def matches_name(cls, name: str) -> bool:
    # 匹配 "YSKJ-" 开头且第 6 位为 'E' 的设备
    return name.upper().startswith("YSKJ-") and len(name) > 5 and name[5].upper() == "E"
```

#### 8.3 自定义事件类型

在 `_on_notify` 中 `await self._emit("my_event", data)` 即可向所有 WS 客户端广播自定义事件。TUI 的 `_handle_event` 会通过 `case _:` 显示未知事件，无需修改。

---

### 9. 配置参数汇总

| 参数 | 来源 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | CLI | `127.0.0.1` | WS 服务端监听地址 |
| `--port` | CLI | `8765` | WS 服务端监听端口 |
| `--tui` | CLI | `false` | 随服务端启动 TUI |
| `WS_URL` | `frontend/tui.py` | `ws://127.0.0.1:8765` | TUI 连接的服务端地址 |
| `MAX_LOG` | `frontend/tui.py` | `200` | TUI 日志最大行数 |
| `scan duration` | WS params | `5.0` | 单次扫描时长（秒） |
| `send timeout` | `frontend/tui.py` | `15` s | WS 请求等待超时 |
| `NAME_PREFIXES` | 设备类 | 各不同 | BLE 设备名匹配前缀 |
| `logging level` | `main.py` | `INFO` | 日志等级，DEBUG 可见原始 BLE 包 |

---

## English

### Overview

YokoNex OpenCLI uses **WebSocket** as its core communication layer. The server manages BLE connections, and any number of clients (TUI, web, scripts) can connect to the same server simultaneously, sharing device state and event streams.

### 1. Connection Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Host | `127.0.0.1` | Server listen address, configurable with `--host` |
| Port | `8765` | Server listen port, configurable with `--port` |
| Protocol | `ws://` | Standard WebSocket, TLS not yet supported |
| Encoding | UTF-8 JSON | All messages are JSON strings |

Connection URL example: `ws://127.0.0.1:8765`

---

### 2. Message Format

#### 2.1 Request (Client → Server)

```json
{
  "id":     "req-001",
  "type":   "<message type>",
  "params": { ... }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | No | Request ID, echoed back in response for matching |
| `type` | string | Yes | Message type, see below |
| `params` | object | No | Parameters vary by type |

#### 2.2 Response (Server → Client)

```json
{
  "id":  "req-001",
  "ok":  true,
  ...
}
```

#### 2.3 Event Push (Server → All Clients)

When device state changes, the server broadcasts to all connected WS clients:

```json
{
  "type":    "event",
  "address": "<BLE address>",
  "event":   "<event name>",
  "data":    { ... }
}
```

---

### 3. Request Types

| `type` | Direction | Description |
|--------|-----------|-------------|
| `scan` | C→S | Scan for nearby BLE devices |
| `connect` | C→S | Connect to a BLE device |
| `disconnect` | C→S | Disconnect a device |
| `list_devices` | C→S | List all connected devices |
| `command` | C→S | Send a control command to a device |

---

### 4. Device Commands (Actions)

#### ToyDevice (`device_type: toy`)

| `action` | Key params | Description |
|----------|-----------|-------------|
| `set_mode` | `motors`, `mode` | Select fixed vibration mode |
| `set_speed` | `motor_a`, `motor_b`, `motor_c` | Real-time speed (0–20 each) |
| `stop` | — | Stop all motors |
| `get_info` | — | Query device info and battery |

#### EStimDevice (`device_type: estim`, planned)

See [EMS BLE Protocol](二代电击器蓝牙协议.md).

---

### 5. CLI Reference

```
usage: python main.py [mode] [options]

positional arguments:
  mode              server (default) or tui

options:
  --tui             also launch TUI alongside server
  --host HOST       listen/connect address, default 127.0.0.1
  --port PORT       listen/connect port, default 8765
  -h, --help        show help
```

### 6. TUI Command Reference

| Command | Short | Args | Description |
|---------|-------|------|-------------|
| `scan` | `s` | `[sec]` | Scan for devices, default 5s |
| `connect` | `c` | `<n>` | Connect n-th device in scan list |
| `disconnect` | `d` | `<n\|addr>` | Disconnect device |
| `mode` | `m` | `<n> <motors> <mode>` | Set fixed mode |
| `speed` | — | `<n> <A> <B> <C>` | Real-time speed control (0–20) |
| `stop` | — | `<n>` | Stop all motors |
| `info` | `i` | `<n>` | Query device info |
| `list` | `l` | — | List connected devices |
| `help` | `h` `?` | — | Show help |
| `quit` | `q` `exit` | — | Quit |

### 7. Configuration Summary

| Parameter | Source | Default | Description |
|-----------|--------|---------|-------------|
| `--host` | CLI | `127.0.0.1` | WS server listen address |
| `--port` | CLI | `8765` | WS server listen port |
| `--tui` | CLI | `false` | Launch TUI with server |
| `WS_URL` | `frontend/tui.py` | `ws://127.0.0.1:8765` | TUI server URL |
| `MAX_LOG` | `frontend/tui.py` | `200` | Max TUI log lines |
| `scan duration` | WS params | `5.0` | Scan duration in seconds |
| `send timeout` | `frontend/tui.py` | `15` s | WS request timeout |
| `NAME_PREFIXES` | device class | varies | BLE device name match prefixes |
| `logging level` | `main.py` | `INFO` | `DEBUG` shows raw BLE packets |

### 8. Extension Guide

To add a new device type, implement a class inheriting `BaseDevice`, decorate with `@register`, and add one import line to `main.py`. No changes to core infrastructure needed.

Required class attributes: `DEVICE_TYPE`, `SERVICE_UUID`, `WRITE_UUID`, `NOTIFY_UUID`, `NAME_PREFIXES`

Required methods: `matches()`, `connect()`, `disconnect()`, `handle_command()`
