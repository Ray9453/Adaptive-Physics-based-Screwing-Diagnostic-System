from typing import List, Dict
from pydantic import BaseModel

class ToleranceConfig(BaseModel):
    production_tolerance_factor: float = 3.0  # σ (Default 3.0)

class CodesConfig(BaseModel):
    disabled_e_codes: List[str] = []
    disabled_r_codes: List[str] = []

class SystemConfig(BaseModel):
    tolerance: ToleranceConfig
    codes: CodesConfig
