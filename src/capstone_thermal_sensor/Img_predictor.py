import numpy as np
import pandas as pd
import pickle as pi
import streamlit as st
import matplotlib.pyplot as plt
import board
import busio
import cv2
import adafruit_mlx90640
import logging
import os
from tensorflow import keras

logger = logging.getLogger("Img_predictor")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Img_predictor:
    def __init__(self):
        keras.backend.clear_session()
        self.model = keras.models.load_model('best_thermal_human_V1.keras')
        # self.processer = pi.load(open('Th_image_processer_V1.pkl', 'rb'))
        # self.img_path = os.path.join('dataset', 'test_img.csv')
        self.img_height = 24
        self.img_width = 32
        self.temp_min = -40
        self.temp_max = 40
        self.X_processed = None

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

        logger.info(f"Running env: {'Docker' if os.path.exists('/.dockerenv') else 'Real Machine'}")
        i2c_devices = ['/dev/i2c-1', '/dev/i2c-20', '/dev/i2c-21']
        available_device = None
        
        for device in i2c_devices:
            if os.path.exists(device):
                available_device = device
                logger.info(f"Found I2C Device: {device}")
                break
        
        if not available_device:
            self.simulation_mode = True
            return
        try:
            if os.path.exists('/.dockerenv'):
                i2c_frequency = 200000
                i2c_refresh = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
            else:
                i2c_frequency = 200000
                i2c_refresh = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
                
            i2c = busio.I2C(board.SCL, board.SDA, frequency=i2c_frequency)
            self.mlx = adafruit_mlx90640.MLX90640(i2c)
            self.mlx.refresh_rate = i2c_refresh
            self.df = [0] * 768
            self.raw_data = None
            logger.info("Thermal Camera initialized successfully.")
       
        except Exception as e:
            logger.critical(f"Thermal Camera initialized FAILED: {e}")
            raise e
    
    def camera(self):
        try:
            # Getting frame data
            self.mlx.getFrame(self.df)
            self.raw_data = np.array(self.df)
            # Reshape to 24X32 grid
            data_array = self.raw_data.reshape((self.img_height,self.img_width))
            
            if np.isnan(data_array).any() or np.isinf(data_array).any():
                logger.warning("Invalid temperature data dectected (NaN or Inf)")
                return None, None
            
            X = self.raw_data.reshape(-1, self.img_height, self.img_width)
            X_normalized = (X - self.temp_min) / (self.temp_max - self.temp_min)
            X_normalized = np.clip(X_normalized, 0, 1)
            self.X_processed = X_normalized[..., np.newaxis]
            logger.debug(f"X_processed shape: {self.X_processed.shape}")
            logger.debug(f"Normalized range: [{np.min(self.X_processed):.3f}, {np.max(self.X_processed):.3f}]")
            # Normalize for visualization
            min_val, max_val = np.min(data_array), np.max(data_array)
            norm_data = (data_array - min_val) / (max_val - min_val)
            norm_data = (norm_data * 255).astype(np.uint8)

            heatmap = cv2.applyColorMap(norm_data, cv2.COLORMAP_JET)
            heatmap = cv2.resize(heatmap, (640, 480), interpolation=cv2.INTER_NEAREST)

            ret, jpeg = cv2.imencode('.jpg', heatmap)

            return jpeg.tobytes(), list(self.df)

        except RuntimeError as e:
            logger.warning(f'Sensor read error (RuntimeError): {e}')
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error in get_frame: {e}")
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
    
    def predict_from_camera(self):
        X_pred = self.model.predict(self.X_processed)
        confidence = float(X_pred[0][0]) if X_pred.shape[1] == 1 else float(np.max(X_pred))
        y_pred = (X_pred > 0.5).astype(int)
        logger.info(y_pred)
        if y_pred == 1:
            logger.info("Human")
            return True 
        else:
            logger.info("Non-Human")
            return False