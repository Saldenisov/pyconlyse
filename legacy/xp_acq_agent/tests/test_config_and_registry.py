import json
import os
import shutil
import tempfile
import unittest

from elyse_agent.channel_registry import ChannelRegistry
from elyse_agent.config import load_config
from elyse_agent.errors import ConfigError


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigAndRegistryTests(unittest.TestCase):
    def test_xp_config_is_fail_closed(self):
        config = load_config(os.path.join(ROOT, "config.xp.json"))
        self.assertEqual(config["mode"], "discover_only")
        self.assertIs(config["allow_hardware_writes"], False)

    def test_hardware_writes_cannot_be_enabled(self):
        temp_dir = tempfile.mkdtemp()
        try:
            path = os.path.join(temp_dir, "config.json")
            with open(path, "w") as stream:
                json.dump({"allow_hardware_writes": True}, stream)
            with self.assertRaises(ConfigError):
                load_config(path)
        finally:
            shutil.rmtree(temp_dir)

    def test_recovered_csv_tables_load(self):
        registry = ChannelRegistry(os.path.join(ROOT, "data")).load()
        summary = registry.summary()
        self.assertGreater(summary["channel_map.csv"], 100)
        self.assertEqual(summary["ni6602_timing.csv"], 8)


if __name__ == "__main__":
    unittest.main()
