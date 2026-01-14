from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict

@dataclass
class DiagnosisResult:
    status: str  # "OK" or "NG"
    e_code: str
    w_code: str  # Warning code (internal) or Weight
    r_code: str
    health_score: Optional[float] = None # 僅載具需要
    threshold_recommendation: Optional[float] = None # 僅載具需要

@dataclass
class OptimizationSuggestion:
    status: str
    e_code: str
    w_code: str
    r_code: str
    params: Dict[str, Any] # 推薦參數

@dataclass
class HoleDiagnosis:
    screw_issue: DiagnosisResult
    carrier_issue: DiagnosisResult
    tool_issue: DiagnosisResult
    machine_issue: DiagnosisResult
    data_issue: DiagnosisResult
    optimization: OptimizationSuggestion

    def to_dict(self):
        return {
            "screw_issue": asdict(self.screw_issue),
            "carrier_issue": asdict(self.carrier_issue),
            "tool_issue": asdict(self.tool_issue),
            "machine_issue": asdict(self.machine_issue),
            "data_issue": asdict(self.data_issue),
            "optimization_suggestion": asdict(self.optimization)
        }
