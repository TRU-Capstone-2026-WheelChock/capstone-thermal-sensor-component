from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from capstone_thermal_sensor.thermal_camera_pub import ThermalPublisher
from capstone_thermal_sensor.config import get_shared_dir

SHARED_DIR = Path(get_shared_dir())
LATEST_JPG = SHARED_DIR / "latest.jpg"
LATEST_JSON = SHARED_DIR / "latest.json"


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO_ROOT / "templates" / "index.html"

app = FastAPI(title="Thermal Visualizer")

def _default_status() -> dict[str, object]:
    return {
        "ts": None,
        "is_there_human": False,
        "frame_count": 0,
        "drop_count": 0,
        "source": "no-data",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _read_status() -> dict[str, object]:
    if not LATEST_JSON.exists():
        return _default_status()
    try:
        return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except Exception:
        return _default_status()


def _iter_mjpeg() -> Generator[bytes, None, None]:
    last_frame: bytes | None = None
    last_mtime_ns = -1

    while True:
        try:
            if LATEST_JPG.exists():
                st = LATEST_JPG.stat()
                if st.st_mtime_ns != last_mtime_ns:
                    last_mtime_ns = st.st_mtime_ns
                    last_frame = LATEST_JPG.read_bytes()
        except FileNotFoundError:
            pass
        except Exception:
            # Keep stream alive even if one read fails.
            pass

        if last_frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + last_frame
                + b"\r\n"
            )
        time.sleep(0.08)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return HTMLResponse("<h1>index.html not found</h1>", status_code=500)


@app.get("/status")
def status() -> JSONResponse:
    return JSONResponse(_read_status())


@app.get("/video_feed")
def video_feed() -> StreamingResponse:
    return StreamingResponse(
        _iter_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "shared_dir": str(SHARED_DIR)})
