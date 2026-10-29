"""No-network tests: no published category/budget may be recycled by a schedule."""
import base64
from datetime import date
import json
import unittest
from pathlib import Path

from automation.auto_campaign_v1 import choose_campaign, rotation_candidates, campaign_id
from automation.posting_history_v1 import (
    _historical_identity, fetch_successful_records, used_budgets_from_records,
    HistoryUnavailable, LEDGER_BRANCH,
)

POLICY = json.loads(Path("automation/campaigns.json").read_text("utf8"))
DAY = date(2026, 10, 29)


def site_stub(category, budget, brand):
    return {"generated_at": "unit-test", "ads": [{
        "ranking_source": "live_trustfolio_website_api",
        "products": [{"product_id": "test-" + str(i)} for i in range(5)],
    }]}


class PublishedBudgetHistoryTests(unittest.TestCase):
    def test_new_record_fields_trump_opaque_campaign_id(self):
        record = {"campaign_id": "tfauto-000000000000000000",
                  "category": "smart-phones", "budget_inr": 15000}
        self.assertEqual(("smart-phones", 15000),
                         _historical_identity(record, DAY, POLICY, "unused"))

    def test_legacy_id_can_be_resolved_without_original_manifest(self):
        candidate = rotation_candidates("budget", POLICY, DAY)[0]
        key = campaign_id(DAY, "budget", candidate["category"], candidate["budget"], "")
        self.assertEqual((candidate["category"], candidate["budget"]),
                         _historical_identity({"campaign_id":key,"mode":"budget"},
                                              DAY, POLICY, "meta-publication-ledger/2026-10-29/facebook-mode-budget.json"))

    def test_failed_or_reserved_entries_do_not_consume_a_budget(self):
        records = [
            ("meta-publication-ledger/2026-10-29/facebook-mode-budget.json",
             {"status":"reserved","category":"smart-phones","budget_inr":15000}),
            ("meta-publication-ledger/2026-10-29/instagram-mode-budget.json",
             {"status":"api_accepted_published","category":"smart-phones","budget_inr":16500}),
            ("meta-publication-ledger/2026-10-28/facebook-mode-comparison.json",
             {"status":"api_accepted_published","category":"smart-phones","budget_inr":16500}),
        ]
        result=used_budgets_from_records(records,POLICY,DAY)
        self.assertEqual([{"category":"smart-phones","budget":16500,
                           "dates":["2026-10-28","2026-10-29"]}],result["used"])

    def test_same_category_new_nonround_budget_is_chosen(self):
        initial=choose_campaign("budget",POLICY,day=DAY,fetcher=site_stub)
        excluded={(initial["category"],initial["budget"])}
        next_plan=choose_campaign("budget",POLICY,day=DAY,fetcher=site_stub,
                                  excluded_budget_pairs=excluded)
        self.assertEqual("eligible",next_plan["status"])
        self.assertEqual(initial["category"],next_plan["category"])
        self.assertNotEqual(initial["budget"],next_plan["budget"])

    def test_previous_mode_also_excludes_same_category_budget(self):
        original=choose_campaign("comparison",POLICY,day=DAY,fetcher=site_stub)
        next_plan=choose_campaign("comparison",POLICY,day=DAY,fetcher=site_stub,
                     excluded_budget_pairs={(original["category"],original["budget"])})
        self.assertNotEqual((original["category"],original["budget"]),
                            (next_plan["category"],next_plan["budget"]))

    def test_unavailable_budgets_fail_closed_not_repeat(self):
        candidates=rotation_candidates("budget",POLICY,DAY)
        excluded={(c["category"],c["budget"]) for c in candidates}
        called=[]
        def no_fetch(*args):
            called.append(args)
            return site_stub(*args)
        result=choose_campaign("budget",POLICY,day=DAY,fetcher=no_fetch,
                               excluded_budget_pairs=excluded)
        self.assertEqual("no_eligible_campaign",result["status"])
        self.assertEqual([],called)

    def test_tree_and_blobs_read_without_writes(self):
        path="meta-publication-ledger/2026-10-28/facebook-mode-budget.json"
        blob="a"*40
        record={"status":"api_accepted_published","category":"smart-phones",
                "budget_inr":15000,"campaign_id":"tfauto-0123456789abcdefab"}
        requests=[]
        def getter(route,token):
            requests.append(route)
            if route.startswith("git/trees/"):
                return {"truncated":False,"tree":[
                    {"path":path,"type":"blob","sha":blob},
                    {"path":"meta-publication-ledger/2026-09-01/facebook-mode-budget.json",
                     "type":"blob","sha":"b"*40}
                ]}
            if route.startswith("git/blobs/"):
                return {"encoding":"base64","content":base64.b64encode(json.dumps(record).encode()).decode()}
            raise AssertionError("Unexpected route")
        got=fetch_successful_records("test",DAY,getter=getter)
        self.assertEqual([(path,record)],got)
        self.assertTrue(requests[0].startswith("git/trees/"+LEDGER_BRANCH))
        self.assertEqual(2,len(requests))

    def test_truncated_history_is_blocked(self):
        with self.assertRaises(HistoryUnavailable):
            fetch_successful_records("test",DAY,
                  getter=lambda route,token:{"truncated":True,"tree":[]})


if __name__=="__main__":
    unittest.main()
