"""Unit checks for TrustFolio deep-link and rank contract (stdlib only)."""
import unittest
from urllib.parse import urlsplit, parse_qs
from campaign_link_contract_v1 import campaign_link, check_ranked_site_snapshot
from ad_link_manifest_v1 import build_manifest
from social_post_generator_v1 import build_copy


def config():
    return {
        "links": {
            "category_url_template": "https://www.trustfolio.in/category/{route_slug}/",
            "results_url_template": "https://www.trustfolio.in/category/{route_slug}/products",
            "route_slug_overrides": {"speakers": "bluetooth-speakers"},
            "tracking": {"parameters": {"utm_source": "social", "utm_campaign": "daily"}},
            "budget_query_parameter": {"enabled": False, "parameter": "budget"},
        },
        "brand": {
            "name": "TrustFolio",
            "tagline": "Compare Save Shop Smart",
            "website_url": "https://www.trustfolio.in/",
            "play_store_url": "https://play.google.com/store/apps/details?id=com.trustfolio.app",
        },
        "creative_defaults": {},
    }


def ad(ad_type="budget_recommendation", brand=""):
    return {
        "ad_type": ad_type,
        "category": "smartwatches",
        "budget_inr": 2000,
        "brand": brand,
        "headline": "Best Smartwatches Under 2000",
        "products": [
            {"rank": i, "product_id": f"sku{i}", "brand": brand or "Example",
             "title": f"Watch {i}", "price_inr": 500 + i * 100}
            for i in range(1, 6)
        ],
    }


class CampaignContractTests(unittest.TestCase):
    def test_disabled_budget_never_claimed_prefilled(self):
        link = campaign_link(ad(), config(), "tf-one")
        q = parse_qs(urlsplit(link["landing_url"]).query)
        self.assertNotIn("budget", q)
        self.assertEqual(q["utm_content"], ["tf-one"])
        self.assertEqual(q["ad_type"], ["budget_recommendation"])
        self.assertFalse(link["prefill_ready"])
        self.assertEqual(link["unverified_prefill_fields"], ["budget"])
        self.assertEqual(link["site_ranking_status"], "unverified")

    def test_verified_budget_and_brand_query_are_encoded(self):
        cfg = config()
        cfg["links"]["budget_query_parameter"] = {
            "enabled": True, "frontend_verified": True, "parameter": "budget"}
        cfg["links"]["brand_query_parameter"] = {
            "enabled": True, "frontend_verified": True, "parameter": "brand"}
        link = campaign_link(ad("brand_recommendation", "boAt Audio"), cfg, "tf-two")
        q = parse_qs(urlsplit(link["landing_url"]).query)
        self.assertEqual(q["budget"], ["2000"])
        self.assertEqual(q["brand"], ["boAt Audio"])
        self.assertTrue(link["prefill_ready"])
        self.assertEqual(urlsplit(link["landing_url"]).path, "/category/smartwatches/products")
        self.assertEqual(link["click_destination"], "filtered_products")

    def test_enabled_without_frontend_confirmation_stays_off(self):
        cfg = config()
        cfg["links"]["budget_query_parameter"]["enabled"] = True
        link = campaign_link(ad(), cfg, "tf-three")
        self.assertFalse(link["prefill_ready"])
        self.assertNotIn("budget", parse_qs(urlsplit(link["landing_url"]).query))

    def test_category_input_page_for_unverified_budget(self):
        link = campaign_link(ad(), config(), "tf-input")
        self.assertEqual(urlsplit(link["landing_url"]).path, "/category/smartwatches/")
        self.assertEqual(link["click_destination"], "category_landing")

    def test_offsite_results_path_rejected(self):
        cfg = config()
        cfg["results_url_template"] = "https://untrusted.example/category/{route_slug}/products"
        cfg["budget_query_parameter"] = {"enabled": True, "frontend_verified": True}
        with self.assertRaises(ValueError):
            campaign_link(ad(), cfg, "tf-bad")

    def test_route_override(self):
        candidate = ad()
        candidate["category"] = "speakers"
        link = campaign_link(candidate, config(), "tf-speakers")
        self.assertIn("/category/bluetooth-speakers/", link["landing_url"])

    def test_disallow_offsite_and_bad_budget(self):
        cfg = config()
        cfg["links"]["category_url_template"] = "https://evil.example/{route_slug}"
        with self.assertRaises(ValueError):
            campaign_link(ad(), cfg, "tf-one")
        candidate = ad()
        candidate["budget_inr"] = -10
        with self.assertRaises(ValueError):
            campaign_link(candidate, config(), "tf-one")

    def test_manifest_preserves_product_identity_and_warns_on_prefill(self):
        manifest = build_manifest({"ads": [ad()]}, config())
        item = manifest["ads"][0]
        self.assertEqual(item["requested_filters"]["budget_inr"], 2000)
        self.assertEqual(item["site_ranking_status"], "unverified")
        self.assertEqual(item["products"][0]["product_id"], "sku1")
        self.assertEqual(item["products"][0]["ad_rank"], 1)

    def test_instagram_caption_carries_campaign_url(self):
        item = build_manifest({"ads": [ad()]}, config())["ads"][0]
        caption = build_copy(item)["instagram"]["caption"]
        self.assertIn(item["landing_url"], caption)
        self.assertIn("utm_content=", caption)

    def test_parity_requires_actual_snapshot(self):
        self.assertIn("missing", check_ranked_site_snapshot(ad(), None)[0])
        matched = ad()
        self.assertEqual(check_ranked_site_snapshot(ad(), matched), [])

    def test_detects_rank_product_and_budget_mismatches(self):
        expected = ad("brand_recommendation", "Fastrack")
        site = ad("brand_recommendation", "Fastrack")
        site["products"][2]["product_id"] = "wrong"
        self.assertTrue(any("rank 3" in x for x in check_ranked_site_snapshot(expected, site)))
        candidate = ad()
        candidate["products"][0]["price_inr"] = 2500
        self.assertTrue(any("exceeds advertised budget" in x
                            for x in check_ranked_site_snapshot(candidate, ad())))

    def test_brand_must_match_in_brand_ad(self):
        candidate = ad("brand_recommendation", "Fastrack")
        candidate["products"][0]["brand"] = "Croma"
        self.assertTrue(any("brand mismatch" in x
                            for x in check_ranked_site_snapshot(candidate, ad("brand_recommendation", "Fastrack"))))


if __name__ == "__main__":
    unittest.main()
