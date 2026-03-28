from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
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

if TYPE_CHECKING:
    from capstone_thermal_sensor.Img_predictor import Img_predictor

ThermalFrame = npt.NDArray[np.float32]

class ThermalPublisher:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        from capstone_thermal_sensor.Img_predictor import Img_predictor

        self.device_id = get_device_id()
        self.device_name = get_device_name()
        self.logger = logger or logging.getLogger("ThermalPublisher")
        self.loop_sleep_sec = get_publish_interval_sec()

        self.is_presentation_mode = is_presentation_mode()
        self.presentation_writer: FrameFileWriter | None = (
            FrameFileWriter(WriterConfig(), logger=self.logger)
            if self.is_presentation_mode
            else None
        )
        self.picture: bytes | None = None
        self.is_there_human: bool = False
        self.frame: ThermalFrame | None = None
        self._camera_error_logged: bool = False
        self.camera: Img_predictor | None = None

        try:
            self.camera = Img_predictor()
        except Exception:
            self.logger.exception("Image predictor failed to submit")

    def _fallback_frame(self) -> ThermalFrame:
        # 一定値だと FrameFileWriter 側で 0 に正規化され、
        # COLORMAP_JET で青系の表示になります
        return np.full((24, 32), -40.0, dtype=np.float32)

    def _read_camera(self) -> tuple[ThermalFrame, bool, bytes | None, bool]:
        """
        Return:
            frame, is_there_human, picture, is_camera_ok
        """
        if self.camera is None:
            if not self._camera_error_logged:
                self.logger.error("Camera is not initialized. Using fallback frame.")
                self._camera_error_logged = True
            return self._fallback_frame(), False, None, False

        try:
            picture, raw_data = self.camera.camera()
            if raw_data is None:
                raise RuntimeError("camera() returned no thermal data")

            human_detected = bool(self.camera.predict_from_camera())
            frame = np.asarray(raw_data, dtype=np.float32)

            self._camera_error_logged = False
            return frame, human_detected, picture, True

        except Exception:
            if not self._camera_error_logged:
                self.logger.exception("Camera read failed. Using fallback frame.")
                self._camera_error_logged = True
            return self._fallback_frame(), False, None, False

    def _thermal_publisher(
        self,
        connect_center: msg_handler.pub_base.BasePublisher,
        is_presentation_mode: bool = True,
    ) -> None:
        while True:
            now = datetime.now()

            frame, is_there_human, picture, is_camera_ok = self._read_camera()
            self.frame = frame
            self.is_there_human = is_there_human
            self.picture = picture

            if is_camera_ok:
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

            if is_presentation_mode and self.presentation_writer is not None:
                self.presentation_writer.write(
                    frame=frame,
                    ts=now,
                    is_there_human=is_there_human,
                )

            if self.loop_sleep_sec > 0:
                time.sleep(self.loop_sleep_sec)

    def run(self) -> None:
        pub_option = ZmqPubOptions(endpoint=get_endpoint("center"))

        ##################################
        # SET UP CAMERA HERE
        ##################################

        with get_publisher(pub_option) as pub:
            self._thermal_publisher(pub, is_presentation_mode=self.is_presentation_mode)
