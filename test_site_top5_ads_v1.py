"""Contract tests for website-ranked dynamic ads (no network needed)."""
import json
import unittest
from urllib.parse import parse_qs, urlsplit

from site_top5_ads_v1 import (
    build_site_ads_payload,
    normalize_site_ad,
    site_api_url,
    fetch_public_top5,
)
from ad_link_manifest_v1 import build_manifest
from test_campaign_link_contract_v1 import config


def site_payload(brand=""):
    products = []
    for index in range(1, 6):
        products.append({
            "id": "website-sku-" + str(index),
            "rank": index,
            "title": "Website watch " + str(index),
            "brand": brand or "TIMEX",
            "platform": "amazon",
            "price_inr": 1900 + index,
            "main_image": "https://images.example.com/item-" + str(index) + ".png",
            "specifications": {"Battery": "7 days"},
            "average_rating": "4.2",
            "product_url": "https://example.com/product-" + str(index),
        })
    return {"products": products, "fallbackApplied": False, "matchType": "within_budget"}


class MockResponse:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, data):
        self.data = json.dumps({"success": True, "data": data}).encode("utf8")
    def read(self, n=None):
        return self.data[:n]
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


class SiteRankedCampaignTests(unittest.TestCase):
    def test_source_api_url_exact_search_filters(self):
        url = site_api_url("smartwatches", 2000, "TIMEX & Co")
        self.assertEqual(urlsplit(url).netloc, "api.trustfolio.in")
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query, {
            "category": ["smartwatches"], "budget": ["2000"],
            "limit": ["5"], "brand": ["TIMEX & Co"],
        })

    def test_real_website_response_keeps_its_rank_and_identity(self):
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            return MockResponse(site_payload())
        payload = build_site_ads_payload("smartwatches", 2000, opener=opener)
        self.assertEqual(len(calls), 1)
        self.assertEqual(payload["ranking_source"], "live_trustfolio_website_api")
        ad = payload["ads"][0]
        self.assertEqual([p["product_id"] for p in ad["products"]],
                         ["website-sku-" + str(i) for i in range(1, 6)])
        self.assertEqual([p["rank"] for p in ad["products"]], list(range(1, 6)))

    def test_manifest_links_to_actual_results_page_and_keeps_ranks(self):
        cfg = config()
        cfg["links"]["budget_query_parameter"] = {
            "enabled": True, "frontend_verified": True, "parameter": "budget"}
        cfg["links"]["brand_query_parameter"] = {
            "enabled": True, "frontend_verified": True, "parameter": "brand"}
        ad = normalize_site_ad("smartwatches", 2000, "TIMEX", site_payload("TIMEX"))
        manifest = build_manifest({"ads": [ad]}, cfg)
        item = manifest["ads"][0]
        self.assertEqual(item["site_ranking_status"], "verified")
        self.assertTrue(item["prefill_ready"])
        self.assertEqual(urlsplit(item["landing_url"]).path, "/category/smartwatches/products")
        self.assertEqual(parse_qs(urlsplit(item["landing_url"]).query)["brand"], ["TIMEX"])
        self.assertEqual([p["ad_rank"] for p in item["products"]], [1, 2, 3, 4, 5])
        self.assertEqual(item["products"][0]["product_id"], "website-sku-1")
        self.assertTrue(all(p["click_url"] == item["landing_url"] for p in item["products"]))

    def test_brand_fallback_rejected(self):
        result = site_payload("TIMEX")
        result["fallbackApplied"] = True
        with self.assertRaisesRegex(ValueError, "brand-fallback"):
            normalize_site_ad("smartwatches", 2000, "TIMEX", result)

    def test_brand_mismatch_rejected(self):
        result = site_payload("TIMEX")
        result["products"][2]["brand"] = "Noise"
        with self.assertRaisesRegex(ValueError, "different brand"):
            normalize_site_ad("smartwatches", 2000, "TIMEX", result)

    def test_missing_image_rejected(self):
        result = site_payload()
        result["products"][3]["main_image"] = ""
        with self.assertRaisesRegex(ValueError, "HTTPS image"):
            normalize_site_ad("smartwatches", 2000, "", result)

    def test_price_over_budget_rejected(self):
        result = site_payload()
        result["products"][4]["price_inr"] = 2100
        with self.assertRaisesRegex(ValueError, "exceeds budget"):
            normalize_site_ad("smartwatches", 2000, "", result)

    def test_short_and_duplicate_lists_rejected(self):
        result = site_payload()
        result["products"].pop()
        with self.assertRaisesRegex(ValueError, "exactly five"):
            normalize_site_ad("smartwatches", 2000, "", result)
        result = site_payload()
        result["products"][4]["id"] = result["products"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            normalize_site_ad("smartwatches", 2000, "", result)

    def test_unverified_snapshot_must_not_claim_parity(self):
        ad = normalize_site_ad("smartwatches", 2000, "", site_payload())
        ad["website_snapshot"]["products"][1]["product_id"] = "wrong"
        item = build_manifest({"ads": [ad]}, config())["ads"][0]
        self.assertEqual(item["site_ranking_status"], "unverified")

    def test_api_does_not_execute_mutating_http_methods(self):
        def opener(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            return MockResponse(site_payload())
        self.assertEqual(len(fetch_public_top5("smartwatches", 2000, opener=opener)["products"]), 5)


if __name__ == "__main__":
    unittest.main()
