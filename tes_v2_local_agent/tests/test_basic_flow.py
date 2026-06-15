import unittest
import json
import os
from tes_v2_local_agent.core.mapping_loader import MappingLoader
from tes_v2_local_agent.core.data_loader import DataLoader
from tes_v2_local_agent.models.mapping import ScreenMapping

class TestBasicFlow(unittest.TestCase):
    def setUp(self):
        self.mapping_file = "test_mapping.json"
        self.data_file = "test_data.json"

        self.mapping_data = {
            "meta": {
                "app": "TestApp",
                "screen": "Login",
                "created_at": "2023-10-27T10:00:00",
                "resolution": [1920, 1080]
            },
            "elements": [
                {
                    "stable_id": "sid1",
                    "logical_key": "username",
                    "ui_type": "input",
                    "action": "type",
                    "bbox_relative": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.05},
                    "source": "human",
                    "click_target": {"x": 0.25, "y": 0.225}
                }
            ]
        }
        with open(self.mapping_file, "w") as f:
            json.dump(self.mapping_data, f)

        self.records = [{"username": "testuser"}]
        with open(self.data_file, "w") as f:
            json.dump(self.records, f)

    def tearDown(self):
        if os.path.exists(self.mapping_file):
            os.remove(self.mapping_file)
        if os.path.exists(self.data_file):
            os.remove(self.data_file)

    def test_loaders(self):
        ml = MappingLoader()
        dl = DataLoader()

        mapping = ml.load_screen_mapping(self.mapping_file)
        self.assertEqual(mapping.meta.app, "TestApp")

        data = dl.load_data(self.data_file)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["username"], "testuser")

if __name__ == "__main__":
    unittest.main()
