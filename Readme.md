# capstone-thermal-sensor-component

## Quick start

### Normal runtime (publisher + visualizer)

```bash
docker compose up --build publisher visualizer
```

Open:

- `http://localhost:8000/`
- `http://localhost:8000/video_feed`
- `http://localhost:8000/status`

### Visualizer-only test (without thermal publisher)

1. Generate 50 test PNG frames:

```bash
poetry run python tests_visualizer/generate_sequence.py
```

2. Start visualizer test stack:

```bash
docker compose -f docker-compose.visualizer-test.yml up --build
```

Open:

- `http://localhost:8001/`
- `http://localhost:8001/video_feed`
- `http://localhost:8001/status`

## Why `tmpfs` for thermal frames

This project continuously writes `latest.jpg` and `latest.json` for the FastAPI visualizer.
If these files are written to normal container storage, the writes hit host disk I/O.
On Raspberry Pi, that can increase SD card wear and reduce performance.

Using `tmpfs` keeps these files in RAM:

- lower write latency
- less disk wear
- simpler "latest frame only" workflow

The files are ephemeral (deleted when the container restarts), which is fine for live streaming state.

## Docker Compose setup

`docker-compose.yml` is configured with:

- `Dockerfile.dev` for devcontainer service (`app`)
- `Dockerfile` for runtime services (`publisher` and `visualizer`)
- Compose project name `capstone-thermal-dev`
- `THERMAL_SHARED_DIR=/dev/shm/thermal` on both `publisher` and `visualizer`
- a shared named volume `thermal-shared` mounted at `/dev/shm/thermal`
- `thermal-shared` backed by `tmpfs` (`size=64m`)

This means publisher and FastAPI share the same in-memory path for
`latest.jpg` and `latest.json`.

`publisher` runs `python -m capstone_thermal_sensor.main`, so `main.py` is
executed by Compose.

## Which services to start

For normal runtime, start only:

- `publisher`
- `visualizer`

Example:

```bash
docker compose up --build publisher visualizer
```

`app` is a devcontainer/workspace service and uses `sleep infinity`, so it is
not required for normal runtime.

## Config override

You can switch config files at runtime with environment variables:

- `THERMAL_CONFIG_PATH` (recommended)
- `CONFIG_YML_PATH` (alias)

Example:

```bash
THERMAL_CONFIG_PATH=/app/config/prod.yml docker compose up
```

## Visualizer-only test with PNG sequence

If you want to test FastAPI visualizer behavior without starting thermal publisher:

1. Put test frames in `/app/tests_visualizer/frames/*.png` (or pass custom `--input-dir`)
2. Start dedicated test stack:

```bash
docker compose -f docker-compose.visualizer-test.yml up --build
```

This stack runs:

- `visualizer_test` (`/`, `/video_feed`, `/status`)
- `frame_player` (replays PNG sequence to `latest.jpg/latest.json`)

Test stack details:

- Compose project name `capstone-thermal-visualizer-test`
- Exposed host port `8001` mapped to container port `8000`
- Separate named volumes from the normal runtime stack, so it can run alongside `docker-compose.yml`

## Project file guide

Core runtime:

- `src/capstone_thermal_sensor/main.py`
  - Runtime entrypoint for publisher service.
- `src/capstone_thermal_sensor/thermal_camera_pub.py`
  - Thermal sensor publisher logic.
- `src/capstone_thermal_sensor/frame_writer.py`
  - Writes `latest.jpg` and `latest.json` into shared directory.
- `src/capstone_thermal_sensor/visualize.py`
  - FastAPI app (`/`, `/video_feed`, `/status`, `/health`).
- `templates/index.html`
  - Visualizer UI page.

Container and environment:

- `docker-compose.yml`
  - Normal runtime services (`publisher`, `visualizer`) and shared tmpfs volume.
- `docker-compose.visualizer-test.yml`
  - Visualizer test stack (`visualizer_test`, `frame_player`).
- `Dockerfile`
  - Runtime image.
- `Dockerfile.dev`
  - Dev image with Poetry virtualenv for local development/testing.

Visualizer test utilities:

- `tests_visualizer/generate_sequence.py`
  - Generates numbered PNG frames (default 50) into `tests_visualizer/frames`.
- `tests_visualizer/play_png_sequence.py`
  - Replays PNG sequence by writing `latest.jpg/latest.json` repeatedly.
- `tests_visualizer/frames/`
  - Default input directory for `play_png_sequence.py`.

Notes:

- Normal runtime exposed port is `8000`.
- Visualizer test exposed port is `8001`.
- `latest.jpg` and `latest.json` are ephemeral because shared volume uses tmpfs.
