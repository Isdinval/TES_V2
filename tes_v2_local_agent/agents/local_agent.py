import os
import time
import cv2
import numpy as np
import json
from loguru import logger
from datetime import datetime
from typing import List, Dict, Any, Optional
from tes_v2_local_agent.core.mapping_loader import MappingLoader
from tes_v2_local_agent.core.data_loader import DataLoader
from tes_v2_local_agent.core.data_mapper import DataMapper
from tes_v2_local_agent.core.screen_detector import ScreenDetector
from tes_v2_local_agent.core.action_executor import ActionExecutor
from tes_v2_local_agent.core.navigator import Navigator
from tes_v2_local_agent.core.popup_handler import PopupHandler

class LocalAgent:
    def __init__(
        self,
        mappings_dir: str,
        ref_images_dir: str,
        popup_refs_dir: Optional[str] = None,
        dry_run: bool = False
    ):
        self.mappings_dir = mappings_dir
        self.ref_images_dir = ref_images_dir
        self.popup_refs_dir = popup_refs_dir
        self.dry_run = dry_run

        self.mapping_loader = MappingLoader()
        self.data_loader = DataLoader()
        self.data_mapper = DataMapper()
        self.detector = ScreenDetector(ref_images_dir)
        self.executor = None
        self.navigator = None
        self.popup_handler = None

        self.reports = []

    def run_scenario(self, data_file: str, scenario: List[str], start_from_screen: Optional[str] = None):
        logger.info(f"Starting automation session (Scenario: {scenario}, Dry Run: {self.dry_run})")
        all_data = self.data_loader.load_data(data_file)

        for index, record in enumerate(all_data):
            record_id = index + 1
            logger.info(f"=== [Record {record_id}/{len(all_data)}] Starting ===")

            report = {
                "record_index": index,
                "start_time": datetime.now().isoformat(),
                "screens": [],
                "status": "success",
                "error": None
            }

            try:
                self.execute_scenario_for_record(record, scenario, report, start_from_screen)
                logger.success(f"=== [Record {record_id}] Finished Successfully ===")
            except Exception as e:
                logger.error(f"=== [Record {record_id}] Failed: {e} ===")
                report["status"] = "failed"
                report["error"] = str(e)
                self._capture_error_state(record_id)

            report["end_time"] = datetime.now().isoformat()
            self.reports.append(report)

        self._save_final_report()

    def execute_scenario_for_record(self, record: Dict[str, Any], scenario: List[str], report: Dict[str, Any], start_screen: Optional[str] = None):
        screens_to_process = scenario
        if start_screen and start_screen in scenario:
            start_index = scenario.index(start_screen)
            screens_to_process = scenario[start_index:]

        for i, screen_name in enumerate(screens_to_process):
            screen_report = {"screen_name": screen_name, "actions": [], "status": "pending"}
            report["screens"].append(screen_report)

            logger.info(f"Targeting Screen: {screen_name}")

            # 1. Load mapping
            mapping_path = os.path.join(self.mappings_dir, f"{screen_name}.json")
            mapping = self.mapping_loader.load_screen_mapping(mapping_path)

            # 2. Lazy Init components
            if not self.executor:
                self.executor = ActionExecutor(tuple(mapping.meta.resolution), dry_run=self.dry_run)
                self.navigator = Navigator(self.executor)
                if self.popup_refs_dir:
                    self.popup_handler = PopupHandler(self.popup_refs_dir, self.executor)

            # 3. Detect & Wait
            self._wait_for_screen(screen_name)
            screen_report["status"] = "detected"

            # 4. Fill
            self.execute_screen_actions(mapping, record, screen_report)
            screen_report["status"] = "filled"

            # 5. Navigate
            if i < len(screens_to_process) - 1:
                next_screen = screens_to_process[i + 1]
                if self.navigate_to(mapping, next_screen):
                    screen_report["status"] = "navigated"
                else:
                    logger.warning(f"No navigation link found for {next_screen}, assuming manual transition or end of flow.")

    def execute_screen_actions(self, mapping, record: Dict[str, Any], screen_report: Dict[str, Any]):
        actions = self.data_mapper.map_record_to_screen(record, mapping)

        for field, value in actions:
            action_info = {"logical_key": field.logical_key, "value": value, "status": "pending"}
            screen_report["actions"].append(action_info)
            try:
                self.executor.execute_action(field, value)
                action_info["status"] = "success"
            except Exception as e:
                action_info["status"] = "failed"
                action_info["error"] = str(e)
                raise

    def navigate_to(self, current_mapping, next_screen_name: str) -> bool:
        if self.dry_run:
            logger.info(f"[DRY RUN] Navigation to {next_screen_name}")
            return True

        if self.navigator.navigate_to_screen(current_mapping, next_screen_name):
            time.sleep(1.5)
            return True
        return False

    def _wait_for_screen(self, screen_name: str, max_retries: int = 5):
        if self.dry_run:
            return

        ref_img_path = os.path.join(self.ref_images_dir, f"{screen_name}.png")
        for attempt in range(max_retries):
            if not os.path.exists(ref_img_path):
                logger.warning(f"No ref image for {screen_name}, skipping.")
                return

            if self.detector.detect_screen(screen_name, ref_img_path):
                return

            if self.popup_handler:
                shot = self.detector.capture_screenshot()
                shot_cv = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2GRAY)
                if self.popup_handler.check_and_handle(shot_cv):
                    time.sleep(1)
                    continue

            logger.info(f"Waiting for {screen_name} (Attempt {attempt+1}/{max_retries})...")
            time.sleep(2)

        raise RuntimeError(f"Screen {screen_name} not detected.")

    def _capture_error_state(self, record_id: int):
        if not self.dry_run:
            error_file = f"error_record_{record_id}_{int(time.time())}.png"
            self.detector.capture_screenshot().save(error_file)
            logger.error(f"Error screenshot saved: {error_file}")

    def _save_final_report(self):
        report_file = f"execution_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.reports, f, indent=2, ensure_ascii=False)
        logger.info(f"Final execution report saved to {report_file}")
