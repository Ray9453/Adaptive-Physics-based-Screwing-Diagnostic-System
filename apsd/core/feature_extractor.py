import numpy as np
from dataclasses import dataclass
from apsd.models.input_data import CurveData
from apsd.utils.math_utils import SignalProcessor

@dataclass
class PhysicalFeatures:
    """單次鎖附的物理指紋 (Physical Fingerprint)"""
    peak_torque: float       # 最終扭力 (Nm)
    seating_angle: float     # 貼合後轉角 (Degree)
    rigidity_slope: float    # 剛性斜率 (Nm/deg)
    total_work: float        # 總做功 (J)
    snug_torque: float       # 貼合點扭力 (Nm)
    
    def to_vector(self) -> np.ndarray:
        return np.array([self.peak_torque, self.rigidity_slope, self.total_work])

class FeatureExtractor:
    def __init__(self):
        self.processor = SignalProcessor()

    def _detect_snug_point(self, torque: np.ndarray, angle: np.ndarray) -> int:
        """
        偵測 Snug Point (貼合點)。
        邏輯：尋找扭力上升率發生顯著變化的點 (二階導數峰值或扭力閾值)。
        對應文件 Section 2.2 Physical Zero-Point Correction
        """
        # 簡易實作：取最大扭力的 10% 作為起始貼合點 (比二階導數在噪聲下更穩定)
        # 若需要更精確的二階導數法，需先對數據進行 Savitzky-Golay 平滑
        peak_t = np.max(torque)
        threshold = peak_t * 0.10 # 10% 閾值
        
        indices = np.where(torque >= threshold)[0]
        if len(indices) > 0:
            return indices[0]
        return 0

    def extract(self, curve: CurveData) -> PhysicalFeatures:
        """
        從原始曲線提取物理特徵
        """
        # 1. 轉換為 Numpy Array
        t_raw = np.array(curve.torque)
        a_raw = np.array(curve.angle)
        time_raw = np.array(curve.time)

        # 2. 數據清洗 (Sanitization) [cite: 19]
        t_clean = self.processor.sanitize_signal(t_raw)
        
        # 3. 時間重採樣 (解決取樣率不穩) 
        # 為了計算一致性，統一重採樣到 100Hz (視需求調整)
        _, t_resampled = self.processor.resample_by_time(time_raw, t_clean)
        _, a_resampled = self.processor.resample_by_time(time_raw, a_raw)

        # 4. 尋找 Snug Point (物理零點修正) 
        snug_idx = self._detect_snug_point(t_resampled, a_resampled)
        
        # 擷取貼合後的有效區段 (Effective Zone)
        t_effective = t_resampled[snug_idx:]
        a_effective = a_resampled[snug_idx:]
        
        # 若有效區段太短，回傳預設值
        if len(t_effective) < 5:
            return PhysicalFeatures(0, 0, 0, 0, 0)

        # 5. 計算物理特徵
        # A. 最終扭力
        peak_torque = np.max(t_effective)
        
        # B. 貼合後轉角 (Seating Angle)
        # 修正角度：當前角度 - 貼合點角度
        seating_angle = a_effective[-1] - a_effective[0]
        
        # C. 剛性斜率 (Rigidity Slope dT/dtheta) [cite: 24, 44]
        # 取中間 50% 線性區段計算斜率
        mid_start = int(len(t_effective) * 0.3)
        mid_end = int(len(t_effective) * 0.8)
        slope = self.processor.calculate_robust_slope(
            a_effective[mid_start:mid_end], 
            t_effective[mid_start:mid_end]
        )
        
        # D. 總做功 (Energy) [cite: 57, 119]
        total_work = self.processor.calculate_work(t_effective, a_effective)
        
        # E. 貼合扭力
        snug_torque = t_effective[0]

        return PhysicalFeatures(
            peak_torque=float(peak_torque),
            seating_angle=float(seating_angle),
            rigidity_slope=float(slope),
            total_work=float(total_work),
            snug_torque=float(snug_torque)
        )

    def check_hard_constraints(self, features: PhysicalFeatures) -> list[str]:
        """
        第一層：物理硬限制檢查 (Heuristic Cold Start)。
        對應文件 Section 4.1 Stage 1: Heuristic Cold Start
        """
        errors = []
        
        # 規則 1: 斜率必須為正 (VDI 2647)
        if features.rigidity_slope <= 0:
            errors.append("E_NEG_SLOPE") # E-Code placeholder
            
        # 規則 2: 最終扭力必須大於貼合扭力
        if features.peak_torque <= features.snug_torque:
            errors.append("E_NO_TORQUE_RISE")
            
        # 規則 3: 做功必須大於 0
        if features.total_work <= 0:
            errors.append("E_ZERO_WORK")
            
        return errors
