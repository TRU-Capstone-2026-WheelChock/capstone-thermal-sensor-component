from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate numbered PNG frames for visualizer tests."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BASE_DIR / "frames",
        help="Output directory for generated PNG frames.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of frames to generate.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=320,
        help="Frame width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=240,
        help="Frame height.",
    )
    return parser.parse_args()


def make_frame(idx: int, count: int, width: int, height: int) -> np.ndarray:
    x = np.linspace(0, 255, width, dtype=np.uint8)
    gradient = np.tile(x, (height, 1))
    base = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)

    t = idx / max(count - 1, 1)
    cx = int(20 + t * (width - 40))
    cy = int(height / 2 + np.sin(t * np.pi * 2) * (height * 0.2))
    frame = base.copy()
    cv2.circle(frame, (cx, cy), max(12, width // 20), (255, 255, 255), -1)

    cv2.putText(
        frame,
        f"frame {idx + 1:03d}",
        (10, height - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"frame {idx + 1:03d}",
        (10, height - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return frame


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise ValueError("--count must be greater than 0")
    if args.width <= 0 or args.height <= 0:
        raise ValueError("--width/--height must be greater than 0")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(args.count):
        frame = make_frame(idx, args.count, args.width, args.height)
        out = args.output_dir / f"frame_{idx + 1:04d}.png"
        ok = cv2.imwrite(str(out), frame)
        if not ok:
            raise RuntimeError(f"Failed to write frame: {out}")

    print(f"Generated {args.count} frames in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
