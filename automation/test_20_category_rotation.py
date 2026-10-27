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

    def test_non_round_budget_within_configured_minimum_and_maximum(self):
        day=date(2026,10,27)
        candidates=rotation_candidates("budget",POLICY,day)
        first_category=candidates[0]["category"]
        bounds=next(x["budgets"] for x in POLICY["rotation"]["categories"]
                    if x["site_slug"]==first_category)
        same=[x["budget"] for x in candidates if x["category"]==first_category]
        self.assertTrue(set(bounds).issubset(same))
        self.assertTrue(any(min(bounds)<v<max(bounds) and v not in bounds for v in same))
        self.assertTrue(all(min(bounds)<=v<=max(bounds) for v in same))

    def test_third_budget_fallback_before_moving_to_new_category(self):
        day=date(2026,10,27)
        amounts=rotation_candidates("comparison",POLICY,day)
        first=amounts[0]["category"]
        candidate_amounts=[x["budget"] for x in amounts if x["category"]==first]
        self.assertGreaterEqual(len(candidate_amounts),3)
        wanted=candidate_amounts[2]
        calls=[]
        def site(category,budget,brand):
            calls.append((category,budget))
            if category==first and budget==wanted:
                return live_mock(category,budget,brand)
            raise ValueError("No five real products for this candidate")
        result=choose_campaign("comparison",POLICY,day=day,fetcher=site)
        self.assertEqual(result["status"],"eligible")
        self.assertEqual(result["budget"],wanted)
        self.assertEqual(result["category"],first)
        self.assertEqual(calls[:3],[(first,x) for x in candidate_amounts[:3]])

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
        self.assertLessEqual(len(calls),POLICY['rotation']['max_website_attempts_per_run'])

    def test_campaign_type_must_match_rendered_visual(self):
        plan={"status":"eligible","mode":"brand_budget","category":"smartwatches",
              "brand":"Noise","budget":2000}
        report={"source":"live_trustfolio_website_api","campaign_category":"smartwatches",
                "campaign_budget_inr":2000,"campaign_brand":"Noise",
                "campaign_mode":"budget"}
        with self.assertRaisesRegex(ValueError,"ad type"):
            check_report(plan,report)

    def test_six_distinct_mode_slot_primary_categories(self):
        for days in range(85):
            day=date(2026,10,19)+timedelta(days=days)
            picks=[rotation_candidates(mode,POLICY,day,slot=slot)[0]
                   for mode in ("budget","brand_budget","comparison") for slot in (0,1)]
            self.assertEqual(len(picks),6)
            self.assertEqual(len({p["category"] for p in picks}),6,day)
            self.assertTrue(all(POLICY["rotation"]["categories"][
                next(i for i,c in enumerate(POLICY["rotation"]["categories"])
                     if c["site_slug"]==p["category"])]["budgets"].count(p["budget"])==1
                for p in picks))
            self.assertEqual(len({p["category"] for p in picks}),6)

    def test_second_slot_uses_distinct_category(self):
        day=date(2026,10,26)
        for mode in ("budget","brand_budget","comparison"):
            first=rotation_candidates(mode,POLICY,day,slot=0)[0]
            second=rotation_candidates(mode,POLICY,day,slot=1)[0]
            self.assertNotEqual(first["category"],second["category"])
            self.assertEqual(bool(first["brand"]),mode=="brand_budget")
            self.assertEqual(bool(second["brand"]),mode=="brand_budget")
            selected=choose_campaign(mode,POLICY,day=day,slot=1,fetcher=live_mock)
            self.assertEqual(selected["status"],"eligible")
            self.assertEqual(selected["category"],second["category"])
            self.assertEqual(selected["slot"],1)

    def test_six_daily_cron_slots_and_live_price_guard(self):
        workflow=(ROOT/".github/workflows/auto-instagram-campaigns.yml").read_text("utf8")
        self.assertIn("TF_META_MAX_POSTS_PER_DAY_PER_NETWORK: '3'",workflow)
        self.assertIn("github.event_name == 'schedule'",workflow)
        self.assertIn("python automation/verify_price_before_meta_publish_v1.py",workflow)
        self.assertIn("2026-10-21",workflow)
        self.assertIn("TF_AUTO_POST_ENABLED",workflow)
        cron=['0 3 * * *','0 5 * * *','0 8 * * *',
              '30 10 * * *','30 13 * * *','30 15 * * *']
        cron+=['0 14 * * *','0 15 * * *','45 16 * * *']
        for item in cron:
            self.assertIn("cron: '"+item+"'",workflow)
            self.assertIn("github.event.schedule == '"+item+"'",workflow)
        self.assertIn("'--slot',str(slot)",workflow)
        # Each mode's second cron is recovery, never an extra published mode.
        self.assertIn("'0 5 * * *':('budget',0)",workflow)
        self.assertIn("'30 10 * * *':('brand_budget',0)",workflow)
        self.assertIn("'30 15 * * *':('comparison',0)",workflow)
        self.assertIn("mode=plan['mode']",workflow)
        self.assertEqual(POLICY["rotation"]["cadence_ist"],{
            "budget":["08:30","10:30 recovery"],
            "brand_budget":["13:30","16:00 recovery"],
            "comparison":["19:00","21:00 recovery"]})


if __name__=="__main__":
    unittest.main()
