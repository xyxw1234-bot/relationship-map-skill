import re
import tomllib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "3.0.4"


class ReleaseContractTests(unittest.TestCase):
    def test_release_versions_are_unified(self):
        manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        installer = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        runtime_skill = (ROOT / "skills" / "relationship-map" / "SKILL.md").read_text(encoding="utf-8")
        install_contract = (ROOT / "INSTALL.md").read_text(encoding="utf-8")

        self.assertEqual(EXPECTED_VERSION, manifest["version"])
        self.assertEqual(EXPECTED_VERSION, project["project"]["version"])
        self.assertIn(f"version: {EXPECTED_VERSION}", installer)
        self.assertIn(f"version: {EXPECTED_VERSION}", runtime_skill)
        self.assertIn(f"relationship-map-vault@{EXPECTED_VERSION}", install_contract)
        self.assertIn("/main/SKILL.md", install_contract)

    def test_distribution_has_one_plugin_manifest_and_one_runtime_skill(self):
        self.assertTrue((ROOT / "plugin.yaml").is_file())
        self.assertTrue((ROOT / "__init__.py").is_file())
        self.assertTrue((ROOT / "after-install.md").is_file())
        self.assertTrue((ROOT / "skills" / "relationship-map" / "SKILL.md").is_file())
        self.assertFalse((ROOT / "relationship_map_plugin" / "plugin.yaml").exists())
        self.assertFalse((ROOT / "relationship_map_plugin" / "skills").exists())
        self.assertFalse((ROOT / "人脉地图").exists())

    def test_public_text_has_no_line_number_prefix_artifacts(self):
        for path in [
            ROOT / "SKILL.md",
            ROOT / "after-install.md",
            ROOT / "skills" / "relationship-map" / "SKILL.md",
        ]:
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertIsNone(re.match(r"^\d+\|", line), f"{path}: {line}")

    def test_manifest_declares_all_runtime_tools(self):
        manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
        from relationship_map_plugin.relationship_map_plugin.tools import TOOL_DEFINITIONS

        self.assertEqual(
            [name for name, _, _ in TOOL_DEFINITIONS],
            manifest["provides_tools"],
        )


if __name__ == "__main__":
    unittest.main()
