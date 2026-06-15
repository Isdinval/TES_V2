import json
import pandas as pd
from typing import Dict, Any, List, Union
from loguru import logger
from tes_v2_local_agent.models.input_data import InputData

class DataLoader:
    def load_json(self, file_path: str) -> Dict[str, Any]:
        logger.info(f"Loading JSON data from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def load_excel(self, file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Loading Excel data from {file_path}")
        df = pd.read_excel(file_path)
        # Convert all values to string or appropriate types for filling
        return df.to_dict(orient="records")

    def load_data(self, file_path: str) -> List[Dict[str, Any]]:
        if file_path.endswith(".json"):
            raw_data = self.load_json(file_path)
            if isinstance(raw_data, list):
                return raw_data
            return [raw_data]
        elif file_path.endswith((".xlsx", ".xls")):
            return self.load_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
