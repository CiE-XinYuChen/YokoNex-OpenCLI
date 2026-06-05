<div align="center">

# YokoNex OpenCLI

**役次元统一蓝牙设备客户端 / Unified BLE Device Client for YokoNex**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Protocol TOY](https://img.shields.io/badge/BLE-YSKJ_TOY_BLE_V1.1-purple)](docs/飞机杯蓝牙协议.md)
[![Protocol EMS](https://img.shields.io/badge/BLE-YSKJ_EMS_BLE_V1.6-red)](docs/二代电击器蓝牙协议.md)

</div>

---

> 🇨🇳 [中文](#中文) | 🇬🇧 [English](#english)

---

## 中文

### 简介

YokoNex OpenCLI 是役次元（YokoNex）系列智能设备的统一蓝牙控制客户端。通过 WebSocket 桥接层，任意数量的设备可以同时连接并独立控制；上层客户端（TUI、Web、脚本）通过标准 JSON API 与设备通信，无需关心底层蓝牙细节。

### 特性

- **统一架构** — 飞机杯、跳蛋、电击器等所有设备共用同一套 WS API
- **多设备并发** — 可同时连接任意数量设备，互不干扰

### 支持设备

| 设备类型 | `device_type` | BLE 服务 UUID | 名称前缀 | 协议文档 |
|---------|--------------|--------------|---------|---------|
| 役次元 榨精机PRO | `toy` | `FF40` | `YCY-FJB-03` | [飞机杯蓝牙协议](docs/飞机杯蓝牙协议.md) |
```
该设备拥有3个马达，A为主电机，B为吮吸强度，C为震动强度。
```
| 设备类型 | `device_type` | BLE 服务 UUID | 名称前缀 | 协议文档 |
|---------|--------------|--------------|---------|---------|
| 役次元 电击器 | `estim` | `FF30` | `YCY-EMS`, `YCY-DJQ`, `YSKJ-EMS` | [二代电击器蓝牙协议](docs/二代电击器蓝牙协议.md) |


### 快速开始

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 启动

```bash
# 推荐：服务端 + TUI 同时启动
python main.py server --tui

# 分开启动（两个终端）
python main.py server          # 终端 1：启动 WS 服务端
python main.py tui             # 终端 2：启动 TUI

# 自定义端口
python main.py server --host 0.0.0.0 --port 9000
python main.py tui   --host 192.168.1.100 --port 9000
```

#### 3. TUI 使用

| 快捷键 | 功能 |
|--------|------|
| `F5` | 扫描设备 |
| `F2` | 连接列表中第一个设备 |
| `F3` | 断开第一个已连接设备 |
| `q` | 退出 |

命令行（底部输入框）：

```
scan [秒数]                  扫描设备，默认 5 秒
connect <编号>               连接扫描列表中第 n 个设备
disconnect <编号|地址>        断开连接
mode <编号> <马达> <模式>      设置固定模式，马达：A/B/C/AB/ABC
speed <编号> <A> <B> <C>     实时速率，0–20
stop <编号>                  停止所有马达
info <编号>                   查询设备信息和电量
list                         列出所有已连接设备
help                         帮助
```

### 项目结构

```
YokoNex-OpenCLI/
├── main.py                  # 入口
├── requirements.txt
├── core/
│   ├── base_device.py       # 设备抽象基类（扩展接口）
│   ├── device_manager.py    # 多设备生命周期管理
│   └── ws_server.py         # WebSocket 服务端
├── devices/
│   ├── registry.py          # 设备类型注册表
│   └── toy/
│       ├── protocol.py      # YSKJ_TOY_BLE V1.1 报文构建/解析
│       └── device.py        # ToyDevice 实现
├── ble/
│   └── scanner.py           # BLE 扫描器
├── frontend/
│   └── tui.py               # 终端 UI
└── docs/
    ├── union-api.md          # 统一 WS API 文档
    ├── 飞机杯蓝牙协议.md
    └── 二代电击器蓝牙协议.md
```

### 添加新设备类型

1. 新建 `devices/<type>/` 目录
2. 实现 `protocol.py`（报文构建/解析）
3. 实现继承 `BaseDevice` 的设备类，添加 `@register` 装饰器
4. 在 `main.py` 顶部添加一行 `import devices.<type>.device`

详见 [Union API 文档 — 扩展指南](docs/union-api.md#扩展指南)。

### 免责声明

本项目依据役次元官方开源协议二次开发。使用者须遵循设备官方文档中的安全使用规范。作者不对因使用本软件造成的任何损失负责。

---

## English

### Overview

YokoNex OpenCLI is a unified Bluetooth control client for the YokoNex series of smart devices. A WebSocket bridge layer allows any number of devices to be connected simultaneously and controlled independently. Upper-layer clients (TUI, web, scripts) communicate with devices through a standard JSON API without worrying about the underlying BLE details.

### Features

- **Unified architecture** — All devices (masturbator, vibrator, e-stim, etc.) share the same WS API
- **Multi-device concurrency** — Connect any number of devices simultaneously without interference
- **Dual device discovery** — Supports both Service UUID matching and device name prefix matching (handles devices that don't advertise UUIDs in their broadcast packets)
- **Full-terminal TUI** — Full-screen terminal UI built on `prompt_toolkit`, no browser required
- **Easy to extend** — Adding a new device type only requires a new module with `@register`, no changes to core code
- **Open protocol** — Based on the official YokoNex open-source BLE protocol

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        Clients                           │
│         TUI (prompt_toolkit)  ·  Web  ·  Script          │
└──────────────────────┬───────────────────────────────────┘
                       │  WebSocket (JSON)
┌──────────────────────▼───────────────────────────────────┐
│                  WS Server (ws_server.py)                 │
│              core/device_manager.py                       │
└────────┬─────────────────────┬────────────────────────────┘
         │ BLE (bleak)         │ BLE (bleak)
┌────────▼──────┐     ┌────────▼──────┐     ┌─────────────┐
│  ToyDevice    │     │  EStimDevice  │     │  Future...  │
│(masturbator/  │     │  (e-stim)     │     │             │
│  vibrator)    │     │               │     │             │
└───────────────┘     └───────────────┘     └─────────────┘
```

### Supported Devices

| Device | `device_type` | BLE Service UUID | Name Prefix | Protocol Doc |
|--------|--------------|-----------------|-------------|--------------|
| Masturbator / Vibrator | `toy` | `FF40` | `YCY-FJB`, `YCY-TDD` | [TOY BLE Protocol](docs/飞机杯蓝牙协议.md) |
| E-Stim Device | `estim` | `FF30` | `YCY-EMS`, `YCY-DJQ`, `YSKJ-EMS` | [EMS BLE Protocol](docs/二代电击器蓝牙协议.md) |

### Quick Start

#### 1. Install dependencies

```bash
pip install -r requirements.txt
```

#### 2. Run

```bash
# Recommended: start server + TUI together
python main.py server --tui

# Separate (two terminals)
python main.py server          # Terminal 1: WS server
python main.py tui             # Terminal 2: TUI

# Custom host/port
python main.py server --host 0.0.0.0 --port 9000
python main.py tui   --host 192.168.1.100 --port 9000
```

#### 3. TUI shortcuts

| Key | Action |
|-----|--------|
| `F5` | Scan for devices |
| `F2` | Connect first device in scan list |
| `F3` | Disconnect first connected device |
| `q` | Quit |

Command line (bottom input box):

```
scan [sec]                   Scan for devices, default 5 sec
connect <n>                  Connect n-th device in scan list
disconnect <n|addr>          Disconnect device
mode <n> <motors> <mode>     Set fixed mode; motors: A/B/C/AB/ABC
speed <n> <A> <B> <C>        Real-time speed, 0–20 per motor
stop <n>                     Stop all motors
info <n>                     Query device info and battery
list                         List all connected devices
help                         Show help
```

### Adding a New Device Type

1. Create `devices/<type>/` directory
2. Implement `protocol.py` (packet builder/parser)
3. Implement a class inheriting `BaseDevice` with `@register` decorator
4. Add `import devices.<type>.device` at the top of `main.py`

See the [Union API — Extension Guide](docs/union-api.md#extension-guide).

### Disclaimer

This project is based on the official YokoNex open-source protocol. Users must follow the safety guidelines in the official device documentation. The author is not responsible for any loss caused by the use of this software.

---

<div align="center">

Built on [YCY-YOKONEX-OpenSource](https://github.com/YCY-YOKONEX/YCY-YOKONEX-OpenSource) · MIT License

</div>
