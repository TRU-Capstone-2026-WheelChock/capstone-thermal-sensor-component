from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play PNG frames by repeatedly writing latest.jpg/latest.json."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=BASE_DIR / "frames",
        help="Directory that contains input PNG files.",
    )
    parser.add_argument(
        "--shared-dir",
        type=Path,
        default=Path("/dev/shm/thermal"),
        help="Directory used by visualizer (contains latest.jpg/latest.json).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=12.5,
        help="Playback FPS.",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=80,
        help="JPEG quality (1-100).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop sequence indefinitely.",
    )
    parser.add_argument(
        "--is-there-human",
        action="store_true",
        help="Set is_there_human=true in latest.json.",
    )
    return parser.parse_args()


def find_frames(input_dir: Path) -> list[Path]:
    frames = sorted(input_dir.glob("*.png"))
    if not frames:
        raise FileNotFoundError(f"No PNG files found in {input_dir}")
    return frames


def write_status(status_path: Path, is_there_human: bool, frame_count: int) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "is_there_human": is_there_human,
        "frame_count": frame_count,
        "source": "visualizer-test-player",
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.fps <= 0:
        raise ValueError("--fps must be greater than 0")
    if args.jpeg_quality < 1 or args.jpeg_quality > 100:
        raise ValueError("--jpeg-quality must be in range 1..100")

    frames = find_frames(args.input_dir)
    args.shared_dir.mkdir(parents=True, exist_ok=True)

    latest_jpg = args.shared_dir / "latest.jpg"
    latest_json = args.shared_dir / "latest.json"
    frame_count = 0
    delay_sec = 1.0 / args.fps

    while True:
        for frame_path in frames:
            image = cv2.imread(str(frame_path))
            if image is None:
                raise RuntimeError(f"Failed to load image: {frame_path}")

            ok, encoded = cv2.imencode(
                ".jpg",
                image,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(args.jpeg_quality)],
            )
            if not ok:
                raise RuntimeError(f"Failed to encode image as JPEG: {frame_path}")

            latest_jpg.write_bytes(encoded.tobytes())
            frame_count += 1
            write_status(latest_json, args.is_there_human, frame_count)
            print(f"[frame {frame_count}] wrote {frame_path.name}", flush=True)
            time.sleep(delay_sec)

        if not args.loop:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
