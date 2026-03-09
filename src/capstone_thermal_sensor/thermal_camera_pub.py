from __future__ import annotations

from datetime import datetime
import logging
import time
from Img_predictor import Img_predictor

import numpy as np
from msg_handler import get_publisher, ZmqPubOptions
import msg_handler.pub_base
import msg_handler.schemas as mschema

from capstone_thermal_sensor.config import (
    get_device_id,
    get_device_name,
    get_endpoint,
    get_publish_interval_sec,
    is_presentation_mode,
)
from capstone_thermal_sensor.frame_writer import FrameFileWriter, WriterConfig


class ThermalPublisher:
    def __init__(self, logger: logging.Logger | None = None):
        self.device_id = get_device_id()
        self.device_name = get_device_name()
        self.logger = logger or logging.getLogger("ThermalPublisher")
        self.loop_sleep_sec = get_publish_interval_sec()

        self.is_presentation_mode = is_presentation_mode()
        self.presentation_writer = (
            FrameFileWriter(WriterConfig(), logger=self.logger)
            if self.is_presentation_mode
            else None
        )

        # TODO: Replace with real camera service.
        self.camera = Img_predictor()

    def _read_camera(self) -> tuple[np.ndarray | None, bool]:
        """
        Read one frame from camera.
        Return: (frame_2d_or_1d_thermal_array, is_there_human)
        """
        picture, raw_data = self.camera.camera()
        human_dected = self.camera.predict_from_camera()
             
        if self.camera is None:
            return None, False
        # Example contract for future camera integration:
        # frame, is_there_human = self.camera.get_frame_and_human_state()
        # return frame, bool(is_there_human)
        return raw_data, human_dected

    def _thermal_publisher(
        self,
        connect_center: msg_handler.pub_base.BasePublisher,
        is_presentation_mode: bool = True,
    ) -> None:
        while True:
            now = datetime.now()

            ####################################################
            # DO CAMERA CONTROL HERE
            # REMEMBER this is in the loop
            #####################################################
            frame, is_there_human = self._read_camera()

            connect_center.send(
                mschema.SensorMessage(
                    sender_id=self.device_id,
                    sender_name=self.device_name,
                    timestamp=now,
                    data_type=mschema.GenericMessageDatatype.SENSOR,
                    payload=mschema.SensorPayload(
                        isThereHuman=is_there_human,
                        sensor_status="OK",
                        sensor_status_code=200,
                    ),
                )
            )

            if is_presentation_mode and self.presentation_writer and frame is not None:
                self.presentation_writer.write(
                    frame=frame,
                    ts=now,
                    is_there_human=is_there_human,
                )

            if self.loop_sleep_sec > 0:
                time.sleep(self.loop_sleep_sec)

    def run(self):
        pub_option = ZmqPubOptions(
            endpoint=get_endpoint("center")
        )

        ##################################
        # SET UP CAMERA HERE
        ##################################

        with get_publisher(pub_option) as pub:
            self._thermal_publisher(pub, is_presentation_mode=self.is_presentation_mode)
