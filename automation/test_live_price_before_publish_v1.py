"""No-network regression tests for rechecking actual website prices at Meta publish."""
import copy
import unittest
from automation.validate_live_price_before_publish_v1 import verify_snapshot


def fixture():
    plan={"status":"eligible","mode":"brand_budget",
          "category":"induction-cooktop","budget":5000,"brand":"Prestige",
          "campaign_id":"tfauto-"+"a"*18}
    ids=["product-"+str(i) for i in range(1,6)]
    prices=[4599,4999,4897,4699,4999]
    sources=["website_live_price_api","website_catalog",
             "website_live_price_api","website_live_price_api","website_live_price_api"]
    report={"source":"live_trustfolio_website_api","live_price_refresh_completed":True,
            "live_price_api":"https://api.trustfolio.in/api/live-prices",
            "campaign_category":"induction-cooktop","campaign_budget_inr":5000,
            "campaign_brand":"Prestige","campaign_mode":"brand_budget",
            "source_product_ids_by_rank":ids,"visual_product_ids_by_rank":ids[:],
            "displayed_prices_by_rank":prices,"price_sources_by_rank":sources}
    payload={"ads":[{"ranking_source":"live_trustfolio_website_api",
                    "live_price_refresh_completed":True,
                    "products":[{"product_id":i,"price_inr":p,"price_source":s,"brand":"Prestige"}
                                for i,p,s in zip(ids,prices,sources)]}]}
    return plan,report,payload


class LivePriceBeforePublishTests(unittest.TestCase):
    def test_live_and_catalog_matches_website_display_contract(self):
        plan,report,payload=fixture()
        calls=[]
        def fake(category,budget,brand):
            calls.append((category,budget,brand))
            return payload
        out=verify_snapshot(plan,report,fetcher=fake)
        self.assertEqual(calls,[("induction-cooktop",5000,"Prestige")])
        self.assertEqual(out["live_price_api_count"],4)
        self.assertEqual(out["website_catalog_fallback_count"],1)
        self.assertEqual(out["ranked_product_count"],5)
        self.assertEqual(out["status"],"verified_same_displayed_prices_before_publish")

    def test_stale_price_must_abort_instead_of_post(self):
        plan,report,payload=fixture()
        payload["ads"][0]["products"][2]["price_inr"]=4988
        with self.assertRaisesRegex(ValueError,"price changed"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)

    def test_changed_rank_id_must_abort(self):
        plan,report,payload=fixture()
        payload["ads"][0]["products"][1]["product_id"]="new-product"
        with self.assertRaisesRegex(ValueError,"rank/product IDs changed"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)

    def test_live_status_change_must_abort(self):
        plan,report,payload=fixture()
        payload["ads"][0]["products"][1]["price_source"]="website_live_price_api"
        with self.assertRaisesRegex(ValueError,"price source changed"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)

    def test_render_without_price_refresh_proof_blocked(self):
        plan,report,payload=fixture()
        report["live_price_refresh_completed"]=False
        attempted=[]
        def fake(*args):
            attempted.append(True)
            return payload
        with self.assertRaisesRegex(ValueError,"no verified website live-price refresh"):
            verify_snapshot(plan,report,fetcher=fake)
        self.assertFalse(attempted)

    def test_invalid_brand_or_budget_fails_closed(self):
        plan,report,payload=fixture()
        payload["ads"][0]["products"][4]["brand"]="Other"
        with self.assertRaisesRegex(ValueError,"brand invalidates"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)
        plan,report,payload=fixture()
        payload["ads"][0]["products"][0]["price_inr"]=5001
        with self.assertRaisesRegex(ValueError,"price changed"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)

    def test_no_current_live_price_refresh_blocks_publication(self):
        plan,report,payload=fixture()
        payload["ads"][0]["live_price_refresh_completed"]=False
        with self.assertRaisesRegex(ValueError,"not completed"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)

    def test_exact_rendered_mode_and_product_order(self):
        plan,report,payload=fixture()
        report["campaign_mode"]="budget"
        with self.assertRaisesRegex(ValueError,"differs from plan"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)
        plan,report,payload=fixture()
        report["visual_product_ids_by_rank"][0]="replacement"
        with self.assertRaisesRegex(ValueError,"Visual rankings"):
            verify_snapshot(plan,report,fetcher=lambda *args:payload)


if __name__=="__main__":
    unittest.main()
