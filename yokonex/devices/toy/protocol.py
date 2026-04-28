"""YSKJ_TOY_BLE V1.1 — Packet builder and parser.

Service : FF40
Write   : FF41  (WRITE_WITHOUT_RESPONSE)
Notify  : FF42
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

HEADER = 0x35

CMD_DEVICE_INFO = 0x10
CMD_FIXED_MODE  = 0x11
CMD_SPEED       = 0x12
CMD_BATTERY_RPT = 0x13  # device → host only
CMD_HEARTBEAT   = 0x14  # device → host, ~10 Hz keepalive, no payload

# Motor bitmasks
MOTOR_A = 0x01
MOTOR_B = 0x02
MOTOR_C = 0x04
MOTOR_ALL = MOTOR_A | MOTOR_B | MOTOR_C


# ── Builders ───────────────────────────────────────────────────────────────

def _pack(*bytes_: int) -> bytes:
    payload = bytes(bytes_)
    return payload + bytes([sum(payload) & 0xFF])


def build_device_info_query() -> bytes:
    return _pack(HEADER, CMD_DEVICE_INFO)


def build_fixed_mode(motors: int, mode: int) -> bytes:
    """
    motors: MOTOR_A | MOTOR_B | MOTOR_C bitmask
    mode  : 0 = off, 1..N = fixed mode number
    """
    return _pack(HEADER, CMD_FIXED_MODE, motors & 0x07, max(0, mode) & 0xFF)


def build_speed(motor_a: int = 0, motor_b: int = 0, motor_c: int = 0) -> bytes:
    """Real-time speed control. Values are 0 (off) or 1–20."""
    def clamp(v: int) -> int:
        return max(0, min(20, int(v)))

    return _pack(HEADER, CMD_SPEED, clamp(motor_a), clamp(motor_b), clamp(motor_c))


# ── Parser ─────────────────────────────────────────────────────────────────

def parse_notify(data: bytes) -> Optional[dict]:
    if len(data) < 3 or data[0] != HEADER:
        return None

    cmd = data[1]

    if cmd == CMD_DEVICE_INFO and len(data) >= 10:
        return {
            "type": "device_info",
            "product_id": data[2],
            "version": data[3],
            "motor_a_modes": data[4],
            "motor_b_modes": data[5],
            "motor_c_modes": data[6],
        }

    if cmd == CMD_BATTERY_RPT and len(data) >= 5 and data[2] == 0x01:
        return {"type": "battery", "level": int(data[3])}

    if cmd == CMD_HEARTBEAT:
        return {"type": "heartbeat"}

    return {"type": "raw", "hex": data.hex()}
