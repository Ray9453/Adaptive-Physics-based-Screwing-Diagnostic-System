from typing import List, Dict
from pydantic import BaseModel, Field

class CurveData(BaseModel):
    """單一孔位的曲線數據"""
    torque: List[float] = Field(...)
    angle: List[float] = Field(...)
    time: List[float] = Field(...)

    class Config:
        populate_by_name = True

# 輸入格式: Dict[str, CurveData]  key="[1]1"
InputPayload = Dict[str, CurveData]
