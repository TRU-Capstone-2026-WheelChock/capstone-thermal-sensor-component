from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


class ZmqConfig(BaseModel):
    picture_endpoint: str = "tcp://127.0.0.1:5558"
    center_endpoint: str = "tcp://127.0.0.1:5557"
    picture_topic: str = ""
    picture_sub_is_bind: bool = False


class VisualConfig(BaseModel):
    fps_limit: float = 12.0
    jpeg_quality: int = 70
    frame_width: int = 640
    frame_height: int = 480


class PathsConfig(BaseModel):
    thermal_shared_dir: str = "/tmp/thermal"


class ThermalPubConfig(BaseModel):
    device_id: str = "thermal-001"
    device_name: str = "thermal-camera"
    publish_interval_sec: float = 0.1
    presentation_mode: bool = True


class AppConfig(BaseModel):
    zmq: ZmqConfig = ZmqConfig()
    visual: VisualConfig = VisualConfig()
    paths: PathsConfig = PathsConfig()
    thermal_pub: ThermalPubConfig = ThermalPubConfig()


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yml")
CONFIG_PATH_ENVS = ("THERMAL_CONFIG_PATH", "CONFIG_YML_PATH")


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "":
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    low = value.lower()
    if low in {"true", "false"}:
        return low == "true"
    if low in {"null", "none"}:
        return None

    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """
    Parse a minimal YAML subset:
    - nested dicts by 2-space indentation
    - `key: value` and `key:` entries
    """
    root: dict[str, Any] = {}
    # stack items: (indent_level, current_dict)
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"Invalid indentation at line {lineno}: '{raw_line}'")

        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"Invalid YAML format at line {lineno}: '{raw_line}'")

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value_part = raw_value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"Invalid nesting at line {lineno}: '{raw_line}'")

        parent = stack[-1][1]
        if value_part == "":
            node: dict[str, Any] = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = _parse_scalar(value_part)

    return root


def _resolve_config_path(config_path: str | Path | None = None) -> Path:
    if config_path is not None:
        return Path(config_path)
    for env_name in CONFIG_PATH_ENVS:
        env_value = os.getenv(env_name)
        if env_value:
            return Path(env_value)
    return DEFAULT_CONFIG_PATH


@lru_cache(maxsize=1)
def load_config(config_path: str | Path | None = None) -> AppConfig:
    path = _resolve_config_path(config_path)
    if not path.exists():
        return AppConfig()

    try:
        parsed = _parse_simple_yaml(path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(parsed)
    except (OSError, ValueError, ValidationError) as exc:
        raise RuntimeError(f"Failed to load config file: {path} ({exc})") from exc


def reload_config(config_path: str | Path | None = None) -> AppConfig:
    load_config.cache_clear()
    return load_config(config_path=config_path)


def get_endpoint(name: str) -> str:
    cfg = load_config()
    if name == "picture":
        return os.getenv("PICTURE_ENDPOINT", cfg.zmq.picture_endpoint)
    if name == "center":
        return os.getenv("CENTER_ENDPOINT", cfg.zmq.center_endpoint)
    raise ValueError(f"Unknown endpoint name: {name}")


def get_picture_topic() -> str:
    cfg = load_config()
    return os.getenv("PICTURE_TOPIC", cfg.zmq.picture_topic)


def is_picture_sub_bind() -> bool:
    cfg = load_config()
    return os.getenv("PICTURE_SUB_IS_BIND", str(cfg.zmq.picture_sub_is_bind)).lower() == "true"


def get_shared_dir() -> str:
    cfg = load_config()
    return os.getenv("THERMAL_SHARED_DIR", cfg.paths.thermal_shared_dir)


def get_fps_limit() -> float:
    cfg = load_config()
    return float(os.getenv("VIS_FPS_LIMIT", str(cfg.visual.fps_limit)))


def get_device_id() -> str:
    cfg = load_config()
    return os.getenv("DEVICE_ID", cfg.thermal_pub.device_id)


def get_device_name() -> str:
    cfg = load_config()
    return os.getenv("DEVICE_NAME", cfg.thermal_pub.device_name)


def get_publish_interval_sec() -> float:
    cfg = load_config()
    return float(os.getenv("PUBLISH_INTERVAL_SEC", str(cfg.thermal_pub.publish_interval_sec)))


def is_presentation_mode() -> bool:
    cfg = load_config()
    return os.getenv("PRESENTATION_MODE", str(cfg.thermal_pub.presentation_mode)).lower() == "true"
