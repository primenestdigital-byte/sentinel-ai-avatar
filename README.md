# J.A.R.V.I.S. — Holographic Interface

A live, browser-based AI avatar interface styled after the Iron Man J.A.R.V.I.S. HUD — central rotating ring assembly, sweep radar, boot sequence — with **100% real system telemetry**, nothing simulated.

> Redesigned 2026-11-14 from the earlier SENTINEL look (original kept as `index.sentinel-v1.bak.html`).

## Live Demo
Running at: `http://<server-ip>:9090`

## Features
- **3D holographic helmet** — real Iron Man helmet model (glTF) rendered in Three.js: cyan wireframe + fresnel rim glow, slow oscillation, mouse-tilt parallax, state-reactive color, eye blink, speaking pulse (SVG face kept as automatic fallback)
- **Holographic UI** — glass panels, arc-reactor rings, particles, 3D mouse-tilt, boot sequence
- **Ultron-class face** — SVG line-art helmet with articulated mouth grille, blinking eyes, state-reactive colors (fallback display)
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

## 3D model
`models/helmet.gltf` + `models/helmet.bin` — Iron Man mask geometry, textures stripped (hologram is wireframe-only). Source: [ThorstenBux/halloween-masks](https://github.com/ThorstenBux/halloween-masks) on GitHub. For personal/non-commercial use.
