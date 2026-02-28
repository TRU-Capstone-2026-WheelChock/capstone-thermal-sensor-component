"""Thermal frame file writer for FastAPI visualization.

This module provides a minimal writer that converts thermal frame arrays into
JPEG and stores the latest frame/status as files for the visualizer process.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from capstone_thermal_sensor.config import get_shared_dir


@dataclass
class WriterConfig:
    """Configuration for frame-to-file output.

    Attributes:
        shared_dir: Directory where latest frame/status files are written.
        jpeg_quality: JPEG compression quality used by OpenCV.
        width: Output frame width in pixels.
        height: Output frame height in pixels.
    """

    shared_dir: Path = field(default_factory=lambda: Path(get_shared_dir()))
    jpeg_quality: int = int(os.getenv("VIS_JPEG_QUALITY", "70"))
    width: int = int(os.getenv("VIS_FRAME_WIDTH", "640"))
    height: int = int(os.getenv("VIS_FRAME_HEIGHT", "480"))


class FrameFileWriter:
    """Write thermal frames to latest JPEG/JSON files.

    The writer keeps only the latest frame and latest metadata:
    - ``latest.jpg`` for MJPEG visualization
    - ``latest.json`` for status polling
    """

    def __init__(self, config: WriterConfig, logger: logging.Logger | None = None) -> None:
        """Initialize the frame writer.

        Args:
            config: Writer settings for output path and image format.
            logger: Optional logger instance. If omitted, a module logger is used.
        """

        self.config = config
        self.logger = logger or logging.getLogger("FrameFileWriter")

        self.shared_dir = config.shared_dir
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self.latest_jpg = self.shared_dir / "latest.jpg"
        self.latest_json = self.shared_dir / "latest.json"
        self.tmp_jpg = self.shared_dir / ".latest.jpg.tmp"
        self.tmp_json = self.shared_dir / ".latest.json.tmp"

    def write(self, frame: np.ndarray, ts: datetime, is_there_human: bool) -> None:
        """Convert a thermal frame and update latest files.

        Args:
            frame: Thermal frame array. Shape can be ``(24, 32)`` or flat ``768``.
            ts: Frame timestamp.
            is_there_human: Detection result for status output.
        """

        jpg = self._frame_to_jpeg(frame)
        if jpg is None:
            return

        self._atomic_write(self.tmp_jpg, self.latest_jpg, jpg)

        status = {
            "ts": ts.isoformat(),
            "is_there_human": is_there_human,
            "source": "frame_writer",
        }
        self._atomic_write(
            self.tmp_json,
            self.latest_json,
            json.dumps(status, ensure_ascii=True).encode("utf-8"),
        )

    def _frame_to_jpeg(self, frame: np.ndarray) -> bytes | None:
        """Convert thermal frame to JPEG bytes.

        Args:
            frame: Thermal frame array to convert.

        Returns:
            JPEG bytes when conversion succeeds, otherwise ``None``.
        """

        arr = self._to_thermal_array(frame)
        if arr is None:
            return None

        norm = self._normalize_thermal(arr)
        heatmap = self._to_display_image(norm)
        ok, encoded = cv2.imencode(
            ".jpg",
            heatmap,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.config.jpeg_quality],
        )
        if not ok:
            return None
        return encoded.tobytes()

    def _to_thermal_array(self, frame: np.ndarray) -> np.ndarray | None:
        """Convert raw input into a 2D thermal array.

        Args:
            frame: Input thermal array.

        Returns:
            A ``(24, 32)`` style 2D array if accepted, otherwise ``None``.
        """

        arr = np.asarray(frame, dtype=np.float32)
        if arr.ndim == 1 and arr.size == 24 * 32:
            return arr.reshape((24, 32))
        if arr.ndim == 2:
            return arr
        self.logger.warning("unexpected frame shape: %s", arr.shape)
        return None

    @staticmethod
    def _normalize_thermal(arr: np.ndarray) -> np.ndarray:
        """Normalize thermal values to 8-bit grayscale.

        Args:
            arr: 2D thermal array.

        Returns:
            8-bit normalized array in the range ``0..255``.
        """

        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        if max_val - min_val < 1e-6:
            return np.zeros_like(arr, dtype=np.uint8)
        return ((arr - min_val) / (max_val - min_val) * 255.0).astype(np.uint8)

    def _to_display_image(self, norm: np.ndarray) -> np.ndarray:
        """Convert normalized frame to colorized display image.

        Args:
            norm: Normalized 8-bit frame.

        Returns:
            Resized BGR image suitable for JPEG encoding.
        """

        heatmap = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
        return cv2.resize(
            heatmap,
            (self.config.width, self.config.height),
            interpolation=cv2.INTER_NEAREST,
        )

    @staticmethod
    def _atomic_write(tmp_path: Path, dst_path: Path, data: bytes) -> None:
        """Write file atomically using tmp + replace.

        Args:
            tmp_path: Temporary file path used for staged write.
            dst_path: Final destination path to replace.
            data: Byte content to persist.
        """

        tmp_path.write_bytes(data)
        tmp_path.replace(dst_path)


# Backward-compatible alias for previous naming.
ReceiverConfig = WriterConfig
