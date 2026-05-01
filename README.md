<div align="center">

# YokoNex OpenCLI

**役次元统一蓝牙设备客户端 / Unified BLE Device Client for YokoNex**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Protocol](https://img.shields.io/badge/BLE-YSKJ_TOY_BLE_V1.1-purple)](docs/飞机杯蓝牙协议.md)

</div>

---

> 🇨🇳 [中文](#中文) | 🇬🇧 [English](#english)

---

## 中文

### 简介

YokoNex OpenCLI 是役次元（YokoNex）系列智能设备的统一蓝牙控制客户端。通过 WebSocket 桥接层，任意数量的设备可以同时连接并独立控制；上层客户端（TUI、Web、脚本、移动 App）通过标准 JSON API 与设备通信，无需关心底层蓝牙细节。

本仓库包含四个组件：

| 目录 | 说明 |
|------|------|
| `yokonex/` | Python BLE 服务端（可打包为 whl） |
| `YCY-VRCOSC/` | VRChat OSC 桥接 GUI（PySide6） |
| `YokoNex-Cloud/` | Node.js 云端 WS 中继服务器 |
| `YokoNex-Flutter/` | Flutter 移动客户端（Android / iOS） |

### 整体架构

```
[Flutter App (Android/iOS)]     [VRChat (PC)]
        │ wss://                      │ OSC UDP:9001
        ▼                             ▼
[YokoNex-Cloud]            [YCY-VRCOSC GUI]
  Node.js 云端中继                  │
        │ ws://                       │
        ▼                             ▼
[yokonex agent --cloud]     [YokoNex WS Server  ws://127.0.0.1:8765]
   Python 桥接          ──────────────┘
                                      │ BLE (bleak)
                                      ▼
                                  [设备 (YSKJ_TOY_BLE V1.1)]
```

### 支持设备

| 设备类型 | `device_type` | BLE 服务 UUID | 名称前缀 | 协议文档 |
|---------|--------------|--------------|---------|---------|
| 役次元 榨精机PRO | `toy` | `FF40` | `YCY-FJB-03` | [飞机杯蓝牙协议](docs/飞机杯蓝牙协议.md) |

```
该设备拥有3个马达，A为主电机，B为吮吸强度，C为震动强度。速度范围 0-20，模式 1-4。
```

---

### 一、Python BLE 服务端（yokonex）

#### 安装

```bash
pip install -r requirements.txt
# 或直接安装 whl
pip install dist/yokonex_opencli-*.whl
```

#### 启动

```bash
# 推荐：服务端 + TUI 同时启动
yokonex server --tui

# 仅启动服务端（供其他客户端连接）
yokonex server

# 自定义端口
yokonex server --host 0.0.0.0 --port 9000
```

#### 云桥模式（配合 YokoNex-Cloud 使用）

```bash
# 先在本机启动 BLE 服务端
yokonex server

# 另开终端，注册为云端 Agent
yokonex agent --cloud wss://your-server:8080 --token <AGENT_TOKEN> --agent-id home-pc
```

#### TUI 快捷键

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
info <编号>                  查询设备信息和电量
list                         列出所有已连接设备
help                         帮助
```

---

### 二、VRChat OSC 桥接（YCY-VRCOSC）

通过 VRChat OSC 接口控制设备，支持 SoundPad 面板 + PhysBone 交互参数映射。详见 [YCY-VRCOSC/README.md](YCY-VRCOSC/README.md)。

```bash
cd YCY-VRCOSC
pip install -r requirements.txt
python src/app.py
```

---

### 三、云端 WS 中继（YokoNex-Cloud）

Node.js 服务器，将远程移动客户端与本地 Python BLE 服务端桥接。透明代理，whl 升级后无需修改。详见 [YokoNex-Cloud/README.md](YokoNex-Cloud/README.md)。

```bash
cd YokoNex-Cloud
cp .env.example .env   # 配置 AGENT_TOKEN 和 CLIENT_TOKEN
npm install
npm start
```

---

### 四、Flutter 移动客户端（YokoNex-Flutter）

Android / iOS 远程控制 App，通过云端 WS 服务操控设备。详见 [YokoNex-Flutter/README.md](YokoNex-Flutter/README.md)。

```bash
cd YokoNex-Flutter
flutter pub get
flutter run
```

---

### 项目结构

```
YokoNex-OpenCLI/
├── yokonex/                     # Python BLE 服务端 (whl)
│   ├── main.py                  # CLI 入口（server / tui / agent）
│   ├── core/
│   │   ├── ws_server.py         # WebSocket 服务端
│   │   ├── device_manager.py    # 多设备生命周期管理
│   │   ├── base_device.py       # 设备抽象基类
│   │   └── cloud_bridge.py      # 云桥（agent 模式）
│   ├── devices/
│   │   ├── registry.py          # 设备类型注册表
│   │   └── toy/
│   │       ├── protocol.py      # YSKJ_TOY_BLE V1.1 报文
│   │       └── device.py        # ToyDevice 实现
│   ├── ble/scanner.py
│   └── frontend/tui.py
├── YCY-VRCOSC/                  # VRChat OSC 桥接 GUI
├── YokoNex-Cloud/               # Node.js 云端 WS 中继
│   └── src/index.js
└── YokoNex-Flutter/             # Flutter 移动客户端
    └── lib/
        ├── api/yokonex_client.dart
        └── screens/
```

### 添加新设备类型

1. 新建 `yokonex/devices/<type>/` 目录
2. 实现 `protocol.py`（报文构建/解析）
3. 实现继承 `BaseDevice` 的设备类，添加 `@register` 装饰器
4. 在 `yokonex/main.py` 顶部 import 新模块

云端中继和移动客户端**无需修改**即可支持新设备类型。

### 免责声明

本项目依据役次元官方开源协议二次开发。使用者须遵循设备官方文档中的安全使用规范。作者不对因使用本软件造成的任何损失负责。

---

## English

### Overview

YokoNex OpenCLI is a unified Bluetooth control client for the YokoNex series of smart devices. A WebSocket bridge layer allows any number of devices to be connected simultaneously and controlled independently. Upper-layer clients (TUI, web, scripts, mobile apps) communicate through a standard JSON API without dealing with BLE details.

This repository contains four components:

| Directory | Description |
|-----------|-------------|
| `yokonex/` | Python BLE server (packaged as whl) |
| `YCY-VRCOSC/` | VRChat OSC bridge GUI (PySide6) |
| `YokoNex-Cloud/` | Node.js cloud WS relay server |
| `YokoNex-Flutter/` | Flutter mobile client (Android / iOS) |

### Architecture

```
[Flutter App (Android/iOS)]     [VRChat (PC)]
        │ wss://                      │ OSC UDP:9001
        ▼                             ▼
[YokoNex-Cloud]            [YCY-VRCOSC GUI]
  Node.js relay                       │
        │ ws://                       │
        ▼                             ▼
[yokonex agent --cloud]   [YokoNex WS Server  ws://127.0.0.1:8765]
   Python bridge      ────────────────┘
                                      │ BLE (bleak)
                                      ▼
                                [Device (YSKJ_TOY_BLE V1.1)]
```

### Supported Devices

| Device | `device_type` | BLE Service UUID | Name Prefix | Protocol Doc |
|--------|--------------|-----------------|-------------|--------------|
| Masturbator / Vibrator | `toy` | `FF40` | `YCY-FJB`, `YCY-TDD` | [TOY BLE Protocol](docs/飞机杯蓝牙协议.md) |

### Quick Start

#### Python BLE Server

```bash
pip install -r requirements.txt

# Start server + TUI
yokonex server --tui

# Cloud agent mode (bridge to YokoNex-Cloud)
yokonex server &
yokonex agent --cloud wss://your-server:8080 --token <AGENT_TOKEN> --agent-id home-pc
```

#### Cloud Relay (Node.js)

```bash
cd YokoNex-Cloud
cp .env.example .env  # set AGENT_TOKEN and CLIENT_TOKEN
npm install && npm start
```

#### Flutter Mobile App

```bash
cd YokoNex-Flutter
flutter pub get && flutter run
```

#### VRChat OSC Bridge

```bash
cd YCY-VRCOSC && pip install -r requirements.txt && python src/app.py
```

### Adding a New Device Type

1. Create `yokonex/devices/<type>/` directory
2. Implement `protocol.py` (packet builder/parser)
3. Subclass `BaseDevice` with `@register` decorator
4. Import the new module in `yokonex/main.py`

The cloud relay and mobile client require **no changes** to support new device types.

### Disclaimer

This project is based on the official YokoNex open-source protocol. Users must follow the safety guidelines in the official device documentation. The author is not responsible for any loss caused by the use of this software.

---

<div align="center">

Built on [YCY-YOKONEX-OpenSource](https://github.com/YCY-YOKONEX/YCY-YOKONEX-OpenSource) · MIT License

</div>
