"""Six-category, three-mode TrustFolio batch runner regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ads_qa.render_social_batch_v1 import PLAN, MODES, website_candidate, verified_brand, run_batch


def mocked_source(slug,budget,brand=""):
    # Valid public-website structure: these are intentionally TEST-ONLY fixtures.
    name=brand or "SampleBrand"
    return {"generated_at":"2026-10-16T02:00:00Z","ads":[{
       "ranking_source":"live_trustfolio_website_api",
       "products":[{"rank":i,"product_id":f"{slug}-{name}-{i}",
                    "brand":name,"price_inr":min(1999,budget)}
                   for i in range(1,6)]}
    ]}


def fake_renderer(slug,budget,brand,folder,*,mode):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    ids=[f"{slug}-{brand or 'SampleBrand'}-{i}" for i in range(1,6)]
    report={
      "source":"live_trustfolio_website_api",
      "campaign_category":slug,"campaign_budget_inr":budget,
      "campaign_brand":brand or None,"campaign_mode":mode,
      "source_product_ids_by_rank":ids,"visual_product_ids_by_rank":ids,
      "renderer":"master_template_renderer_html_v4",
      "visual_geometry_errors":[],"dimensions":[1024,1536],
      "landing_url":"https://www.trustfolio.in/category/"+slug+"/products?budget="+str(budget),
      "automatic_publication":False,
    }
    (folder/"website-top5-render-qa.json").write_text(json.dumps(report))
    (folder/"trustfolio-live-website-top5-1024x1536.png").write_bytes(b"FAKE-DATA-FOR-MOCK-TESTS-ONLY")


def fake_packager(plan,report,image,dest):
    dest=Path(dest)
    dest.mkdir(parents=True,exist_ok=True)
    jpg=dest/(plan["campaign_id"]+".jpg")
    jpg.write_bytes(b"FAKE-JPEG-TEST-ONLY")
    return jpg,{"ranked_product_ids":report["visual_product_ids_by_rank"],
                "landing_url":report["landing_url"],
                "caption":"Test-only caption; NEVER PUBLISH"}


class BatchTests(unittest.TestCase):
    def test_exact_six_distinct_categories_and_three_modes(self):
        self.assertEqual(len(PLAN),6)
        self.assertEqual(MODES,("budget","brand_budget","comparison"))
        self.assertEqual(len(PLAN)*len(MODES),18)
        self.assertIn("smart-phones",PLAN["smartphones"]["slugs"])
        self.assertIn("smart-tvs",PLAN["televisions"]["slugs"])
        self.assertIn("headphones-earbuds",PLAN["earbuds"]["slugs"])

    def test_public_website_is_only_source_for_candidates(self):
        slug,budget,ad=website_candidate(["smartwatches"],[2000],reader=mocked_source)
        self.assertEqual(slug,"smartwatches")
        self.assertEqual(budget,2000)
        self.assertEqual(len(ad["products"]),5)
        self.assertTrue(all("product_id" in p for p in ad["products"]))

    def test_brand_is_requeried_on_real_site(self):
        calls=[]
        def reader(slug,budget,brand):
            calls.append((slug,budget,brand))
            return mocked_source(slug,budget,brand)
        brand,budget=verified_brand("smartwatches",[2000],
                                   mocked_source("smartwatches",2000)["ads"][0],
                                   ["Noise"],reader=reader)
        self.assertTrue(brand)
        self.assertIn(("smartwatches",2000,brand),calls)

    def test_missing_real_brand_matches_skip_not_fake(self):
        def fail_brand(slug,budget,brand):
            if brand:
                raise ValueError("No five products for brand")
            return mocked_source(slug,budget,brand)
        result=run_batch(
            Path(tempfile.mkdtemp())/"artifacts",day="2026-10-16",
            reader=fail_brand,renderer=fake_renderer,packager=fake_packager,
            public_dir=Path(tempfile.mkdtemp())/"published"
        )
        self.assertEqual(len(result["entries"]),18)
        self.assertEqual(sum(x["status"]=="qa_passed" for x in result["entries"]),12)
        self.assertEqual(sum(x["status"]=="skipped" for x in result["entries"]),6)
        self.assertTrue(all(x["mode"]=="brand_budget" for x in result["entries"]
                            if x["status"]=="skipped"))

    def test_exact_eighteen_valid_creatives_and_distinct_campaign_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_batch(
                Path(tmp)/"batch",day="2026-10-16",
                reader=mocked_source,renderer=fake_renderer,packager=fake_packager,
                public_dir=Path(tmp)/"media"
            )
            entries=result["entries"]
            self.assertEqual(len(entries),18)
            self.assertTrue(all(x["status"]=="qa_passed" for x in entries))
            self.assertEqual(len({x["campaign_id"] for x in entries}),18)
            self.assertTrue(all(x["public_basename"].startswith("tfauto-")
                                for x in entries))
            self.assertTrue(all(x["scheduling"]=="manual_metricool_connector_only"
                                for x in entries))
            self.assertTrue((Path(tmp)/"batch"/"batch_index.json").is_file())
            self.assertEqual(sum(x["mode"]=="comparison" for x in entries),6)
            self.assertEqual(sum(x["mode"]=="brand_budget" for x in entries),6)


if __name__=="__main__":
    unittest.main()
