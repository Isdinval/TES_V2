import os
import sys
from unittest.mock import MagicMock

# Mock everything that needs a DISPLAY
sys.modules['pyautogui'] = MagicMock()
sys.modules['mouseinfo'] = MagicMock()
sys.modules['pynput'] = MagicMock()
sys.modules['pynput.keyboard'] = MagicMock()
sys.modules['mss'] = MagicMock()

from tes_v2_local_agent.agents.local_agent import LocalAgent

def test_dry_run():
    # Setup paths
    mappings = "tes_v2_local_agent/examples/mappings"
    refs = "tes_v2_local_agent/examples/refs"
    data = "tes_v2_local_agent/examples/test_data.json"
    scenario = ["Login", "Dashboard"]

    # Initialize agent in dry_run mode
    agent = LocalAgent(mappings, refs, dry_run=True)

    # Mock some methods that depend on OS/Display or images
    agent.detector.capture_screenshot = MagicMock()
    agent.detector.detect_screen = MagicMock(return_value=True)
    # Mock cv2 if needed
    import cv2
    cv2.imread = MagicMock()
    cv2.matchTemplate = MagicMock()
    cv2.minMaxLoc = MagicMock(return_value=(0, 1, (0,0), (0,0)))

    print("--- Starting Dry Run Test ---")
    agent.run_scenario(data, scenario)
    print("--- Dry Run Test Finished ---")

if __name__ == "__main__":
    test_dry_run()
