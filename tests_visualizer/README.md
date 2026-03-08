# Visualizer test assets

Place your PNG sequence files in this directory:

- `/app/tests_visualizer/frames/*.png`

Generate sample sequence:

```bash
poetry run python tests_visualizer/generate_sequence.py
```

Run visualizer test setup:

```bash
docker compose -f docker-compose.visualizer-test.yml up --build
```

Then open:

- `http://localhost:8000/`
- `http://localhost:8000/video_feed`
- `http://localhost:8000/status`

Default playback is loop mode at 12.5 FPS.
