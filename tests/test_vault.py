import os
import tempfile
import unittest
from pathlib import Path


class RelationshipVaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        self.old_owner = os.environ.get("RELATIONSHIP_MAP_OWNER_ID")
        os.environ["HERMES_HOME"] = self.tmp.name
        os.environ["RELATIONSHIP_MAP_OWNER_ID"] = "owner-a"
        from relationship_map_plugin.relationship_map_plugin import vault
        self.vault = vault

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        if self.old_owner is None:
            os.environ.pop("RELATIONSHIP_MAP_OWNER_ID", None)
        else:
            os.environ["RELATIONSHIP_MAP_OWNER_ID"] = self.old_owner
        self.tmp.cleanup()

    def test_persistent_contact_timeline_and_meeting_context(self):
        self.vault.record_interaction("张总", "后天在长沙讨论研学合作。", "2026-07-20T09:00:00+00:00", "拜访计划", "长沙未来学校", "长沙", "校长")
        self.vault.record_commitment("张总", "下周引荐两位学校负责人", "2026-07-27T09:00:00+00:00")
        self.vault.create_followup("张总", "长沙拜访前确认时间", "2026-07-22T09:00:00+00:00")
        context = self.vault.meeting_context("张总")
        self.assertIsNotNone(context)
        self.assertEqual("长沙未来学校", context["organization"])
        self.assertEqual(1, len(context["recent_interactions"]))
        self.assertEqual(1, len(context["open_commitments"]))
        self.assertTrue(Path(self.vault.database_path()).exists())

    def test_owner_scopes_do_not_mix(self):
        self.vault.record_interaction("李校长", "聊过研学", "2026-07-20T09:00:00+00:00")
        os.environ["RELATIONSHIP_MAP_OWNER_ID"] = "owner-b"
        self.assertEqual([], self.vault.find_contacts("李校长"))

    def test_backup_preserves_live_vault(self):
        self.vault.record_interaction("王总", "电话沟通", "2026-07-20T09:00:00+00:00")
        backup = self.vault.create_backup("test")
        self.assertTrue(backup.exists())
        self.assertEqual(1, len(self.vault.find_contacts("王总")))


if __name__ == "__main__":
    unittest.main()
