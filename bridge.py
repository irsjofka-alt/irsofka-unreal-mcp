"""Transport sisi stasiun ke penerima di dalam engine: satu baris JSON per koneksi TCP 127.0.0.1:9877.

Framing diambil dari implementasi yang sudah berjalan (plugin `IRSofkaStationCore`,
`Content/Python/pipeline_executor.py`, dan `FIRSofkaSocketServer::ProcessJsonCommand`), bukan
ditulis ulang dari ingatan: `set_transform` dan `get_transform` harus memakai bingkai yang sama
dengan yang dibaca plugin, kalau tidak yang diuji adalah karangan.

Aturan yang diikat pemilik proyek 2026-10-15 15:02 dan diulang 2026-10-16:
plugin adalah PENERIMA utama. Ketika plugin mendeteksi ai-station ia menjadi perpanjangan stasiun;
ketika tidak, ia bekerja sebagai plugin biasa. Yang memutuskan keadaannya adalah PLUGIN — sisi
stasiun di bawah ini tidak lagi menyimpulkan "terdeteksi" dari socket yang menjawab, tapi
menanyakannya lewat `core.presence`, dan melaporkan tiga keadaan yang berbeda.
"""

import json
import socket
from typing import Any, Dict, List, Optional

DEFAULT_PORT = 9877
HOST = "127.0.0.1"


def _request(domain: str, action: str, params: Optional[Dict[str, Any]] = None,
             host: Optional[str] = None, port: Optional[int] = None,
             timeout: float = 120.0) -> Dict[str, Any]:
    """Satu koneksi, satu baris JSON masuk, satu baris JSON keluar.

    Alamat dibaca dari modul pada waktu panggil (bukan dari default argumen) supaya tes boleh
    memindahkan `bridge.HOST` / `bridge.DEFAULT_PORT` ke pendengar tiruan tanpa menyentuh produksi.
    """
    target_host = HOST if host is None else host
    target_port = DEFAULT_PORT if port is None else port
    payload = {"domain": domain, "action": action, "params": params or {}}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((target_host, target_port))
            s.sendall((json.dumps(payload) + "\n").encode("utf-8"))

            buffer = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                if buffer.endswith(b"\n"):
                    try:
                        parsed = json.loads(buffer.decode("utf-8").strip())
                        return parsed
                    except Exception:
                        continue

            return json.loads(buffer.decode("utf-8").strip())
    except ConnectionRefusedError:
        return {"status": "UNAVAILABLE",
                "error": f"Cannot connect to Unreal Engine on {target_host}:{target_port}. "
                         "Ensure IRSofkaStationCore is loaded."}
    except TimeoutError:
        return {"status": "UNAVAILABLE",
                "error": f"No reply from {target_host}:{target_port} within {timeout}s — "
                         "listener ada tapi tidak menjawab (GameThread macet atau timeout terlalu pendek)"}
    except OSError as exc:
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
    except json.JSONDecodeError as exc:
        # Balasan yang bukan JSON adalah cacat protokol, dan menyembunyikannya sebagai sukses
        # kosong adalah cara paling mudah membuat kegagalan tidak pernah terlihat.
        return {"status": "ERROR", "error": f"reply is not JSON: {exc}"}
    except Exception as exc:  # noqa: BLE001 — bentuk jawaban tetap harus JSON, bukan traceback
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def station_status(host: Optional[str] = None, port: Optional[int] = None,
                   timeout: float = 2.0) -> Dict[str, Any]:
    """Keadaan jembatan, ditanyakan ke plugin — bukan disimpulkan dari socket yang menjawab.

    Tiga keadaan, tiga kata, karena ketiganya menuntut tindakan berbeda dari pembaca:

      * `station_bridge`     — plugin hidup DAN tahu ia terpasang ke ai-station.
      * `standalone_listener`— plugin hidup tapi tidak kenal `core.presence` (binaannya lebih tua
                               dari fitur ini): jembatan bisa dipakai, tetapi keputusannya bukan
                               dari plugin. Ini keadaan yang dulu disamarkan sebagai "terdeteksi".
      * `no_receiver`        — tidak ada yang menyahut: editor tertutup atau plugin tidak termuat.

    `detected` tetap ada (bool) karena pemanggil lama membacanya; maknanya sekarang "ada penerima
    yang menjawab", dan `mode` yang membedakan ketiga keadaan di atas.
    """
    target_host = HOST if host is None else host
    target_port = DEFAULT_PORT if port is None else port
    endpoint = f"{target_host}:{target_port}"

    reply = _request("core", "presence", {}, host=target_host, port=target_port, timeout=timeout)
    answered = reply.get("status") in ("SUCCESS", "FAILED")

    if not answered:
        return {"detected": False, "mode": "no_receiver", "endpoint": endpoint,
                "reported_by": "probe sisi stasiun (tidak ada yang menyahut)",
                "why": f"plugin tidak terdeteksi ({str(reply.get('error', ''))[:90]}) — "
                       "engine bekerja normal tanpa jembatan; alat MCP menjawab UNAVAILABLE"}

    station = reply.get("station")
    if isinstance(station, dict) and station:
        return {"detected": True, "mode": "station_bridge", "endpoint": endpoint,
                "reported_by": station.get("reported_by", "plugin"),
                "plugin_says_detected": bool(station.get("detected")),
                "station_root": station.get("root", ""),
                "evidence": station.get("evidence", ""),
                "why": station.get("why", "plugin melaporkan keadaannya sendiri")}

    # Plugin menjawab tapi tidak mengenal presence: jawaban itu datang dari handshake, bukan
    # dari plugin. Ditulis apa adanya, lengkap dengan apa yang perlu dilakukan.
    return {"detected": True, "mode": "standalone_listener", "endpoint": endpoint,
            "reported_by": "handshake TCP sisi stasiun (plugin tidak menjawab core.presence)",
            "why": f"penerima hidup tetapi binanya lebih tua dari fitur presence "
                   f"({str(reply.get('error') or reply.get('message') or reply)[:80]}) — "
                   "rebuild IRSofkaStationCore dari repo agar plugin melaporkan keadaannya sendiri"}


def send_to_engine(domain: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Kirim satu perintah domain ke C++ Socket Server di dalam Unreal Engine 5.8."""
    return _request(domain, action, params)


def execute_atomic_pipeline(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Jalankan rangkaian langkah secara atomik dengan laporan Partial Success.

    Kalau satu langkah gagal, langkah yang sudah berhasil tetap dilaporkan — bukan transaksi
    buta yang dibuang seluruhnya.
    """
    executed_steps = []
    for idx, step in enumerate(steps):
        domain = step.get("domain", "")
        action = step.get("action", "")
        params = step.get("params", {})
        result = send_to_engine(domain, action, params)
        if result.get("status") == "SUCCESS":
            executed_steps.append({"step_index": idx, "domain": domain, "action": action,
                                   "result": result})
        else:
            return {"status": "PARTIAL_SUCCESS" if executed_steps else "FAILED",
                    "completed_steps": executed_steps,
                    "failed_step_index": idx,
                    "failed_step": {"domain": domain, "action": action},
                    "error": result.get("error", "Unknown step failure")}
    return {"status": "SUCCESS", "completed_steps": executed_steps}
