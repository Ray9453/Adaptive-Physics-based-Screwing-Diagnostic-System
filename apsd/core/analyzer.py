import logging
from typing import Dict, Any, Optional
from apsd.models.input_data import CurveData
from apsd.models.results import HoleDiagnosis, DiagnosisResult, OptimizationSuggestion
from apsd.core.feature_extractor import FeatureExtractor, PhysicalFeatures
from apsd.core.learning import HoleModel
from apsd.storage.model_manager import ModelManager
from apsd.storage.config_loader import ConfigLoader

# 設定 Logger
logger = logging.getLogger("APSD")

class APSDiagnosticSystem:
    def __init__(self, config_path: str = "configs/default_config.yaml", model_dir: str = "saved_models"):
        self.config = ConfigLoader.load_config(config_path)
        self.model_manager = ModelManager(storage_dir=model_dir)
        self.extractor = FeatureExtractor()
        
        # 記憶體快取：目前載入的載具模型 {carrier_id: {hole_id: HoleModel}}
        # 針對 Edge Device，我們可能只需要 cache 當前正在做的載具
        self._active_carrier_id: Optional[str] = None
        self._active_models: Dict[str, HoleModel] = {}

    def _get_model(self, carrier_id: str, hole_id: str) -> HoleModel:
        """取得指定孔位的模型，若切換載具則自動重新載入"""
        if self._active_carrier_id != carrier_id:
            # 切換載具：先儲存舊的（如果有的話），再載入新的
            if self._active_carrier_id:
                self.save_models() 
            
            logger.info(f"Switching carrier context to {carrier_id}")
            self._active_models = self.model_manager.load_model(carrier_id)
            self._active_carrier_id = carrier_id

        # 若該孔位是第一次出現，建立新模型
        if hole_id not in self._active_models:
            self._active_models[hole_id] = HoleModel(hole_id)
            
        return self._active_models[hole_id]

    def save_models(self):
        """手動觸發儲存 (通常在批次結束或程式關閉時呼叫)"""
        if self._active_carrier_id and self._active_models:
            self.model_manager.save_model(self._active_carrier_id, self._active_models)
            logger.info(f"Models saved for carrier {self._active_carrier_id}")

    def diagnose(self, carrier_id: str, data: Dict[str, dict]) -> Dict[str, Any]:
        """
        SDK 主入口方法
        :param carrier_id: 載具編號 (用作檔名)
        :param data: 輸入資料 dict，格式 {"孔位": {"扭力值": [], ...}}
        :return: 診斷結果 dict
        """
        results = {}

        for hole_id, raw_data in data.items():
            # 1. 資料驗證與轉換
            try:
                curve = CurveData(**raw_data)
            except Exception as e:
                logger.error(f"Data format error for {hole_id}: {e}")
                results[hole_id] = self._create_error_response("E99", "DATA_FORMAT_ERROR")
                continue

            # 2. 物理特徵提取
            features = self.extractor.extract(curve)

            # 3. Layer 1: 物理硬限制檢查 (Heuristic)
            # 這些規則來自 VDI 2647，違反則代表物理過程完全錯誤
            hard_errors = self.extractor.check_hard_constraints(features)
            
            if hard_errors:
                # 違反物理硬限制 -> 直接 NG，且不更新模型 (避免汙染)
                # 取第一個錯誤碼
                err_code = hard_errors[0] 
                results[hole_id] = self._create_result(
                    is_ok=False, 
                    e_code=err_code, 
                    r_code=self._map_r_code(err_code),
                    desc="Physics Constraint Violation"
                )
                continue

            # 4. Layer 2: 統計自適應學習 (AI Learning)
            model = self._get_model(carrier_id, hole_id)
            
            # 先更新模型 (讓它學習這次的正常物理特徵)
            model.update(features)
            
            # 再進行評估 (基於歷史數據 + 生產寬容度)
            diagnosis = model.evaluate(features, self.config.tolerance.production_tolerance_factor)
            
            # 5. 取得優化建議
            optimization = model.get_optimization_suggestion()

            # 6. 組合最終結果
            results[hole_id] = self._assemble_final_dict(diagnosis, optimization)

        # 自動儲存 (可選：或由外部控制)
        # 考慮到即時性，建議每次診斷完都存，或是外部定期呼叫 save_models
        # 這裡為了安全起見，每次都存 (配合 Atomic Write 效能尚可)
        self.save_models()

        return results

    def _create_result(self, is_ok: bool, e_code: str, r_code: str, desc: str) -> Dict[str, Any]:
        """建立標準化單項結果物件"""
        status = "OK" if is_ok else "NG"
        return self._assemble_final_dict(
            DiagnosisResult(status, e_code, "0.0", r_code, 100 if is_ok else 0),
            OptimizationSuggestion("N/A", "", "", "", {})
        )

    def _map_r_code(self, e_code: str) -> str:
        """簡單的 E-Code 轉 R-Code 映射 (可擴充)"""
        mapping = {
            "E_NEG_SLOPE": "R_CHECK_FIXTURE",
            "E_NO_TORQUE_RISE": "R_CHECK_SCREW",
            "E_ZERO_WORK": "R_CHECK_SENSOR"
        }
        return mapping.get(e_code, "R_GENERAL_CHECK")

    def _assemble_final_dict(self, diag: DiagnosisResult, opt: OptimizationSuggestion) -> Dict[str, Any]:
        """組裝符合使用者要求的最終 Dict 結構"""
        
        # 根據 NG 類型分派到不同類別 (這裡做簡化邏輯，實際可根據 E-Code 前綴分派)
        # 預設歸類為「螺絲問題」，若 E-Code 特定則歸類他處
        
        base_result = {
            "status": diag.status,
            "e_code": diag.e_code,
            "w_code": diag.w_code,
            "r_code": diag.r_code
        }
        
        # 建立預設空結果
        empty_result = {"status": "OK", "e_code": "", "w_code": "", "r_code": ""}
        
        # 構建輸出
        output = {
            "screw_issue": empty_result.copy(),
            "carrier_issue": empty_result.copy(),
            "tool_issue": empty_result.copy(),
            "machine_issue": empty_result.copy(),
            "data_issue": empty_result.copy(),
            "optimization_suggestion": {
                "status": opt.status,
                "e_code": opt.e_code,
                "w_code": opt.w_code,
                "r_code": opt.r_code,
                "params": opt.params
            }
        }
        
        # 載具需要額外欄位
        output["carrier_issue"]["health_score"] = diag.health_score if diag.health_score is not None else 100
        output["carrier_issue"]["threshold_recommendation"] = diag.threshold_recommendation

        # 簡單分派邏輯
        if diag.status == "NG":
            if "SLOPE" in diag.e_code or "E04" in diag.e_code:
                output["carrier_issue"].update(base_result) # 斜率通常與載具/孔位剛性有關
            elif "TORQUE" in diag.e_code or "E02" in diag.e_code:
                output["tool_issue"].update(base_result)
            elif "DATA" in diag.e_code:
                output["data_issue"].update(base_result)
            else:
                output["screw_issue"].update(base_result) # 預設

        return output
    
    def _create_error_response(self, e_code, msg):
        """資料層級錯誤的回傳"""
        return self._create_result(False, e_code, "R_CHECK_DATA", msg)
