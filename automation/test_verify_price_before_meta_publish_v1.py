"""Ads-only live price/rank QA: do not alter website/API or original ranking."""
import copy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock

from automation.verify_price_before_meta_publish_v1 import (
    verify_fresh_snapshot, PriceAuditBlocked,
)

NOW = datetime(2026, 10, 19, 14, 30, tzinfo=timezone.utc)
IDS = [f"website-product-{n}" for n in range(1, 6)]
PRICES = [1599, 2199, 2999, 3500, 4500]
SOURCES = ["website_live_price_api", "website_catalog", "website_live_price_api",
           "website_live_price_api", "website_live_price_api"]
STATES = ["ok", None, "ok", "ok", "ok"]


def fixture():
    plan = {"status": "eligible", "mode": "budget", "date_ist": "2026-10-19",
            "category": "induction-cooktop", "budget": 5000, "brand": ""}
    report = {
        "source": "live_trustfolio_website_api",
        "live_price_refresh_completed": True,
        "live_price_api": "https://api.trustfolio.in/api/live-prices",
        "campaign_category": "induction-cooktop",
        "campaign_budget_inr": 5000,
        "campaign_brand": None,
        "campaign_mode": "budget",
        "source_product_ids_by_rank": list(IDS),
        "visual_product_ids_by_rank": list(IDS),
        "displayed_prices_by_rank": list(PRICES),
        "price_sources_by_rank": list(SOURCES),
        "live_statuses_by_rank": list(STATES),
        "source_observed_at": (NOW - timedelta(seconds=70)).isoformat(),
    }
    response = {
        "ads": [{
            "ranking_source": "live_trustfolio_website_api",
            "live_price_refresh_completed": True,
            "products": [
                {"product_id": id, "price_inr": price, "price_source": source,
                 "live_price_status": status}
                for id, price, source, status in zip(IDS, PRICES, SOURCES, STATES)
            ]
        }]
    }
    return plan, report, response


class PriceParityTests(unittest.TestCase):
    def test_original_website_ranking_and_mix_of_live_catalog_prices_are_preserved(self):
        p, r, data = fixture()
        fetcher = Mock(return_value=copy.deepcopy(data))
        out = verify_fresh_snapshot(p, r, fetcher=fetcher, now=NOW)
        self.assertTrue(out["publication_approved"])
        self.assertEqual(out["five_ranked_products"], 5)
        self.assertEqual(out["live_prices"], 4)
        self.assertEqual(out["catalog_fallback_prices"], 1)
        fetcher.assert_called_once_with("induction-cooktop", 5000, "")

    def test_live_price_changes_after_render_must_not_publish_old_jpg(self):
        p, r, data = fixture()
        data["ads"][0]["products"][0]["price_inr"] = 1799
        with self.assertRaisesRegex(PriceAuditBlocked, "price changed"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)

    def test_ranking_changes_after_render_must_not_publish_old_order(self):
        p, r, data = fixture()
        data["ads"][0]["products"].reverse()
        with self.assertRaisesRegex(PriceAuditBlocked, "ranking changed"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)

    def test_rendered_and_current_prices_must_fit_budget(self):
        p, r, data = fixture()
        data["ads"][0]["products"][4]["price_inr"] = 5100
        with self.assertRaisesRegex(PriceAuditBlocked, "exceeds the advertised budget"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)
        p, r, data = fixture()
        r["displayed_prices_by_rank"][4] = 5200
        with self.assertRaisesRegex(PriceAuditBlocked, "exceeds the advertised budget"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)

    def test_price_source_changes_are_audited_and_not_mislabeled(self):
        p, r, data = fixture()
        data["ads"][0]["products"][1]["price_source"] = "website_live_price_api"
        data["ads"][0]["products"][1]["live_price_status"] = "ok"
        with self.assertRaisesRegex(PriceAuditBlocked, "provenance changed"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)
        p, r, data = fixture()
        r["price_sources_by_rank"][1] = "website_live_price_api"
        with self.assertRaisesRegex(PriceAuditBlocked, "without an OK"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)

    def test_wrong_live_price_endpoint_refused_before_api_request(self):
        p,r,data=fixture()
        r["live_price_api"]="https://unverified.example/live-prices"
        fetcher=Mock(return_value=data)
        with self.assertRaisesRegex(PriceAuditBlocked,"original TrustFolio"):
            verify_fresh_snapshot(p,r,fetcher=fetcher,now=NOW)
        fetcher.assert_not_called()

    def test_explicit_zero_live_prices_are_catalog_fallback_not_faked_live(self):
        p,r,data=fixture()
        r["price_sources_by_rank"]=["website_catalog"]*5
        r["live_statuses_by_rank"]=[None]*5
        for product in data["ads"][0]["products"]:
            product["price_source"]="website_catalog"
            product["live_price_status"]=None
        result=verify_fresh_snapshot(p,r,fetcher=Mock(return_value=data),now=NOW)
        self.assertEqual(result["live_prices"],0)
        self.assertEqual(result["catalog_fallback_prices"],5)

    def test_missing_or_stale_or_unavailable_live_price_refuses_to_publish(self):
        p, r, data = fixture()
        r["live_price_refresh_completed"] = False
        with self.assertRaisesRegex(PriceAuditBlocked, "did not complete"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)
        p, r, data = fixture()
        r["source_observed_at"] = (NOW - timedelta(minutes=45)).isoformat()
        with self.assertRaisesRegex(PriceAuditBlocked, "too old"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)
        p, r, data = fixture()
        data["ads"][0]["live_price_refresh_completed"] = False
        with self.assertRaisesRegex(PriceAuditBlocked, "did not complete"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)

    def test_same_brand_original_site_filter_must_stay_unchanged(self):
        p, r, data = fixture()
        p["mode"] = "brand_budget"
        p["brand"] = "Samsung"
        r["campaign_mode"] = "brand_budget"
        r["campaign_brand"] = None
        with self.assertRaisesRegex(PriceAuditBlocked, "brand"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)

    def test_no_fabricated_fifth_product_or_rank_duplicates(self):
        p, r, data = fixture()
        r["source_product_ids_by_rank"][4] = r["source_product_ids_by_rank"][3]
        with self.assertRaisesRegex(PriceAuditBlocked, "product IDs"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)
        p, r, data = fixture()
        data["ads"][0]["products"] = data["ads"][0]["products"][:4]
        with self.assertRaisesRegex(PriceAuditBlocked, "five verified"):
            verify_fresh_snapshot(p, r, fetcher=Mock(return_value=data), now=NOW)


if __name__ == "__main__":
    unittest.main()
