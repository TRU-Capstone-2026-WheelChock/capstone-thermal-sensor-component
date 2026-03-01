import logging
from capstone_thermal_sensor.thermal_camera_pub import ThermalPublisher

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tp = ThermalPublisher()
    try:
        tp.run()
    except KeyboardInterrupt:
        pass