import json
import os
import shutil
from typing import Dict
from apsd.core.learning import HoleModel

class ModelManager:
    def __init__(self, storage_dir: str = "saved_models"):
        self.storage_dir = storage_dir
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def _get_filepath(self, carrier_id: str) -> str:
        # 確保檔名安全，避免路徑遍歷攻擊
        safe_id = "".join([c for c in carrier_id if c.isalnum() or c in ('-', '_')])
        return os.path.join(self.storage_dir, f"{safe_id}.json")

    def save_model(self, carrier_id: str, hole_models: Dict[str, HoleModel]):
        """
        儲存載具下所有孔位的模型狀態。
        使用 Atomic Write 防止斷電導致檔案損壞。
        """
        filepath = self._get_filepath(carrier_id)
        tmp_path = filepath + ".tmp"
        
        # 將所有 HoleModel 轉為 Dict
        data_to_save = {
            h_id: model.to_dict() 
            for h_id, model in hole_models.items()
        }
        
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            
            # 原子操作：只有寫入成功才會覆蓋舊檔
            os.replace(tmp_path, filepath)
            
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise IOError(f"Failed to save model for {carrier_id}: {str(e)}")

    def load_model(self, carrier_id: str) -> Dict[str, HoleModel]:
        """
        載入載具模型。若檔案不存在，回傳空字典。
        """
        filepath = self._get_filepath(carrier_id)
        
        if not os.path.exists(filepath):
            return {}
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 反序列化回 HoleModel 物件
            hole_models = {}
            for h_id, m_data in data.items():
                hole_models[h_id] = HoleModel.from_dict(m_data)
                
            return hole_models
            
        except (json.JSONDecodeError, KeyError) as e:
            # 若檔案損壞，建議備份壞檔並回傳空模型，避免系統卡死
            print(f"Error loading model {carrier_id}: {e}. Starting fresh.")
            if os.path.exists(filepath): # Ensure file exists before copy
                 shutil.copy(filepath, filepath + ".corrupted")
            return {}
