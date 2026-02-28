

from capstone_thermal_sensor.thermal_camera_pub import ThermalPublisher



if __name__ =="__main__":
    tp = ThermalPublisher()

    tp.run()