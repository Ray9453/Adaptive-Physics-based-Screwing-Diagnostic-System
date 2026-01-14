import numpy as np
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Tuple
from apsd.core.feature_extractor import PhysicalFeatures
from apsd.models.results import DiagnosisResult, OptimizationSuggestion

# 狀態常數
STATE_COLD_START = "COLD_START"       # < 1 筆
STATE_SHADOW_MODE = "SHADOW_MODE"     # 1 - 50 筆
STATE_STABILIZING = "STABILIZING"     # 51 - 99 筆
STATE_ESTABLISHED = "ESTABLISHED"     # >= 100 筆

@dataclass
class ModelStats:
    """統計特徵容器"""
    mean: np.ndarray        # [peak_torque, rigidity_slope, total_work]
    std: np.ndarray         # [peak_torque, rigidity_slope, total_work]
    n_samples: int

    def to_dict(self):
        return {
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "n_samples": self.n_samples
        }

    @staticmethod
    def from_dict(data):
        return ModelStats(
            mean=np.array(data["mean"]),
            std=np.array(data["std"]),
            n_samples=data["n_samples"]
        )

class HoleModel:
    def __init__(self, hole_id: str):
        self.hole_id = hole_id
        self.count = 0
        
        # 數據容器
        # 1. 黃金基準 (前 100 筆固定)
        self.golden_buffer: List[np.ndarray] = [] 
        self.golden_stats: Optional[ModelStats] = None
        
        # 2. 循環更新 (最近 500 筆)
        self.rolling_buffer = deque(maxlen=500)
        self.rolling_stats: Optional[ModelStats] = None
        
        # 系統狀態
        self.status = STATE_COLD_START

    def _calculate_stats(self, buffer: List[np.ndarray]) -> ModelStats:
        """計算緩衝區內的均值與標準差"""
        if not buffer:
            return ModelStats(np.zeros(3), np.zeros(3), 0)
        
        matrix = np.array(buffer)
        return ModelStats(
            mean=np.mean(matrix, axis=0),
            std=np.std(matrix, axis=0) + 1e-6, # 加微小值避免除以零
            n_samples=len(buffer)
        )

    def update(self, features: PhysicalFeatures):
        """
        更新模型狀態：
        1. 接收新特徵
        2. 更新計數器與緩衝區
        3. 觸發狀態轉換 (Shadow -> Golden -> Rolling)
        """
        vec = features.to_vector() # [peak_torque, rigidity_slope, total_work]
        self.count += 1

        # 寫入 Rolling Buffer
        self.rolling_buffer.append(vec)
        
        # 狀態機邏輯
        if self.count <= 100:
            # 建立黃金基準階段
            self.golden_buffer.append(vec)
            
            if self.count <= 50:
                self.status = STATE_SHADOW_MODE
            else:
                self.status = STATE_STABILIZING
                
            # 當剛好滿 100 筆時，鎖定黃金基準
            if self.count == 100:
                self.golden_stats = self._calculate_stats(self.golden_buffer)
                print(f"[{self.hole_id}] Golden Base Established with 100 samples.")
        else:
            # 長期監控階段
            self.status = STATE_ESTABLISHED
        
        # 每次更新 Rolling Stats (對應 Welford 的替代方案，利用 numpy 快速重算)
        self.rolling_stats = self._calculate_stats(list(self.rolling_buffer))

    def evaluate(self, features: PhysicalFeatures, tolerance_factor: float = 3.0) -> DiagnosisResult:
        """
        診斷邏輯：
        根據當前狀態與生產寬容度，判斷 OK/NG
        """
        vec = features.to_vector()
        
        # 1. 冷啟動模式 (數據量 < 2，無法統計)
        # 注意：硬物理限制 (Heuristic) 應在外部 FeatureExtractor 檢查
        # 這裡假設如果進來就是要在統計層面檢查
        if self.count < 2 or self.rolling_stats is None:
             return DiagnosisResult("OK", "", "", "R00", health_score=100)

        # 2. 決定使用的基準 (優先使用 Rolling 以適應環境，但需監控 Drift)
        # 初期使用 rolling_stats，它包含了所有數據
        stats = self.rolling_stats
        
        # 計算 Z-Score: (x - mean) / std
        z_scores = np.abs((vec - stats.mean) / stats.std)
        
        # 3. 判斷邏輯
        # Shadow Mode (前50筆): 強制寬容度至少 3.0，避免初期資料不足導致誤殺
        effective_tolerance = max(3.0, tolerance_factor) if self.status == STATE_SHADOW_MODE else tolerance_factor
        
        # 檢查是否超出 Sigma 界限
        # 0: Torque, 1: Slope, 2: Work
        is_ng = np.any(z_scores > effective_tolerance)
        
        if not is_ng:
            # 計算健康度 (基於 Z-Score，越接近 0 越健康)
            max_z = np.max(z_scores)
            health = max(0, 100 - (max_z / effective_tolerance) * 100)
            return DiagnosisResult("OK", "", "", "R00", health_score=health)
        else:
            # NG 分類邏輯 (對應 E-Code)
            e_code = "E00"
            r_code = "R00"
            
            # 優先級：斜率 (載具/螺絲) > 扭力 (工具/設定) > 做功 (材質)
            if z_scores[1] > effective_tolerance: # Rigidity Slope 異常
                # 斜率異常通常代表：滑牙 (低斜率) 或 卡死 (高斜率)
                e_code = "E04" # 假設 E04 = 斜率異常
                r_code = "R04" # 檢查螺紋或更換螺絲
            elif z_scores[0] > effective_tolerance: # Peak Torque 異常
                e_code = "E02" # 扭力過高/過低
                r_code = "R02" # 檢查工具設定
            elif z_scores[2] > effective_tolerance: # Work 異常
                e_code = "E08" # 材質異常 (如：墊片遺失導致做功變少)
                r_code = "R08" # 檢查墊片
            
            return DiagnosisResult("NG", e_code, "1.0", r_code, health_score=0) 


    def get_optimization_suggestion(self) -> OptimizationSuggestion:
        """
        提供回控優化建議 (基於 Golden Base 與 Rolling 的差異)
        對應系統需求 Requirement 13.
        邏輯：
        1. 穩定性檢查 (Stability): 若變異係數 (CV) 過高，建議降低轉速以提升穩定度。
        2. 趨勢漂移檢查 (Drift): 若均值偏移過大，建議修正目標扭力。
        """
        if self.golden_stats is None or self.rolling_stats is None:
            return OptimizationSuggestion("N/A", "", "", "", {})
            
        params = {}
        actions = []
        
        # 1. 穩定性檢查 (基於 Torque 的變異係數 CV = Std / Mean)
        # 假設 CV > 3% 代表不穩定 (工業常見標準)
        current_mean_torque = self.rolling_stats.mean[0]
        current_std_torque = self.rolling_stats.std[0]
        cv = current_std_torque / (current_mean_torque + 1e-6)
        
        if cv > 0.03: 
            # 變異過大，建議降低轉速
            params["suggested_speed_adjustment_percent"] = -10 # 降低 10%
            params["reason_speed"] = f"High Variance (CV={cv:.2%}), reduce speed to stabilize."
            actions.append("REDUCE_SPEED")
            
        # 2. 趨勢漂移檢查 (Drift)
        # 如果 Rolling Mean 與 Golden Mean 差異超過 1.5 個標準差
        drift = np.abs(self.rolling_stats.mean - self.golden_stats.mean) / self.golden_stats.std
        
        if np.any(drift > 1.5):
            # 偵測到漂移，建議更新參數
            new_target_torque = float(self.rolling_stats.mean[0])
            original_target_torque = float(self.golden_stats.mean[0])
            
            # 計算百分比變化: (New - Old) / Old * 100
            if original_target_torque != 0:
                pct_change = ((new_target_torque - original_target_torque) / original_target_torque) * 100
            else:
                pct_change = 0.0
                
            params["suggested_torque_adjustment_percent"] = round(pct_change, 1)
            params["reason_torque"] = f"Mean Drift Detected ({drift[0]:.2f} sigma)"
            actions.append("UPDATE_TORQUE")

        if actions:
            return OptimizationSuggestion(
                status="OPTIMIZE",
                e_code="DRIFT_DETECTED",
                w_code="0.8",
                r_code="UPDATE_PARAM",
                params=params
            )
            
        return OptimizationSuggestion("STABLE", "", "", "", {})
    
    def to_dict(self):
        """序列化用於儲存"""
        return {
            "hole_id": self.hole_id,
            "count": self.count,
            "status": self.status,
            "golden_stats": self.golden_stats.to_dict() if self.golden_stats else None,
            "rolling_buffer": list([v.tolist() for v in self.rolling_buffer]), # 存 raw buffer
            # golden_buffer 通常不存全部，只存 stats 節省空間，或存最近的
        }

    @staticmethod
    def from_dict(data):
        """反序列化載入"""
        model = HoleModel(data["hole_id"])
        model.count = data["count"]
        model.status = data["status"]
        
        if data["golden_stats"]:
            model.golden_stats = ModelStats.from_dict(data["golden_stats"])
            
        if data["rolling_buffer"]:
            for vec in data["rolling_buffer"]:
                model.rolling_buffer.append(np.array(vec))
            # 重算 rolling stats
            model.rolling_stats = model._calculate_stats(list(model.rolling_buffer))
            
        return model
