import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "3.1.2"


def manifest_value(key):
    for line in (ROOT / "plugin.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"missing manifest key: {key}")


def manifest_tools():
    lines = (ROOT / "plugin.yaml").read_text(encoding="utf-8").splitlines()
    start = lines.index("provides_tools:") + 1
    return [line.strip()[2:] for line in lines[start:] if line.startswith("  - ")]


class ReleaseContractTests(unittest.TestCase):
    def test_versions_and_public_contract_are_unified(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        installer = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        runtime = (ROOT / "skills" / "relationship-map" / "SKILL.md").read_text(encoding="utf-8")
        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(EXPECTED_VERSION, manifest_value("version"))
        self.assertEqual(EXPECTED_VERSION, project["project"]["version"])
        self.assertIn(f"version: {EXPECTED_VERSION}", installer)
        self.assertIn(f"version: {EXPECTED_VERSION}", runtime)
        self.assertIn(f"relationship-map-vault@{EXPECTED_VERSION}", install)
        self.assertIn(f"v{EXPECTED_VERSION}", readme)
        self.assertIn(f"## v{EXPECTED_VERSION}", changelog)
        self.assertIn("/main/SKILL.md", install)

    def test_manifest_equals_registered_tool_contract(self):
        from relationship_map_plugin.relationship_map_plugin.tools import TOOL_DEFINITIONS
        self.assertEqual([name for name, _, _ in TOOL_DEFINITIONS], manifest_tools())
        self.assertEqual(10, len(manifest_tools()))

    def test_single_root_plugin_and_clean_public_skill_files(self):
        self.assertTrue((ROOT / "__init__.py").is_file())
        self.assertTrue((ROOT / "after-install.md").is_file())
        self.assertTrue((ROOT / "skills" / "relationship-map" / "SKILL.md").is_file())
        self.assertFalse((ROOT / "relationship_map_plugin" / "plugin.yaml").exists())
        self.assertFalse((ROOT / "relationship_map_plugin" / "skills").exists())
        for path in (ROOT / "SKILL.md", ROOT / "after-install.md", ROOT / "skills" / "relationship-map" / "SKILL.md"):
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertIsNone(re.match(r"^\d+\|", line), f"line-number artifact in {path}")

    def test_install_paths_cannot_drift_back_to_short_welcome_copy(self):
        installer = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        after_install = (ROOT / "after-install.md").read_text(encoding="utf-8")
        install_contract = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        runtime_skill = (ROOT / "skills" / "relationship-map" / "SKILL.md").read_text(encoding="utf-8")
        required = [
            "① 🧭", "② 📝", "③ 🎯", "④ 🤝", "⑤ 📥",
            "请介绍一下人脉地图的全部能力，以及我可以怎么样使用它。",
        ]
        for name, text in {"installer": installer, "after_install": after_install}.items():
            for marker in required:
                self.assertIn(marker, text, f"{name} missing welcome marker: {marker}")
        self.assertIn("完整的手机端欢迎文案", install_contract)
        self.assertIn("不得将欢迎文案缩短", install_contract)
        self.assertIn("五类能力", runtime_skill)
        self.assertIn(required[-1], runtime_skill)

    def test_installer_uses_only_the_fast_state_aware_path(self):
        installer = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        for marker in [
            "单次终端调用", "GIT_CONFIG_COUNT=1", "timeout 45s",
            "codeload.github.com", "command -v unzip", "zipfile.ZipFile", "init -q",
            "官方 GitHub Archive 恢复", "relationship-map-vault",
        ]:
            self.assertIn(marker, installer)
        for forbidden in [
            "gateway restart", "discover_and_load", "sqlite3", "config.yaml",
            "git status", "读取本文件、根目录 `plugin.yaml`", "hermes config set",
            "os.makedirs", "vault.initialise", "SELF_CHECK", "/opt/data/plugins/",
        ]:
            self.assertNotIn(forbidden, installer)
        self.assertIn("不得执行源码审查、测试、数据库探查、日志扫描、进程扫描或 Gateway 重启", contract)
        self.assertIn("不写入任何安装自检记录", contract)
        self.assertIn("不得手工创建插件目录、下载散文件或修改 Hermes 配置", contract)
        self.assertIn("不得向用户发送版本、插件、网关、文件或验收结果的技术报告", contract)


if __name__ == "__main__":
    unittest.main()
