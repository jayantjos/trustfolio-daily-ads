"""Regression tests for existing deployed TrustFolio website-price → ads pipeline.

No new product ranker, alternate price database, website/backend edits,
scraper changes, publish attempts or fake product substitutions.
"""
import copy
import unittest
from unittest.mock import Mock

from automation.validate_live_price_before_publish_v1 import verify_snapshot
from website_live_price_sync_v1 import overlay_site_live_prices

IDS=[f"site-product-{i}" for i in range(1,6)]
PRICES=[4599,4999,4897,4699,4999]
SOURCES=["website_live_price_api","website_catalog",
         "website_live_price_api","website_live_price_api","website_live_price_api"]


def sample():
    plan={"status":"eligible","mode":"budget","category":"induction-cooktop",
          "budget":5000,"brand":"","campaign_id":"tfauto-verified-live-test"}
    report={
       "source":"live_trustfolio_website_api",
       "live_price_refresh_completed":True,
       "live_price_api":"https://api.trustfolio.in/api/live-prices",
       "campaign_category":"induction-cooktop",
       "campaign_budget_inr":5000,
       "campaign_brand":None,
       "campaign_mode":"budget",
       "source_product_ids_by_rank":list(IDS),
       "visual_product_ids_by_rank":list(IDS),
       "displayed_prices_by_rank":list(PRICES),
       "price_sources_by_rank":list(SOURCES),
    }
    data={"ads":[{"ranking_source":"live_trustfolio_website_api",
                  "live_price_refresh_completed":True,
                  "products":[{"product_id":id,"price_inr":price,
                               "brand":"Brand","price_source":src}
                              for id,price,src in zip(IDS,PRICES,SOURCES)]}]}
    return plan,report,data


class PreserveOriginalPricesAndRanks(unittest.TestCase):
    def test_real_snapshot_four_live_one_catalog_keeps_original_five_products(self):
        plan,report,payload=sample()
        fetcher=Mock(return_value=copy.deepcopy(payload))
        result=verify_snapshot(plan,report,fetcher=fetcher)
        self.assertEqual(result["status"],"verified_same_displayed_prices_before_publish")
        self.assertEqual(result["ranked_product_count"],5)
        self.assertEqual(result["live_price_api_count"],4)
        self.assertEqual(result["website_catalog_fallback_count"],1)
        fetcher.assert_called_once_with("induction-cooktop",5000,"")

    def test_changed_real_price_blocks_stale_ad_without_updating_it(self):
        plan,report,payload=sample()
        payload["ads"][0]["products"][0]["price_inr"]=4799
        with self.assertRaisesRegex(ValueError,"price changed"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))
        self.assertEqual(report["displayed_prices_by_rank"][0],4599)

    def test_changed_original_rank_fails_without_new_ranking(self):
        plan,report,payload=sample()
        payload["ads"][0]["products"][0],payload["ads"][0]["products"][1]=(
            payload["ads"][0]["products"][1],payload["ads"][0]["products"][0])
        with self.assertRaisesRegex(ValueError,"Top Five rank/product IDs changed"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))

    def test_later_live_over_budget_blocks_claim(self):
        plan,report,payload=sample()
        payload["ads"][0]["products"][4]["price_inr"]=5001
        with self.assertRaisesRegex(ValueError,"price changed"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))

    def test_changed_live_catalog_source_blocks_stale_ad(self):
        plan,report,payload=sample()
        payload["ads"][0]["products"][1]["price_source"]="website_live_price_api"
        with self.assertRaisesRegex(ValueError,"price source changed"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))

    def test_brand_ad_keeps_selected_oem_brand(self):
        plan,report,payload=sample()
        plan["mode"]="brand_budget"
        plan["brand"]="Brand"
        report["campaign_brand"]="Brand"
        report["campaign_mode"]="brand_budget"
        result=verify_snapshot(plan,report,fetcher=Mock(return_value=payload))
        self.assertEqual(result["ranked_product_count"],5)
        plan["brand"]="Wrong"
        with self.assertRaisesRegex(ValueError,"differs from plan"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))

    def test_no_second_api_refresh_means_no_social_post(self):
        plan,report,payload=sample()
        payload["ads"][0]["live_price_refresh_completed"]=False
        with self.assertRaisesRegex(ValueError,"live-price refresh"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))
        plan,report,payload=sample()
        report["live_price_refresh_completed"]=False
        with self.assertRaisesRegex(ValueError,"no verified website live-price refresh"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))

    def test_missing_fifth_product_never_fake_fills(self):
        plan,report,payload=sample()
        payload["ads"][0]["products"]=payload["ads"][0]["products"][:4]
        with self.assertRaisesRegex(ValueError,"exactly five"):
            verify_snapshot(plan,report,fetcher=Mock(return_value=payload))

    def test_live_price_overlay_matches_existing_website_display_rule(self):
        site={"products":[{"id":id,"price_inr":price,"rank":index+1}
                          for index,(id,price) in enumerate(zip(IDS,PRICES))]}
        rows=[]
        for index,id in enumerate(IDS):
            if index==1:
                rows.append({"id":id,"deleted":False,"live":None})
            else:
                rows.append({"id":id,"deleted":False,"live":{"status":"ok",
                            "price_inr":PRICES[index]}})
        refreshed=overlay_site_live_prices(site,rows,5000)["products"]
        self.assertEqual([p["id"] for p in refreshed],IDS)
        self.assertEqual([p["rank"] for p in refreshed],[1,2,3,4,5])
        self.assertEqual([p["price_inr"] for p in refreshed],PRICES)
        self.assertEqual([p["price_source"] for p in refreshed],SOURCES)

    def test_site_out_of_stock_and_over_budget_dont_get_advertised(self):
        site={"products":[{"id":id,"price_inr":price,"rank":index+1}
                          for index,(id,price) in enumerate(zip(IDS,PRICES))]}
        rows=[{"id":id,"deleted":False,"live":{"status":"ok","price_inr":PRICES[i]}}
              for i,id in enumerate(IDS)]
        rows[2]["live"]["status"]="out_of_stock"
        with self.assertRaisesRegex(ValueError,"out-of-stock"):
            overlay_site_live_prices(site,rows,5000)
        rows[2]["live"]["status"]="ok"
        rows[2]["live"]["price_inr"]=5999
        with self.assertRaisesRegex(ValueError,"exceeds advertised budget"):
            overlay_site_live_prices(site,rows,5000)


if __name__=="__main__":
    unittest.main()
