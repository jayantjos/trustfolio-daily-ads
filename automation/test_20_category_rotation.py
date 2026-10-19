"""Twenty-category scheduled rotation, budget ladders and cron-mode regression tests."""
import json
from datetime import date,timedelta
from pathlib import Path
import unittest

from automation.auto_campaign_v1 import rotation_candidates,choose_campaign,check_report
from ads_qa.category_copy_v1 import _profile_copy

ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/"automation/campaigns.json").read_text("utf8"))


def live_mock(category,budget,brand):
    """Test-only website Top-5 fixture: never used for actual ad generation."""
    return {"generated_at":"2026-10-17T03:00:00Z","ads":[{
        "ranking_source":"live_trustfolio_website_api",
        "products":[{"product_id":f"{category}-{budget}-{brand}-{i}","rank":i}
                    for i in range(1,6)]
    }]}


class TwentyCategoryRotationTests(unittest.TestCase):
    def test_exact_canonical_twenty_profile_categories(self):
        cfg=POLICY["rotation"]["categories"]
        self.assertEqual(len(cfg),20)
        self.assertEqual({p["key"] for p in cfg},set(_profile_copy()))
        for p in cfg:
            self.assertGreaterEqual(len(p["budgets"]),3)
            self.assertEqual(len(set(p["budgets"])),len(p["budgets"]))
            self.assertTrue(all(isinstance(b,int) and b>500 for b in p["budgets"]))
            self.assertTrue(p["site_slug"].replace("-","").isalnum())
            self.assertGreaterEqual(len(p["brands"]),2)

    def test_all_twenty_categories_covered_across_month_boundary(self):
        # October 31 and November 1 are both odd dates. A 23-day window
        # ensures ten appearances from each date-parity cohort.
        start=date(2026,10,17)
        all_keys={x["site_slug"] for x in POLICY["rotation"]["categories"]}
        for mode in ("budget","brand_budget","comparison"):
            selected=[]
            for n in range(23):
                target=start+timedelta(days=n)
                candidate=rotation_candidates(mode,POLICY,target)[0]
                self.assertEqual(bool(candidate["brand"]),mode=="brand_budget")
                selected.append(candidate["category"])
            self.assertEqual(set(selected),all_keys,mode)

    def test_same_day_categories_differ_across_three_campaign_modes(self):
        for day in (date(2026,10,17),date(2026,10,18),date(2026,11,1)):
            keys=[rotation_candidates(mode,POLICY,day)[0]["category"] for mode in
                  ("budget","brand_budget","comparison")]
            self.assertEqual(len(set(keys)),3)

    def test_budget_tier_rotates_each_category_cycle(self):
        start=date(2026,10,17)
        for mode in ("budget","brand_budget","comparison"):
            first=rotation_candidates(mode,POLICY,start)[0]
            revisits=[rotation_candidates(mode,POLICY,start+timedelta(days=n))[0]
                      for n in range(1,26)]
            same=next((x for x in revisits if x["category"]==first["category"]),None)
            self.assertIsNotNone(same,mode)
            self.assertNotEqual(first["budget"],same["budget"],mode)

    def test_calendar_odd_even_category_and_budget_parity(self):
        categories=POLICY["rotation"]["categories"]
        by_slug={x["site_slug"]:i for i,x in enumerate(categories)}
        start=date(2026,10,19)
        for mode in ("budget","brand_budget","comparison"):
            observed={category["site_slug"]:set() for category in categories}
            for offset in range(85):
                target=start+timedelta(days=offset)
                expected_index_parity=0 if target.day%2 else 1
                candidates=rotation_candidates(mode,POLICY,target)
                # Even when the first choice fails, no retry can cross
                # into the opposite category cohort.
                self.assertTrue(candidates)
                for choice in candidates:
                    i=by_slug[choice["category"]]
                    self.assertEqual(i%2,expected_index_parity,(mode,target,choice))
                primary=candidates[0]
                observed[primary["category"]].add(primary["budget"])
            # Every category visits all three price tiers in later cycles.
            for category in categories:
                self.assertEqual(observed[category["site_slug"]],set(category["budgets"]),
                                 (mode,category["site_slug"]))

    def test_fallback_category_preserves_odd_even_parity(self):
        by_slug={x["site_slug"]:i for i,x in
                 enumerate(POLICY["rotation"]["categories"])}
        for day in (date(2026,10,31),date(2026,11,1),date(2026,11,2)):
            for mode in ("budget","brand_budget","comparison"):
                first=rotation_candidates(mode,POLICY,day)[0]["category"]
                def site(category,budget,brand):
                    if category==first:
                        raise ValueError("Current category does not have five eligible items")
                    return live_mock(category,budget,brand)
                selected=choose_campaign(mode,POLICY,day=day,fetcher=site)
                self.assertEqual(selected["status"],"eligible")
                self.assertNotEqual(selected["category"],first)
                self.assertEqual(by_slug[selected["category"]]%2,0 if day.day%2 else 1)

    def test_ineligible_current_budget_falls_back_safely(self):
        today=date(2026,10,17)
        first=rotation_candidates("budget",POLICY,today)[0]
        calls=[]
        def f(category,budget,brand):
            calls.append((category,budget,brand))
            if category==first["category"]:
                raise ValueError("Website returned fewer than five real products")
            return live_mock(category,budget,brand)
        plan=choose_campaign("budget",POLICY,day=today,fetcher=f)
        self.assertEqual(plan["status"],"eligible")
        self.assertNotEqual(plan["category"],first["category"])
        self.assertFalse(plan["auto_publish"])
        self.assertTrue(all(brand=="" for _,_,brand in calls))

    def test_missing_all_verified_brands_skips_without_faking(self):
        calls=[]
        def f(category,budget,brand):
            calls.append((category,budget,brand))
            raise ValueError("No five matching-brand products on live site")
        plan=choose_campaign("brand_budget",POLICY,day=date(2026,10,17),fetcher=f)
        self.assertEqual(plan["status"],"no_eligible_campaign")
        self.assertFalse(plan["auto_publish"])
        self.assertGreater(len(plan["attempts"]),0)
        self.assertTrue(all(b for _,_,b in calls))
        self.assertLessEqual(len(calls),20)

    def test_campaign_type_must_match_rendered_visual(self):
        plan={"status":"eligible","mode":"brand_budget","category":"smartwatches",
              "brand":"Noise","budget":2000}
        report={"source":"live_trustfolio_website_api","campaign_category":"smartwatches",
                "campaign_budget_inr":2000,"campaign_brand":"Noise",
                "campaign_mode":"budget"}
        with self.assertRaisesRegex(ValueError,"ad type"):
            check_report(plan,report)

    def test_three_verified_modes_each_day_have_distinct_cron_slots(self):
        workflow=(ROOT/".github/workflows/auto-instagram-campaigns.yml").read_text("utf8")
        self.assertIn("TF_META_MAX_POSTS_PER_DAY_PER_NETWORK: '3'",workflow)
        self.assertIn("github.event_name == 'schedule'",workflow)
        # The brand-budget middle slot must be allowed to publish from
        # Oct 26 if five matching same-brand ranked products exist.
        self.assertIn("github.event.schedule == '0 8 * * *'",workflow)
        self.assertIn("github.event.schedule == '0 3 * * *'",workflow)
        self.assertIn("github.event.schedule == '30 13 * * *'",workflow)
        self.assertIn("2026-10-26",workflow)
        self.assertIn("TF_AUTO_POST_ENABLED",workflow)
        self.assertEqual(tuple(POLICY["rotation"]["cadence_ist"].values()),
                         ("08:30","13:30","19:00"))

    def test_github_cron_forwards_mode_to_ads_vps_renderer(self):
        source=(ROOT/".github/workflows/auto-instagram-campaigns.yml").read_text("utf8")
        self.assertIn("mode=plan['mode']",source)
        self.assertIn("TF_AUTO_POST_ENABLED",source)
        self.assertIn("cron: '0 3 * * *'",source)
        self.assertIn("cron: '0 8 * * *'",source)
        self.assertIn("cron: '30 13 * * *'",source)


if __name__=="__main__":
    unittest.main()
