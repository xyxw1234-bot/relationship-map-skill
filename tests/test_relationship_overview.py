import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from relationship_map_plugin.relationship_map_plugin import vault


class RelationshipMapOverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        self.old_owner = os.environ.get("RELATIONSHIP_MAP_OWNER_ID")
        os.environ["HERMES_HOME"] = self.temp.name
        os.environ["RELATIONSHIP_MAP_OWNER_ID"] = "overview-user"
        self.now = datetime.now(UTC).replace(microsecond=0)

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

    def occurred(self, days_ago):
        return (self.now - timedelta(days=days_ago)).isoformat()

    def test_mobile_overview_has_total_bounded_pages_and_no_full_detail(self):
        for name in ("甲", "乙", "丙"):
            vault.record_interaction(name, "已沟通", self.occurred(1))
        page_one = vault.browse_contacts(limit=2, sort_by="name")
        page_two = vault.browse_contacts(limit=2, offset=page_one["next_offset"], sort_by="name")
        self.assertEqual(3, page_one["total"])
        self.assertEqual(2, len(page_one["contacts"]))
        self.assertTrue(page_one["has_more"])
        self.assertEqual(2, page_one["next_offset"])
        self.assertEqual(1, len(page_two["contacts"]))
        self.assertFalse(page_two["has_more"])
        self.assertNotIn("notes", page_one["contacts"][0])
        self.assertNotIn("attributes", page_one["contacts"][0])

    def test_frequency_sort_is_stable_when_counts_are_equal(self):
        vault.record_interaction("甲", "沟通", self.occurred(2))
        vault.record_interaction("乙", "沟通", self.occurred(1))
        vault.record_interaction("丙", "沟通", self.occurred(1))
        vault.record_interaction("丙", "再次沟通", self.occurred(0))
        result = vault.browse_contacts(sort_by="interaction_frequency")
        self.assertEqual("丙", result["contacts"][0]["name"])
        self.assertEqual(2, result["contacts"][0]["interaction_count"])
        self.assertEqual(["乙", "甲"], [item["name"] for item in result["contacts"][1:]])

    def test_heat_and_followup_priority_use_saved_data(self):
        vault.record_interaction("高频近期", "沟通", self.occurred(1))
        vault.record_interaction("高频近期", "再次沟通", self.occurred(2))
        vault.record_interaction("久未联系", "沟通", self.occurred(180))
        vault.create_followup("高频近期", "月底联系", "2030-01-31T09:00:00+00:00")
        vault.create_followup("久未联系", "尽快联系", "2030-01-01T09:00:00+00:00")
        heat = vault.browse_contacts(sort_by="relationship_heat")
        followups = vault.browse_contacts(sort_by="followup_due")
        self.assertEqual("高频近期", heat["contacts"][0]["name"])
        self.assertEqual("热", heat["contacts"][0]["heat"]["label"])
        self.assertEqual("冷", heat["contacts"][1]["heat"]["label"])
        self.assertEqual("久未联系", followups["contacts"][0]["name"])
        self.assertEqual("尽快联系", followups["contacts"][0]["next_followup"]["title"])


if __name__ == "__main__":
    unittest.main()
