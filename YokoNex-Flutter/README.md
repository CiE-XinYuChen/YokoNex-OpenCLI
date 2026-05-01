# YokoNex Flutter

Flutter mobile client (Android / iOS) for remote device control via the YokoNex cloud WS relay.

## Architecture

```
[Flutter App] ──wss://──► [YokoNex-Cloud] ──ws://──► [yokonex agent] ──BLE──► Device
```

## Setup

```bash
# Flutter 3.x required
flutter pub get
flutter run   # connect a device or start an emulator
```

## App Flow

1. **Connect** — enter cloud server URL + client token
2. **Agent** — list online agents (local PCs), tap one to subscribe
3. **Scan** — discover nearby BLE devices
4. **Control** — adjust motor A / B / C speed (0–20) and mode (1–4)

## Screens

| Screen          | File                          |
|-----------------|-------------------------------|
| ConnectScreen   | `lib/screens/connect_screen.dart` |
| AgentScreen     | `lib/screens/agent_screen.dart`   |
| ScanScreen      | `lib/screens/scan_screen.dart`    |
| ControlScreen   | `lib/screens/control_screen.dart` |

The WS client SDK lives in `lib/api/yokonex_client.dart` — a `ChangeNotifier` wrapping `web_socket_channel`. Extend it when the yokonex whl gains new commands.

## Adding new device features

1. Add a method to `YokoNexClient` that calls `_request(...)` with the new action.
2. Update `ControlScreen` (or add a new screen) to expose the feature in the UI.
