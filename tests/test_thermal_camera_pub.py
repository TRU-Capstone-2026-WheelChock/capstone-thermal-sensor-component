import importlib
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class StopPublisherLoop(Exception):
    pass


@pytest.fixture
def thermal_camera_pub_module(monkeypatch):
    msg_handler_module = types.ModuleType("msg_handler")
    pub_base_module = types.ModuleType("msg_handler.pub_base")
    schemas_module = types.ModuleType("msg_handler.schemas")
    frame_writer_module = types.ModuleType("capstone_thermal_sensor.frame_writer")

    class DummyBasePublisher:
        pass

    class DummyZmqPubOptions:
        def __init__(self, endpoint):
            self.endpoint = endpoint

    class DummySensorPayload:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class DummySensorMessage:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class DummyGenericMessageDatatype:
        SENSOR = "sensor"

    class DummyWriterConfig:
        pass

    class DummyFrameFileWriter:
        def __init__(self, config, logger=None):
            self.config = config
            self.logger = logger

        def write(self, frame, ts, is_there_human):
            return None

    msg_handler_module.get_publisher = Mock()
    msg_handler_module.ZmqPubOptions = DummyZmqPubOptions
    msg_handler_module.pub_base = pub_base_module
    msg_handler_module.schemas = schemas_module

    pub_base_module.BasePublisher = DummyBasePublisher

    schemas_module.SensorMessage = DummySensorMessage
    schemas_module.SensorPayload = DummySensorPayload
    schemas_module.GenericMessageDatatype = DummyGenericMessageDatatype

    frame_writer_module.FrameFileWriter = DummyFrameFileWriter
    frame_writer_module.WriterConfig = DummyWriterConfig

    monkeypatch.setitem(sys.modules, "msg_handler", msg_handler_module)
    monkeypatch.setitem(sys.modules, "msg_handler.pub_base", pub_base_module)
    monkeypatch.setitem(sys.modules, "msg_handler.schemas", schemas_module)
    monkeypatch.setitem(
        sys.modules,
        "capstone_thermal_sensor.frame_writer",
        frame_writer_module,
    )
    monkeypatch.delitem(sys.modules, "capstone_thermal_sensor.thermal_camera_pub", raising=False)

    module = importlib.import_module("capstone_thermal_sensor.thermal_camera_pub")
    return module


def test_thermal_publisher_sends_sensor_message(thermal_camera_pub_module, monkeypatch):
    monkeypatch.setattr(thermal_camera_pub_module, "get_device_id", lambda: "device-123")
    monkeypatch.setattr(thermal_camera_pub_module, "get_device_name", lambda: "thermal-node")
    monkeypatch.setattr(thermal_camera_pub_module, "get_publish_interval_sec", lambda: 0.0)
    monkeypatch.setattr(thermal_camera_pub_module, "is_presentation_mode", lambda: False)

    publisher = thermal_camera_pub_module.ThermalPublisher()
    frame = object()
    read_camera = Mock(return_value=(frame, True))
    publisher._read_camera = read_camera
    publisher.presentation_writer = Mock()

    sent_messages = []

    def send(message):
        sent_messages.append(message)
        raise StopPublisherLoop

    connect_center = types.SimpleNamespace(send=Mock(side_effect=send))

    with pytest.raises(StopPublisherLoop):
        publisher._thermal_publisher(connect_center, is_presentation_mode=False)

    read_camera.assert_called_once_with()
    connect_center.send.assert_called_once()
    assert len(sent_messages) == 1

    message = sent_messages[0]
    assert message.sender_id == "device-123"
    assert message.sender_name == "thermal-node"
    assert message.data_type == "sensor"
    assert message.payload.isThereHuman is True
    assert message.payload.sensor_status == "OK"
    assert message.payload.sensor_status_code == 200
    publisher.presentation_writer.write.assert_not_called()


def test_thermal_publisher_writes_frame_in_presentation_mode(
    thermal_camera_pub_module,
    monkeypatch,
):
    monkeypatch.setattr(thermal_camera_pub_module, "get_device_id", lambda: "device-123")
    monkeypatch.setattr(thermal_camera_pub_module, "get_device_name", lambda: "thermal-node")
    monkeypatch.setattr(thermal_camera_pub_module, "get_publish_interval_sec", lambda: 0.5)
    monkeypatch.setattr(thermal_camera_pub_module, "is_presentation_mode", lambda: True)

    def stop_sleep(_seconds):
        raise StopPublisherLoop

    sleep_mock = Mock(side_effect=stop_sleep)
    monkeypatch.setattr(thermal_camera_pub_module.time, "sleep", sleep_mock)

    publisher = thermal_camera_pub_module.ThermalPublisher()
    writer = Mock()
    publisher.presentation_writer = writer
    frame = object()
    publisher._read_camera = Mock(return_value=(frame, False))

    connect_center = types.SimpleNamespace(send=Mock())

    with pytest.raises(StopPublisherLoop):
        publisher._thermal_publisher(connect_center, is_presentation_mode=True)

    writer.write.assert_called_once()
    kwargs = writer.write.call_args.kwargs
    assert kwargs["frame"] is frame
    assert kwargs["is_there_human"] is False
    assert kwargs["ts"] is not None
    sleep_mock.assert_called_once_with(0.5)


def test_run_builds_pub_option_and_uses_context_manager(
    thermal_camera_pub_module,
    monkeypatch,
):
    monkeypatch.setattr(thermal_camera_pub_module, "get_device_id", lambda: "device-123")
    monkeypatch.setattr(thermal_camera_pub_module, "get_device_name", lambda: "thermal-node")
    monkeypatch.setattr(thermal_camera_pub_module, "get_publish_interval_sec", lambda: 0.0)
    monkeypatch.setattr(thermal_camera_pub_module, "is_presentation_mode", lambda: False)
    monkeypatch.setattr(thermal_camera_pub_module, "get_endpoint", lambda name: "tcp://center:5557")

    publisher = thermal_camera_pub_module.ThermalPublisher()
    thermal_loop = Mock()
    monkeypatch.setattr(publisher, "_thermal_publisher", thermal_loop)

    pub = object()
    context_manager = Mock()
    context_manager.__enter__ = Mock(return_value=pub)
    context_manager.__exit__ = Mock(return_value=False)

    get_publisher_mock = Mock(return_value=context_manager)
    monkeypatch.setattr(thermal_camera_pub_module, "get_publisher", get_publisher_mock)

    publisher.run()

    get_publisher_mock.assert_called_once()
    pub_option = get_publisher_mock.call_args.args[0]
    assert pub_option.endpoint == "tcp://center:5557"
    thermal_loop.assert_called_once_with(pub, is_presentation_mode=False)
