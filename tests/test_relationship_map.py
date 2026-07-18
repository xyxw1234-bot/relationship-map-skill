import csv
import os
import tempfile
import unittest
from pathlib import Path

from relationship_map_plugin.relationship_map_plugin import spreadsheet, vault


class RelationshipMapVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        self.old_owner = os.environ.get("RELATIONSHIP_MAP_OWNER_ID")
        os.environ["HERMES_HOME"] = self.temp.name
        os.environ["RELATIONSHIP_MAP_OWNER_ID"] = "test-user"

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        if self.old_owner is None:
            os.environ.pop("RELATIONSHIP_MAP_OWNER_ID", None)
        else:
            os.environ["RELATIONSHIP_MAP_OWNER_ID"] = self.old_owner
        self.temp.cleanup()

    def test_csv_import_dynamic_fields_and_snapshot(self):
        source = Path(self.temp.name) / "customers.csv"
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["姓名", "单位", "城市", "客户类型", "部门"])
            writer.writerow(["张总", "未来学校", "长沙", "学校资源", "A部门"])
        result = spreadsheet.import_spreadsheet(str(source), default_tags=["导入客户"])
        self.assertEqual(1, result["imported"])
        self.assertTrue(Path(result["source_snapshot"]).exists())
        contact = vault.meeting_context("张总")
        self.assertEqual("A部门", contact["attributes"]["部门"])
        self.assertIn("学校资源", contact["tags"])
        self.assertIn("导入客户", contact["tags"])

    def test_five_thousand_contacts_and_search(self):
        source = Path(self.temp.name) / "bulk.csv"
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["姓名", "部门", "客户类型"])
            for index in range(5000):
                writer.writerow([f"客户{index}", "A部门" if index % 2 else "B部门", "学校资源"])
        result = spreadsheet.import_spreadsheet(str(source))
        self.assertEqual(5000, result["imported"])
        self.assertEqual(1, len(vault.find_contacts("客户4999")))
        self.assertGreater(len(vault.find_contacts("A部门", limit=50)), 0)

    def test_empty_search_returns_current_map_overview(self):
        vault.record_interaction("王校长", "沟通研学试点", "2026-07-20T09:00:00+00:00")
        result = vault.find_contacts("")
        self.assertEqual(1, len(result))
        self.assertEqual("王校长", result[0]["name"])

    def test_update_preserves_assets(self):
        vault.record_interaction("李校长", "研学合作沟通", "2026-07-20T09:00:00+00:00")
        vault.update_contact_classification("李校长", add_tags=["重点客户"], attributes={"客户等级": "A"})
        record = vault.meeting_context("李校长")
        self.assertIn("重点客户", record["tags"])
        self.assertEqual("A", record["attributes"]["客户等级"])
        self.assertEqual(1, len(record["recent_interactions"]))


if __name__ == "__main__":
    unittest.main()
