"""Offline tests of safe stale-rank rebuild and fallback. No Meta/VPS writes."""
import copy
import unittest
from unittest.mock import Mock,patch
from datetime import datetime,timezone

from automation import render_with_brand_fallback_v1 as render
from automation import rebuild_stale_meta_campaign_v1 as rebuild
from automation.verify_price_before_meta_publish_v1 import PriceAuditBlocked


def plan():
    return {"status":"eligible","mode":"budget","slot":0,
            "date_ist":"2026-10-27","category":"smartwatches",
            "budget":3000,"brand":"","account":"trustfolio3",
            "campaign_id":"tfauto-"+"a"*18}

def report_for(item):
    ids=["sku-"+str(i) for i in range(1,6)]
    return {
        "source":"live_trustfolio_website_api",
        "campaign_category":item["category"],
        "campaign_budget_inr":item["budget"],
        "campaign_brand":item["brand"],
        "campaign_mode":item["mode"],
        "source_product_ids_by_rank":ids,
        "visual_product_ids_by_rank":ids,
        "displayed_prices_by_rank":[2100,2200,2300,2400,2500],
        "price_sources_by_rank":["website_catalog"]*5,
        "visual_geometry_errors":[],
        "dimensions":[1024,1536],
        "renderer":"master_template_renderer_html_v4",
        "landing_url":"https://www.trustfolio.in/category/"+item["category"]+
                      "/products?budget="+str(item["budget"]),
        "automatic_publication":False,
        "source_observed_at":datetime.now(timezone.utc).isoformat()
    }


class RecoveryTests(unittest.TestCase):
    def test_select_genuine_alternative_never_reuses_failed_brand_and_budget(self):
        item=plan()
        excluded={(item["category"],item["budget"],item["brand"])}
        # Reuse existing true policy; mocked website is sole source for Top-5.
        from automation.test_20_category_rotation import live_mock
        candidate=render.select_alternative(item,excluded=excluded,fetcher=live_mock)
        self.assertNotIn((candidate["category"],candidate["budget"],candidate["brand"]),excluded)
        self.assertEqual(candidate["mode"],item["mode"])
        self.assertEqual(candidate["date_ist"],item["date_ist"])

    def test_render_retries_a_transient_brand_failure_using_next_candidate(self):
        item=plan()
        alternative=dict(item,category="headphones-earbuds",budget=5000,
                         campaign_id="tfauto-"+"b"*18)
        called=[]
        def renderer(p,**kwargs):
            called.append(p["category"])
            if len(called)==1:
                raise ValueError("Website returned brand-fallback products")
            return report_for(p)
        select=Mock(return_value=alternative)
        result,_=render.render_with_fallback(
            item,run_key="123",folder="campaign",host="200.234.47.87",
            user="scraperuser",max_renders=2,renderer=renderer,selector=select)
        self.assertEqual(called,["smartwatches","headphones-earbuds"])
        self.assertEqual(result["category"],"headphones-earbuds")
        self.assertIn(("smartwatches",3000,""),select.call_args.kwargs["excluded"])

    def test_rebuild_mints_a_new_id_when_image_content_changes(self):
        item=plan()
        old=report_for(item)
        new=copy.deepcopy(old)
        new["displayed_prices_by_rank"][0]=2150
        self.assertNotEqual(rebuild.refreshed_campaign_id(item,old),
                            rebuild.refreshed_campaign_id(item,new))
        self.assertEqual(rebuild.refreshed_campaign_id(item,new),
                         rebuild.refreshed_campaign_id(item,new))
        self.assertEqual(len(rebuild.refreshed_campaign_id(item,new)),25)

    def test_rank_drift_causes_another_fresh_render_not_stale_publish(self):
        item=plan()
        calls=[]
        def renderer(p,**kwargs):
            calls.append("render")
            return p,report_for(p)
        def stage(p,r,**kwargs):
            calls.append("stage")
            return p,{"campaign_id":p["campaign_id"]},"https://media.trustfolio.in/x.jpg"
        n=[0]
        def audit(p,r):
            n[0]+=1
            calls.append("audit")
            if n[0]==1:
                raise PriceAuditBlocked("Website product ranking changed")
        result,_,_=rebuild.rebuild_until_stable(item,folder="campaign",run_key="1",
                           host="200.234.47.87",user="scraperuser",
                           render=renderer,stage=stage,audit=audit,max_rebuilds=2)
        self.assertEqual(result["category"],item["category"])
        self.assertEqual(calls,["render","stage","audit","render","stage","audit"])

    def test_persistent_staleness_prevents_publication(self):
        item=plan()
        with self.assertRaisesRegex(PriceAuditBlocked,"ranking changed"):
            rebuild.rebuild_until_stable(item,folder="campaign",run_key="1",
                           host="200.234.47.87",user="scraperuser",
                           render=lambda p,**k:(p,report_for(p)),
                           stage=lambda p,r,**k:(p,{},"https://media.trustfolio.in/x.jpg"),
                           audit=lambda p,r:(_ for _ in ()).throw(
                                  PriceAuditBlocked("Website product ranking changed")),
                           max_rebuilds=2)

    def test_brand_fallback_prepublication_tries_different_genuine_campaign(self):
        item=dict(plan(),mode="brand_budget",brand="Noise")
        alternative=dict(item,category="headphones-earbuds",budget=4000,
                         brand="boAt",campaign_id="tfauto-"+"b"*18)
        calls=[]
        def stage(p,r,**kwargs):
            return p,{"campaign_id":p["campaign_id"]},"https://media.trustfolio.in/x.jpg"
        def audit(p,r):
            calls.append((p["category"],p["brand"]))
            if p["brand"]=="Noise":
                raise ValueError("Website returned brand-fallback products; cannot claim a brand-only ad")
        select=Mock(return_value=alternative)
        selected,_,_=rebuild.rebuild_until_stable(
            item,folder="campaign",run_key="1",host="200.234.47.87",
            user="scraperuser",max_rebuilds=3,
            render=lambda p,**k:(p,report_for(p)),
            stage=stage,audit=audit,alternative_selector=select)
        self.assertEqual(selected["brand"],"boAt")
        self.assertEqual(calls,[("smartwatches","Noise"),("headphones-earbuds","boAt")])
        self.assertIn(("smartwatches",3000,"Noise"),select.call_args.kwargs["excluded"])

    def test_repeated_price_drift_switches_budget_and_category_before_post(self):
        item=plan()
        alternative=dict(item,category="headphones-earbuds",budget=5000,
                         campaign_id="tfauto-"+"b"*18)
        seen=[]
        def audit(p,r):
            seen.append((p["category"],p["budget"]))
            if p["category"]=="smartwatches":
                raise PriceAuditBlocked("Website product ranking changed after poster was rendered")
        select=Mock(return_value=alternative)
        selected,_,_=rebuild.rebuild_until_stable(
            item,folder="campaign",run_key="1",host="200.234.47.87",
            user="scraperuser",max_rebuilds=3,
            render=lambda p,**k:(p,report_for(p)),
            stage=lambda p,r,**k:(p,{},"https://media.trustfolio.in/x.jpg"),
            audit=audit,alternative_selector=select)
        self.assertEqual(seen,[("smartwatches",3000),("smartwatches",3000),
                               ("headphones-earbuds",5000)])
        self.assertEqual(selected["category"],"headphones-earbuds")
        self.assertEqual(select.call_count,1)

    def test_unverified_or_repeated_alternative_never_gets_published(self):
        item=dict(plan(),mode="brand_budget",brand="Noise")
        failing=lambda p,r: (_ for _ in ()).throw(ValueError("Brand fallback"))
        for invalid in (
            dict(item),dict(item,status="no_eligible_campaign"),
        ):
            with self.subTest(invalid=invalid["status"]):
                with self.assertRaises(PriceAuditBlocked):
                    rebuild.rebuild_until_stable(
                        item,folder="campaign",run_key="1",host="200.234.47.87",
                        user="scraperuser",max_rebuilds=2,
                        render=lambda p,**k:(p,report_for(p)),
                        stage=lambda p,r,**k:(p,{},"https://media.trustfolio.in/x.jpg"),
                        audit=failing,alternative_selector=lambda p,**k:invalid)

    def test_no_unbounded_rebuilds_and_remote_target_is_pinned(self):
        with self.assertRaisesRegex(ValueError,"Unbounded"):
            rebuild.rebuild_until_stable(plan(),folder="campaign",run_key="2",
                           host="200.234.47.87",user="scraperuser",max_rebuilds=30)
        with self.assertRaisesRegex(ValueError,"Unknown deployment"):
            render.attempt_render(plan(),run_key="2",folder="campaign",
                                  host="untrusted.host",user="scraperuser")


if __name__=="__main__":
    unittest.main()
