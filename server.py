#!/usr/bin/env python3
"""Sentinel Core backend — serves the UI and real telemetry read from /proc & /sys."""
import json, os, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))


def read_cpu_times():
    with open("/proc/stat") as f:
        vals = list(map(int, f.readline().split()[1:]))
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
    return idle, sum(vals)


class Telemetry:
    def __init__(self):
        self.idle, self.total = read_cpu_times()
        self.last_t = time.time()
        self.cpu = 0.0
        self.last_net = self._read_net()
        self.net_rates = dict(rx_kbps=0.0, tx_kbps=0.0, rxps=0.0, txps=0.0)
        self.hist = []            # rolling cpu% history for the spectrum
        self.latency = None
        self._lat_probe_t = 0.0

    @staticmethod
    def _read_net():
        out = {}
        try:
            with open("/proc/net/dev") as f:
                for line in f.readlines()[2:]:
                    if ":" not in line:
                        continue
                    iface, cols = line.split(":", 1)
                    c = cols.split()
                    out[iface.strip()] = dict(rx=int(c[0]), rxp=int(c[1]),
                                              tx=int(c[8]), txp=int(c[9]))
        except OSError:
            pass
        return out

    def update(self):
        now = time.time()
        dt = max(now - self.last_t, 1e-3)
        idle, total = read_cpu_times()
        d_total = total - self.total
        self.cpu = 100.0 * (1 - (idle - self.idle) / d_total) if d_total > 0 else self.cpu
        self.cpu = max(0.0, min(100.0, self.cpu))
        self.idle, self.total = idle, total

        net = self._read_net()
        agg = dict(rx_kbps=0.0, tx_kbps=0.0, rxps=0.0, txps=0.0)
        for iface, d in net.items():
            p = self.last_net.get(iface)
            if not p or iface == "lo":
                continue
            agg["rx_kbps"] += max(0.0, (d["rx"] - p["rx"]) * 8 / 1000 / dt)
            agg["tx_kbps"] += max(0.0, (d["tx"] - p["tx"]) * 8 / 1000 / dt)
            agg["rxps"]    += max(0.0, (d["rxp"] - p["rxp"]) / dt)
            agg["txps"]    += max(0.0, (d["txp"] - p["txp"]) / dt)
        self.last_net, self.last_t = net, now
        self.net_rates = agg

        self.hist.append(round(self.cpu, 1))
        if len(self.hist) > 44:
            self.hist.pop(0)

        self._probe_latency(now)

    def _probe_latency(self, now):
        if now - self._lat_probe_t < 2.5:
            return
        self._lat_probe_t = now

        def probe():
            t0 = time.time()
            try:
                s = socket.create_connection(("1.1.1.1", 443), timeout=1.5)
                s.close()
                self.latency = round((time.time() - t0) * 1000, 1)
            except OSError:
                self.latency = None
        threading.Thread(target=probe, daemon=True).start()

    def snapshot(self):
        self.update()
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.strip().split()[0])
        total, avail = mem["MemTotal"], mem["MemAvailable"]
        used = total - avail
        swap_t, swap_f = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)

        load1, load5, load15 = (round(float(x), 2)
                                for x in open("/proc/loadavg").read().split()[:3])

        temp = None
        tdir = "/sys/class/thermal"
        if os.path.isdir(tdir):
            for z in sorted(os.listdir(tdir)):
                try:
                    with open(f"{tdir}/{z}/temp") as f:
                        t = int(f.read()) / 1000
                    if t > 0:
                        temp = round(t, 1)
                        break
                except (OSError, ValueError):
                    continue

        try:
            entropy = int(open("/proc/sys/kernel/random/entropy_avail").read())
        except (OSError, ValueError):
            entropy = None
        uptime = float(open("/proc/uptime").read().split()[0])
        procs = sum(1 for n in os.listdir("/proc") if n.isdigit())
        st = os.statvfs("/")
        disk_pct = round(100 * (1 - st.f_bavail / st.f_blocks), 1)

        conns = 0
        for f in ("/proc/net/tcp", "/proc/net/tcp6", "/proc/net/udp", "/proc/net/udp6"):
            try:
                conns += max(0, sum(1 for _ in open(f)) - 1)
            except OSError:
                pass

        cpu_model = ""
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break

        boot = time.time() - uptime
        return dict(
            cpu=round(self.cpu, 1), cores=os.cpu_count() or 1, cpu_model=cpu_model,
            mem_used=used * 1024, mem_total=total * 1024,
            mem_pct=round(100 * used / total, 1),
            swap_pct=round(100 * (swap_t - swap_f) / swap_t, 1) if swap_t else 0.0,
            load=[load1, load5, load15], temp=temp, entropy=entropy,
            uptime=round(uptime), boot_ts=round(boot), proc_count=procs,
            disk_pct=disk_pct, conns=conns, net={k: round(v, 1) for k, v in self.net_rates.items()},
            latency=self.latency, hist=list(self.hist), ts=time.time(),
        )


TEL = Telemetry()


def top_processes(n=8):
    """Top processes by cumulative CPU time from /proc/<pid>/stat."""
    hz = os.sysconf("SC_CLK_TCK")
    procs = []
    total = os.cpu_count() or 1
    uptime = float(open("/proc/uptime").read().split()[0])
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                parts = f.read().split()
            comm = parts[1].decode(errors="replace").strip("()")
            utime, stime = int(parts[13]), int(parts[14])
            threads = int(parts[19])
            rss_pages = int(parts[23])
            cpu_pct = 100 * (utime + stime) / hz / uptime
            procs.append(dict(pid=int(pid), name=comm[:18], cpu=round(cpu_pct, 1),
                              threads=threads, rss_mb=round(rss_pages * 4096 / 1048576, 1)))
        except (OSError, IndexError, ValueError):
            continue
    procs.sort(key=lambda p: -p["cpu"])
    return procs[:n]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(ROOT, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(404, b"not found", "text/plain")
        elif self.path in ("/models/helmet.gltf", "/models/helmet.bin",
                           "/models/ultron.gltf", "/models/ultron.bin",
                           "/models/ultron_head.gltf", "/models/ultron_head.bin"):
            try:
                ctype = "model/gltf+json" if self.path.endswith(".gltf") else "application/octet-stream"
                with open(os.path.join(ROOT, self.path.lstrip("/")), "rb") as f:
                    self._send(200, f.read(), ctype)
            except OSError:
                self._send(404, b"not found", "text/plain")
        elif self.path == "/api/telemetry":
            try:
                self._send(200, json.dumps(TEL.snapshot()).encode())
            except Exception as e:
                self._send(500, json.dumps(dict(error=str(e))).encode())
        elif self.path == "/api/processes":
            try:
                self._send(200, json.dumps(dict(procs=top_processes())).encode())
            except Exception as e:
                self._send(500, json.dumps(dict(error=str(e))).encode())
        elif self.path == "/api/health":
            self._send(200, b'{"ok":true}')
        else:
            self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", 9090), Handler)
    print("sentinel backend on :9090")
    srv.serve_forever()
