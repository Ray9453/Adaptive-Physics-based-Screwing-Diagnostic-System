import numpy as np
from scipy import stats
from scipy.interpolate import interp1d

class SignalProcessor:
    @staticmethod
    def sanitize_signal(data: np.ndarray, threshold: float = 32000) -> np.ndarray:
        """
        清洗信號：去除溢出值 (e.g., 32767) 與異常負值，並使用中值濾波修補。
        對應文件 Section 2.1.1 Handling Signal Anomalies
        """
        # 標記無效值 (溢出或負值)
        mask = (data > threshold) | (data < 0)
        
        if not np.any(mask):
            return data
            
        clean_data = data.copy()
        # 簡單的線性插值修補 (對於邊緣運算比完整 Median Filter 更快)
        # 若是連續壞值，則使用前後有效值的平均
        x = np.arange(len(data))
        valid_mask = ~mask
        
        if np.sum(valid_mask) < 2:
            return np.zeros_like(data) # 數據損壞過於嚴重
            
        f = interp1d(x[valid_mask], clean_data[valid_mask], kind='linear', fill_value="extrapolate")
        clean_data[mask] = f(x[mask])
        
        return clean_data

    @staticmethod
    def resample_by_time(time: np.ndarray, data: np.ndarray, target_freq: float = 100.0) -> tuple[np.ndarray, np.ndarray]:
        """
        基於時間軸的重採樣，解決取樣率不穩問題。
        對應文件 Section 2.1.1 Data Gaps & Inconsistent Sampling
        """
        if len(time) < 2:
            return time, data
            
        duration = time[-1] - time[0]
        num_points = int(duration * target_freq)
        if num_points < 2:
            num_points = len(time) # 保持原樣如果時間太短
            
        new_time = np.linspace(time[0], time[-1], num_points)
        f = interp1d(time, data, kind='linear', fill_value="extrapolate")
        new_data = f(new_time)
        
        return new_time, new_data

    @staticmethod
    def calculate_robust_slope(x: np.ndarray, y: np.ndarray) -> float:
        """
        使用 Theil-Sen Estimator 計算強健斜率 (Rigidity Slope)。
        比最小平方法更能抵抗 Outliers (跳點)。
        對應文件 Section 2.1.1 Data Spikes and Jumps
        """
        if len(x) < 3:
            return 0.0
        
        # 使用 scipy 的 Theil-Sen 實作
        res = stats.theilslopes(y, x, alpha=0.95)
        return res[0] # 回傳斜率

    @staticmethod
    def calculate_work(torque: np.ndarray, angle: np.ndarray) -> float:
        """
        計算做功 (Work Done) = 扭力對角度的積分。
        對應文件 Section 3.2 Work-to-Torque Ratio (Energy Domain Analysis)
        """
        # 轉換角度為弧度 (假設輸入是度)
        angle_rad = np.deg2rad(angle)
        # 使用梯形積分法
        work = np.trapezoid(torque, angle_rad)
        return max(0.0, work)
