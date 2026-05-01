# YokoNex-Cloud

Node.js WebSocket relay server. Bridges remote Flutter clients to local Python `yokonex server` instances (agents) over the internet.

## Architecture

```
[Flutter App]                      [PC near BLE device]
     |                                      |
     | wss:// (internet)                    | ws://127.0.0.1:8765 (loopback)
     |                                      |
[YokoNex-Cloud  ←←←←←←←←←←←←←← yokonex agent --cloud]
  (Node.js relay)                   (Python bridge)
                                           |
                                        BLE (bleak)
                                           |
                                       Toy Device
```

## Quick start

```bash
cp .env.example .env
# Edit .env: set AGENT_TOKEN and CLIENT_TOKEN

npm install
npm start
```

## Environment

| Variable       | Default               | Description                         |
|----------------|-----------------------|-------------------------------------|
| `PORT`         | `8080`                | WS server port                      |
| `HOST`         | `0.0.0.0`             | Bind address                        |
| `AGENT_TOKEN`  | `yokonex-agent-dev`   | PSK for local Python agents         |
| `CLIENT_TOKEN` | `yokonex-client-dev`  | PSK for Flutter / mobile clients    |

## On the PC side

```bash
# Start local BLE server
yokonex server

# In another terminal, start the cloud bridge
yokonex agent --cloud wss://your-server:8080 --token <AGENT_TOKEN> --agent-id home-pc
```

## Protocol

All messages are JSON. The cloud server is a transparent proxy — it adds no device logic and automatically supports every command in the yokonex protocol.

### Client messages
| type            | params                        | description                      |
|-----------------|-------------------------------|----------------------------------|
| `client_hello`  | `token`                       | Auth (first message)             |
| `list_agents`   | —                             | List registered agents           |
| `subscribe`     | `agent_id`                    | Subscribe to an agent            |
| `scan`          | `params.duration`             | Forwarded to agent               |
| `connect`       | `params.address/name/type`    | Forwarded to agent               |
| `disconnect`    | `params.address`              | Forwarded to agent               |
| `command`       | `params.address/action/data`  | Forwarded to agent               |
| `list_devices`  | `params`                      | Forwarded to agent               |

### Agent messages
| type            | description                                       |
|-----------------|---------------------------------------------------|
| `agent_hello`   | Auth + registration (first message)               |
| `{ id, ok, … }` | Response — routed to originating client           |
| `event`         | Device event — broadcast to all subscribed clients|

## Upgrading the whl

When `yokonex-opencli` is upgraded with new device types or commands, the cloud server requires **no changes** — it proxies all JSON transparently.
