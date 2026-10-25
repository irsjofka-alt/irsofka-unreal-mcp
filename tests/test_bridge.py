"""Bukti bahwa fallback dua-keadaan benar-benar ada, bukan hanya tertulis di README.

Menjalankan: python3 tests/test_bridge.py  — tanpa pytest, tanpa Unreal Engine, tanpa jaringan.
Semua tes memakai pendengar TCP tiruan di port bebas; keadaan "tidak terdeteksi" diukur pada port
yang memang tidak ada pemanggilnya, jadi yang teruji adalah jalur kodenya, bukan mesin orang lain.
"""

import json
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((bool(cond), name, detail))
    print(f"[{'ok    ' if cond else 'GAGAL '}] {name}" + ("" if cond else f"  <- {detail}"))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeEngine:
    """Satu baris JSON masuk, satu baris JSON keluar — framing yang sama dengan plugin."""

    def __init__(self, responder):
        self.port = free_port()
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(4)
        self.responder = responder
        self.seen = []
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                if not buf:
                    continue
                self.seen.append(json.loads(buf.decode("utf-8").strip()))
                conn.sendall((json.dumps(self.responder(self.seen[-1])) + "\n").encode("utf-8"))

    def close(self):
        self.sock.close()


def main():
    host = "127.0.0.1"

    # 1 — round-trip lewat framing nyata
    eng = FakeEngine(lambda req: {"status": "SUCCESS", "echo": req})
    try:
        bridge.HOST, bridge.DEFAULT_PORT = host, eng.port
        r = bridge.send_to_engine("world", "get_transform", {"actor_label": "Actor_1"})
        check("satu perintah pulang-pergi lewat bingkai baris-JSON: domain/action/params mendarat utuh",
              r.get("status") == "SUCCESS" and r["echo"]["domain"] == "world"
              and r["echo"]["action"] == "get_transform"
              and r["echo"]["params"] == {"actor_label": "Actor_1"}, str(r)[:160])
        st = bridge.station_status(host, eng.port)
        check("penerima menjawab tapi tidak kenal core.presence -> standalone_listener, "
              "BUKAN station_bridge (yang memutuskan keadaan adalah plugin)",
              st["detected"] is True and st["mode"] == "standalone_listener"
              and f":{eng.port}" in st["endpoint"], str(st)[:200])

        # 1b — plugin yang sudah memuat presence: keadaannya DIBACA dari jawabannya, bukan ditebak
        presence_payload = {"status": "SUCCESS", "station": {
            "detected": True, "root": "$HOME/.ai-station",
            "evidence": "konvensi <home>/.ai-station + tools/work_order.py",
            "why": "stasiun terdeteksi", "reported_by": "IRSofkaStationCore plugin", "bridge_port": 9877}}
        engP = FakeEngine(lambda req: presence_payload if (req.get("domain"), req.get("action")) == ("core", "presence")
                          else {"status": "FAILED", "error": "Unknown core action: " + str(req.get("action"))})
        stP = bridge.station_status(host, engP.port)
        check("plugin menjawab core.presence -> mode station_bridge dan root stasiun ikut dilaporkan",
              stP["mode"] == "station_bridge" and stP["plugin_says_detected"] is True
              and stP["station_root"].endswith(".ai-station")
              and stP["reported_by"] == "IRSofkaStationCore plugin", str(stP)[:200])
        check("presence yang menjawab TIDAK dianggap perintah domain lain: probe menanyakan core.presence",
              engP.seen and engP.seen[0].get("domain") == "core" and engP.seen[0].get("action") == "presence",
              str(engP.seen[:1])[:160])
        engP.close()

        # 1c — plugin lama yang menolak aksi dengan FAILED: tetap penerima hidup, bukan "tidak ada"
        engR = FakeEngine(lambda req: {"status": "FAILED", "error": "Unknown core action: presence"})
        stR = bridge.station_status(host, engR.port)
        check("plugin lama yang menjawab 'Unknown core action' tetap detected True "
              "(penerima hidup) dengan mode standalone_listener",
              stR["detected"] is True and stR["mode"] == "standalone_listener", str(stR)[:200])
        engR.close()

        # 2 — pipeline: langkah yang sudah berhasil tidak hilang saat langkah berikutnya gagal
        replies = [{"status": "SUCCESS", "n": 0}, {"status": "SUCCESS", "n": 1},
                   {"status": "ERROR", "error": "boom"}, {"status": "SUCCESS", "n": 3}]
        step_no = [0]

        def responder(_req):
            out = replies[min(step_no[0], len(replies) - 1)]
            step_no[0] += 1
            return out

        eng2 = FakeEngine(responder)
        bridge.DEFAULT_PORT = eng2.port
        out = bridge.execute_atomic_pipeline([{"domain": "world", "action": f"a{i}"} for i in range(4)])
        check("pipeline atomik: dua langkah pertama dilaporkan, langkah ketiga menghentikan, "
              "statusnya PARTIAL_SUCCESS (bukan FAILED yang membuang bukti)",
              out["status"] == "PARTIAL_SUCCESS" and len(out["completed_steps"]) == 2
              and out["failed_step_index"] == 2, str(out)[:200])
        eng2.close()

        eng3 = FakeEngine(lambda req: {"status": "ERROR", "error": "langsung gagal"})
        bridge.DEFAULT_PORT = eng3.port
        out0 = bridge.execute_atomic_pipeline([{"domain": "world", "action": "a0"}])
        check("kalau langkah PERTAMA sudah gagal, statusnya FAILED — PARTIAL_SUCCESS hanya kalau "
              "ada yang benar-benar selesai",
              out0["status"] == "FAILED" and out0["completed_steps"] == [], str(out0)[:160])
        eng3.close()
    finally:
        eng.close()
        bridge.HOST, bridge.DEFAULT_PORT = host, 9877

    # 3 — keadaan kedua: TIDAK ada plugin. Ini yang harus jujur, bukan mirip berhasil.
    dead = free_port()
    st = bridge.station_status(host, dead)
    check("plugin tidak terdeteksi -> detected False, dan alasannya menyebut jenis kesalahannya",
          st["detected"] is False and "plugin tidak terdeteksi" in st["why"], str(st)[:180])
    bridge.DEFAULT_PORT = dead
    r2 = bridge.send_to_engine("world", "spawn", {"actor_class": "StaticMeshActor"})
    check("tanpa plugin, alat menjawab UNAVAILABLE dengan sebab — BUKAN success palsu, BUKAN "
          "traceback", r2.get("status") == "UNAVAILABLE" and "IRSofkaStationCore" in r2.get("error", ""),
          str(r2)[:180])
    out3 = bridge.execute_atomic_pipeline([{"domain": "world", "action": "a0"}])
    check("pipeline di atas plugin yang tidak ada pun dilaporkan sebagai FAILED, bukan SUCCESS kosong",
          out3["status"] == "FAILED", str(out3)[:140])
    bridge.DEFAULT_PORT = 9877

    total = len(results)
    bad = [n for ok, n, _d in results if not ok]
    print(f"\ntest_bridge: {total - len(bad)}/{total} sesuai")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
