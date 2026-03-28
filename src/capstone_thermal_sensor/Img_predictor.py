from __future__ import annotations

from pathlib import Path
from typing import Any
import logging
import os

import adafruit_mlx90640
import board
import busio
import cv2
import numpy as np
import numpy.typing as npt
from tensorflow import keras

logger = logging.getLogger("Img_predictor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

ThermalFrame = npt.NDArray[np.float32]
ProcessedFrame = npt.NDArray[np.float32]


class Img_predictor:
    def __init__(self) -> None:
        keras.backend.clear_session()
        current_dir = Path(__file__).parent
        self.model: Any = keras.models.load_model(current_dir / "best_thermal_human_V1.keras")
        # self.processer = pi.load(open('Th_image_processer_V1.pkl', 'rb'))
        # self.img_path = os.path.join('dataset', 'test_img.csv')
        self.img_height: int = 24
        self.img_width: int = 32
        self.temp_min: float = -40.0
        self.temp_max: float = 40.0
        self.X_processed: ProcessedFrame | None = None
        self.simulation_mode: bool = False
        self.mlx: Any | None = None
        self.df: list[float] = [0.0] * (self.img_height * self.img_width)
        self.raw_data: ThermalFrame | None = None

        logger.info("Initializing Thermal Camera...")
        # try:
        #     # I2C Setup (800kHz for high speed)
        #     i2c = busio.I2C(board.SCL, board.SDA, frequency=200000)
        #     self.mlx = adafruit_mlx90640.MLX90640(i2c)
        #     self.mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
        #     self.df = [0] * 768
        #     self.raw_data = None
        #     logger.info("Thermal Camera initialized successfully.")

        # except Exception as e:
        #     logger.critical(f"Thermal Camera initialized FAILED: {e}")
        #     raise e

        logger.info("Running env: %s", "Docker" if os.path.exists("/.dockerenv") else "Real Machine")
        i2c_devices = ["/dev/i2c-1", "/dev/i2c-20", "/dev/i2c-21"]
        available_device: str | None = None

        for device in i2c_devices:
            if os.path.exists(device):
                available_device = device
                logger.info("Found I2C Device: %s", device)
                break

        if not available_device:
            self.simulation_mode = True
            return
        try:
            if os.path.exists("/.dockerenv"):
                i2c_frequency = 200000
                i2c_refresh = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
            else:
                i2c_frequency = 200000
                i2c_refresh = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ

            i2c = busio.I2C(board.SCL, board.SDA, frequency=i2c_frequency)
            self.mlx = adafruit_mlx90640.MLX90640(i2c)
            self.mlx.refresh_rate = i2c_refresh
            logger.info("Thermal Camera initialized successfully.")

        except Exception as e:
            logger.critical("Thermal Camera initialized FAILED: %s", e)
            raise

    def camera(self) -> tuple[bytes | None, ThermalFrame | None]:
        if self.simulation_mode or self.mlx is None:
            logger.warning("Thermal camera is not available.")
            return None, None

        try:
            # Getting frame data
            self.mlx.getFrame(self.df)
            self.raw_data = np.asarray(self.df, dtype=np.float32)
            # Reshape to 24X32 grid
            data_array = self.raw_data.reshape((self.img_height, self.img_width))

            if np.isnan(data_array).any() or np.isinf(data_array).any():
                logger.warning("Invalid temperature data dectected (NaN or Inf)")
                return None, None

            X = self.raw_data.reshape(-1, self.img_height, self.img_width)
            X_normalized = (X - self.temp_min) / (self.temp_max - self.temp_min)
            X_normalized = np.clip(X_normalized, 0, 1)
            self.X_processed = X_normalized[..., np.newaxis]
            logger.debug("X_processed shape: %s", self.X_processed.shape)
            logger.debug(
                "Normalized range: [%.3f, %.3f]",
                float(np.min(self.X_processed)),
                float(np.max(self.X_processed)),
            )
            # Normalize for visualization
            min_val, max_val = np.min(data_array), np.max(data_array)
            if max_val - min_val < 1e-6:
                norm_data = np.zeros_like(data_array, dtype=np.uint8)
            else:
                norm_data = ((data_array - min_val) / (max_val - min_val) * 255.0).astype(
                    np.uint8
                )
            heatmap = cv2.applyColorMap(norm_data, cv2.COLORMAP_JET)
            heatmap = cv2.resize(heatmap, (640, 480), interpolation=cv2.INTER_NEAREST)

            ret, jpeg = cv2.imencode(".jpg", heatmap)
            if not ret:
                logger.warning("JPEG encode failed.")
                return None, self.raw_data.copy()

            return jpeg.tobytes(), self.raw_data.copy()

        except RuntimeError as e:
            logger.warning("Sensor read error (RuntimeError): %s", e)
            return None, None
        except Exception as e:
            logger.error("Unexpected error in get_frame: %s", e)
            return None, None

    # def predict_from_csv(self):
    #     try:
    #         X, y = self.processer.load_process_data(self.img_path)
    #         if X is None or len(X) == 0:
    #             logger.warning("No data loaded from CSV.")
    #             return np.array([])
    #         X_pred = self.model.predict(X, verbose=0)
    #         y_pred = (X_pred > 0.5).astype(int)
    #         return y_pred
    #     except FileNotFoundError:
    #         logger.error(f"CSV file not found: {self.img_path}")
    #         raise
    #     except Exception as e:
    #         logger.error(f"Error during prediction from CSV: {e}")
    #         raise

    def predict_from_camera(self) -> bool:
        if self.X_processed is None:
            logger.warning("X_processed is not ready for prediction.")
            return False

        X_pred = self.model.predict(self.X_processed)
        y_pred = (X_pred > 0.5).astype(int)
        logger.info(y_pred)
        if bool(np.any(y_pred == 1)):
            logger.info("Human")
            return True

        logger.info("Non-Human")
        return False
