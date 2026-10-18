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
from website_live_price_sync_v1 import overlay_site_live_prices, fetch_live_price_rows
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
            calls.append((request.get_method(), request.full_url))
            if request.get_method() == "POST":
                ids = json.loads(request.data)["ids"]
                return MockResponse([{
                    "id": pid, "platform": "amazon", "supported": True,
                    "deleted": False, "live": {"status": "ok", "price_inr": 1950},
                } for pid in ids])
            return MockResponse(site_payload())
        payload = build_site_ads_payload("smartwatches", 2000, opener=opener)
        self.assertEqual(len(calls), 2)
        self.assertEqual([method for method, _ in calls], ["GET", "POST"])
        self.assertTrue(calls[1][1].endswith("/api/live-prices"))
        self.assertEqual(payload["ranking_source"], "live_trustfolio_website_api")
        self.assertEqual(payload["price_refresh_source"], "trustfolio_website_live_prices_api")
        self.assertTrue(all(p["price_inr"] == 1950 for p in payload["ads"][0]["products"]))
        self.assertTrue(all(p["price_source"] == "website_live_price_api" for p in payload["ads"][0]["products"]))
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


    def test_live_refresh_mirrors_browser_prices_and_catalog_fallback(self):
        source = site_payload()
        rows = [{"id": p["id"], "supported": True, "deleted": False,
                 "live": {"status": "ok", "price_inr": 1988}}
                for p in source["products"]]
        rows[0]["live"] = {"status": "blocked", "price_inr": 1600}
        rows[2]["supported"] = False
        rows[2]["live"] = None
        updated = overlay_site_live_prices(source, rows, 2000)
        self.assertEqual(updated["products"][0]["price_inr"], 1901)
        self.assertEqual(updated["products"][1]["price_inr"], 1988)
        self.assertEqual(updated["products"][2]["price_inr"], 1903)
        self.assertEqual([p["id"] for p in updated["products"]],
                         [p["id"] for p in source["products"]])

    def test_deleted_or_out_of_stock_is_not_advertised(self):
        original = site_payload()
        rows = [{"id": p["id"], "deleted": False,
                 "live": {"status": "ok", "price_inr": 1950}}
                for p in original["products"]]
        rows[1]["deleted"] = True
        with self.assertRaisesRegex(ValueError, "out-of-stock"):
            overlay_site_live_prices(original, rows, 2000)
        rows[1]["deleted"] = False
        rows[1]["live"]["status"] = "out_of_stock"
        with self.assertRaisesRegex(ValueError, "out-of-stock"):
            overlay_site_live_prices(original, rows, 2000)

    def test_price_exceeds_ad_budget_after_refresh_skip_not_mislead(self):
        original = site_payload()
        rows = [{"id": p["id"], "live": {"status": "ok", "price_inr": 1950}}
                for p in original["products"]]
        rows[4]["live"]["price_inr"] = 2400
        with self.assertRaisesRegex(ValueError, "exceeds advertised budget"):
            overlay_site_live_prices(original, rows, 2000)

    def test_live_api_must_match_exact_product_ids(self):
        original = site_payload()
        rows = [{"id": p["id"], "live": None} for p in original["products"]]
        rows[3]["id"] = "unexpected-product-id"
        with self.assertRaisesRegex(ValueError, "does not match"):
            overlay_site_live_prices(original, rows, 2000)

    def test_live_refresh_invalid_response_prevents_ad(self):
        def opener(request, timeout):
            if request.get_method() == "GET":
                return MockResponse(site_payload())
            return MockResponse([])
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_site_ads_payload("smartwatches", 2000, opener=opener)

    def test_api_does_not_execute_mutating_http_methods(self):
        def opener(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            return MockResponse(site_payload())
        self.assertEqual(len(fetch_public_top5("smartwatches", 2000, opener=opener)["products"]), 5)


if __name__ == "__main__":
    unittest.main()
