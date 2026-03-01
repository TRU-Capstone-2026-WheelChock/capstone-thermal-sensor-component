from typing import Any
from datetime import datetime
import numpy as np
from pydantic import BaseModel, field_validator, field_serializer, ConfigDict

class FrameModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frame: np.ndarray
    ts : datetime
    is_there_human : bool

    @field_validator("frame", mode="before")
    @classmethod
    def parse_frame(cls, v: Any) -> np.ndarray:
        if isinstance(v, np.ndarray):
            return v
        if isinstance(v, dict) and {"data", "shape", "dtype"} <= v.keys():
            arr = np.array(v["data"], dtype=v["dtype"])
            return arr.reshape(v["shape"])
        if isinstance(v, list):
            return np.array(v, dtype=np.float32)
        raise TypeError("Invalid frame format")

    @field_serializer("frame")
    def dump_frame(self, v: np.ndarray):
        return {
            "data": v.reshape(-1).tolist(),
            "shape": list(v.shape),
            "dtype": str(v.dtype),
        }
