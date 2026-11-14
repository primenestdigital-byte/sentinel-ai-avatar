# SENTINEL — Holographic AI Avatar

A live, browser-based AI avatar interface in the JARVIS holographic style, with **100% real system telemetry** — nothing simulated.

## Live Demo
Running at: `http://<server-ip>:9090`

## Features
- **Holographic UI** — glass panels, arc-reactor rings, particles, 3D mouse-tilt, boot sequence
- **Ultron-class face** — SVG line-art helmet with articulated mouth grille, blinking eyes, state-reactive colors
- **Real telemetry** — CPU, memory, swap, disk, network I/O, TCP latency, kernel entropy, uptime, process count, TCP connections — all read directly from `/proc` and `/sys`
- **Live process table** — top processes by CPU time (parsed from `/proc/<pid>/stat`)
- **Auto mode** — the avatar's mood (idle / thinking / speaking / alert) is driven by actual CPU load
- **Stale detection** — alerts if the backend stops responding

## Files
| File | Description |
|---|---|
| `index.html` | Complete frontend (HTML/CSS/JS, no build step) |
| `server.py` | Pure Python stdlib backend — telemetry + process API + static server, port 9090 |

## Run
```bash
python3 server.py
# open http://localhost:9090
```

No dependencies required — Python 3 standard library only.
