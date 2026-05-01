"""YSKJ_EMS_BLE V1.6 — 二代电击器报文构建与解析。

Service : FF30
Write   : FF31  (WRITE_WITHOUT_RESPONSE)
Notify  : FF32
"""
from __future__ import annotations

from typing import Optional

HEADER = 0x35

CMD_CHANNEL = 0x11  # EMS 通道控制
CMD_MOTOR   = 0x12  # 震动马达控制
CMD_STEP    = 0x13  # 计步功能控制
CMD_ANGLE   = 0x14  # 角度传感器控制
CMD_QUERY   = 0x71  # 查询 / 状态应答 / 异常上报

# 通道号
CHANNEL_A  = 0x01
CHANNEL_B  = 0x02
CHANNEL_AB = 0x03

# 通道模式
MODE_CUSTOM = 0x11   # 自定义模式（频率+脉冲时间）
MODE_MAX    = 0x10   # 最大固定模式编号

# EMS 强度范围
INTENSITY_MIN = 1
INTENSITY_MAX = 276  # 0x114

# 计步状态
STEP_START  = 0x01
STEP_STOP   = 0x00
STEP_RESET  = 0x02
STEP_PAUSE  = 0x03
STEP_RESUME = 0x04

# 查询类型
QUERY_CHANNEL_A = 0x01
QUERY_CHANNEL_B = 0x02
QUERY_MOTOR     = 0x03
QUERY_BATTERY   = 0x04
QUERY_STEP      = 0x05
QUERY_ANGLE     = 0x06

# 通道连接状态
CONN_DISCONNECTED  = 0x00
CONN_ACTIVE        = 0x01  # 已接入并在放电
CONN_CONNECTED     = 0x02  # 已接入未放电

_CONN_LABELS = {
    CONN_DISCONNECTED: "disconnected",
    CONN_ACTIVE:       "active",
    CONN_CONNECTED:    "connected",
}

_CHANNEL_BYTES = {"A": CHANNEL_A, "B": CHANNEL_B, "AB": CHANNEL_AB}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pack(*args: int) -> bytes:
    payload = bytes(args)
    return payload + bytes([sum(payload) & 0xFF])


def _clamp_intensity(v: int) -> int:
    return max(INTENSITY_MIN, min(INTENSITY_MAX, int(v)))


# ── Builders ──────────────────────────────────────────────────────────────────

def build_channel(
    channel: str,
    enabled: bool,
    intensity: int,
    mode: int,
    freq: int = 0,
    pulse_us: int = 0,
) -> bytes:
    """
    channel  : "A" | "B" | "AB"
    enabled  : True = 开启输出
    intensity: 1–276（关闭时忽略）
    mode     : 1–16 固定模式；17 (0x11) 自定义模式
    freq     : 自定义模式频率，1–100 Hz（固定模式填 0）
    pulse_us : 自定义模式脉冲时间，0–100 µs（固定模式填 0）
    """
    ch  = _CHANNEL_BYTES.get(channel.upper(), CHANNEL_A)
    en  = 0x01 if enabled else 0x00
    if not enabled:
        return _pack(HEADER, CMD_CHANNEL, ch, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)
    itensity = _clamp_intensity(intensity)
    hi  = (itensity >> 8) & 0xFF
    lo  = itensity & 0xFF
    md  = max(1, min(MODE_CUSTOM, int(mode))) & 0xFF
    fq  = max(1, min(100, int(freq)))   & 0xFF if md == MODE_CUSTOM else 0
    pu  = max(0, min(100, int(pulse_us))) & 0xFF if md == MODE_CUSTOM else 0
    return _pack(HEADER, CMD_CHANNEL, ch, en, hi, lo, md, fq, pu)


def build_stop() -> bytes:
    """同时关闭 A、B 两路通道。"""
    return _pack(HEADER, CMD_CHANNEL, CHANNEL_AB, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)


def build_motor(state: int) -> bytes:
    """
    state: 0x00 关闭 | 0x01 开启 | 0x11/0x12/0x13 预设频率 1/2/3
    """
    return _pack(HEADER, CMD_MOTOR, state & 0xFF)


def build_step(state: int) -> bytes:
    """state: STEP_START / STEP_STOP / STEP_RESET / STEP_PAUSE / STEP_RESUME"""
    return _pack(HEADER, CMD_STEP, state & 0xFF)


def build_angle(enabled: bool) -> bytes:
    return _pack(HEADER, CMD_ANGLE, 0x01 if enabled else 0x00)


def build_query(query_type: int) -> bytes:
    return _pack(HEADER, CMD_QUERY, query_type & 0xFF)


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_notify(data: bytes) -> Optional[dict]:
    if len(data) < 3 or data[0] != HEADER:
        return None

    cmd = data[1]

    if cmd != CMD_QUERY:
        return {"type": "raw", "hex": data.hex()}

    qtype = data[2]

    # 通道 A / B 状态
    if qtype in (QUERY_CHANNEL_A, QUERY_CHANNEL_B) and len(data) >= 9:
        return {
            "type":       "channel_status",
            "channel":    "A" if qtype == QUERY_CHANNEL_A else "B",
            "connection": _CONN_LABELS.get(data[3], "unknown"),
            "enabled":    bool(data[4]),
            "intensity":  (data[5] << 8) | data[6],
            "mode":       data[7],
        }

    # 马达状态
    if qtype == QUERY_MOTOR and len(data) >= 5:
        return {"type": "motor_status", "state": data[3]}

    # 电池电量
    if qtype == QUERY_BATTERY and len(data) >= 5:
        return {"type": "battery", "level": int(data[3])}

    # 计步数据
    if qtype == QUERY_STEP and len(data) >= 6:
        return {"type": "step", "count": (data[3] << 8) | data[4]}

    # 角度 / 六轴原始数据
    if qtype == QUERY_ANGLE and len(data) >= 16:
        def _s16(hi: int, lo: int) -> int:
            v = (hi << 8) | lo
            return v - 65536 if v >= 32768 else v

        return {
            "type":  "angle",
            "accel": {
                "x": _s16(data[3],  data[4]),
                "y": _s16(data[5],  data[6]),
                "z": _s16(data[7],  data[8]),
            },
            "gyro": {
                "x": _s16(data[9],  data[10]),
                "y": _s16(data[11], data[12]),
                "z": _s16(data[13], data[14]),
            },
        }

    # 异常上报
    if qtype == 0x55 and len(data) >= 5:
        _errors = {
            0x01: "checksum_error",
            0x02: "header_error",
            0x03: "command_error",
            0x04: "data_error",
            0x05: "not_implemented",
        }
        return {"type": "device_error", "code": _errors.get(data[3], f"0x{data[3]:02X}")}

    return {"type": "raw", "hex": data.hex()}
