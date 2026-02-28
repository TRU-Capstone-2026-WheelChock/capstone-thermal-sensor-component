# capstone-thermal-sensor-component

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

- `THERMAL_SHARED_DIR=/dev/shm/thermal`
- `tmpfs: /dev/shm/thermal:size=64m`

This means receiver and FastAPI share the same in-memory path for `latest.jpg` and `latest.json`.

## Config override

You can switch config files at runtime with environment variables:

- `THERMAL_CONFIG_PATH` (recommended)
- `CONFIG_YML_PATH` (alias)

Example:

```bash
THERMAL_CONFIG_PATH=/app/config/prod.yml docker compose up
```
