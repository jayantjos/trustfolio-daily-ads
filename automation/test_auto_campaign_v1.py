"""Unit tests for scheduled campaign decisions, ranking gates and 4:5 output."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from automation.auto_campaign_v1 import (
    campaign_id, choose_campaign, check_report, caption_for, package_assets,
)


def fake_site(category, budget, brand):
    if brand == "Unknown":
        raise ValueError("No five products")
    return {"generated_at":"2026-10-16T01:00:00Z","ads":[{
        "ranking_source":"live_trustfolio_website_api",
        "products":[{"product_id":"id"+str(i),"rank":i} for i in range(1,6)],
    }]}


def sample_plan():
    return {
        "status":"eligible","mode":"budget","date_ist":"2026-10-16",
        "category":"smartwatches","budget":2000,"brand":"",
        "campaign_id":campaign_id("2026-10-16","budget","smartwatches",2000,""),
        "source_product_ids_by_rank":["id"+str(i) for i in range(1,6)],
    }


def sample_report():
    return {
        "source":"live_trustfolio_website_api",
        "campaign_category":"smartwatches",
        "campaign_budget_inr":2000,"campaign_brand":None,
        "source_product_ids_by_rank":["id"+str(i) for i in range(1,6)],
        "visual_product_ids_by_rank":["id"+str(i) for i in range(1,6)],
        "visual_geometry_errors":[],"dimensions":[1024,1536],
        "renderer":"master_template_renderer_html_v4",
        "landing_url":"https://www.trustfolio.in/category/smartwatches/products?budget=2000",
        "automatic_publication":False,
        "source_observed_at":"2026-10-16T01:00:00Z",
    }


class AutoCampaignTests(unittest.TestCase):
    def test_stable_campaign_identity_independent_of_run_number(self):
        x=sample_plan()["campaign_id"]
        self.assertEqual(x,campaign_id("2026-10-16","budget","smartwatches",2000,""))
        self.assertNotEqual(x,campaign_id("2026-10-17","budget","smartwatches",2000,""))

    def test_budget_campaign_from_real_site_only(self):
        policy={"campaigns":{"budget":[{"category":"smartwatches","budget":2000}]}}
        x=choose_campaign("budget",policy,day=date(2026,10,16),fetcher=fake_site)
        self.assertEqual(x["status"],"eligible")
        self.assertEqual(x["source_product_ids_by_rank"],["id1","id2","id3","id4","id5"])
        self.assertFalse(x["auto_publish"])

    def test_invalid_slot_fails_closed(self):
        from automation.auto_campaign_v1 import rotation_candidates
        policy=json.loads((Path(__file__).resolve().parents[1]/
                           "automation/campaigns.json").read_text("utf8"))
        with self.assertRaisesRegex(ValueError,"slot"):
            rotation_candidates("budget",policy,date(2026,10,26),slot=2)
        with self.assertRaisesRegex(ValueError,"slot"):
            rotation_candidates("comparison",policy,date(2026,10,26),slot=-1)

    def test_missing_5_brand_products_blocks_post(self):
        policy={"campaigns":{"brand_budget":[{"category":"smartwatches","budget":2000,"brand":"Unknown"}]}}
        x=choose_campaign("brand_budget",policy,day=date(2026,10,16),fetcher=fake_site)
        self.assertEqual(x["status"],"no_eligible_campaign")
        self.assertFalse(x["auto_publish"])

    def test_missing_or_mismatched_filters_rejected(self):
        p=sample_plan()
        r=sample_report()
        self.assertEqual(len(check_report(p,r)),5)
        r["landing_url"]="https://www.trustfolio.in/category/smartwatches/products?budget=5000"
        with self.assertRaisesRegex(ValueError,"filters"):
            check_report(p,r)
        r=sample_report()
        r["visual_product_ids_by_rank"][1]="different"
        with self.assertRaisesRegex(ValueError,"rankings differ"):
            check_report(p,r)
        r=sample_report()
        r["visual_geometry_errors"]=["overlap"]
        with self.assertRaisesRegex(ValueError,"geometry"):
            check_report(p,r)

    def test_comparison_is_different_products_no_invented_savings(self):
        p=sample_plan()
        p["mode"]="comparison"
        c=caption_for(p,sample_report()["landing_url"])
        self.assertIn("Compare Top 5",c)
        self.assertNotIn("Save ₹",c)
        self.assertIn("budget=2000",c)

    def test_every_caption_contains_live_link_hub_and_play_store(self):
        p=sample_plan()
        caption=caption_for(p,sample_report()["landing_url"])
        self.assertIn("https://media.trustfolio.in/trustfolio-links/index.html?",caption)
        self.assertIn("category=smartwatches",caption)
        self.assertIn("budget=2000",caption)
        self.assertIn("https://play.google.com/store/apps/details?id=com.trustfolio.app",caption)
        self.assertIn("links tappable nahi",caption)
        p["mode"]="brand_budget"
        p["brand"]="boAt Audio"
        caption=caption_for(p,sample_report()["landing_url"]+"&brand=boAt+Audio")
        self.assertIn("brand=boAt+Audio",caption)

    def test_brand_ad_requires_exact_brand_link(self):
        p=sample_plan()
        p["mode"]="brand_budget"
        p["brand"]="boAt Audio"
        r=sample_report()
        r["campaign_brand"]="boAt Audio"
        r["landing_url"]+="&brand=boAt+Audio"
        self.assertEqual(len(check_report(p,r)),5)
        r["landing_url"]=sample_report()["landing_url"]
        with self.assertRaisesRegex(ValueError,"filters"):
            check_report(p,r)

    def test_4x5_image_preserves_all_original_pixels(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow unavailable")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            original=root/"server.png"
            Image.new("RGB",(1024,1536),(22,140,221)).save(original)
            pic, manifest=package_assets(sample_plan(),sample_report(),original,root/"out")
            with Image.open(pic) as im:
                self.assertEqual(im.size,(1080,1350))
                self.assertGreater(im.getpixel((540,650))[2],160)
            self.assertEqual(manifest["status"],"ready_for_publishing_gate")
            self.assertIn("budget=2000",manifest["caption"])
            self.assertTrue((root/"out"/"post.json").exists())


if __name__=="__main__":
    unittest.main()
