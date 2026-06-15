import json
from loguru import logger
from tes_v2_local_agent.models.mapping import ScreenMapping

class MappingLoader:
    def load_screen_mapping(self, file_path: str) -> ScreenMapping:
        logger.info(f"Loading screen mapping from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ScreenMapping(**data)
