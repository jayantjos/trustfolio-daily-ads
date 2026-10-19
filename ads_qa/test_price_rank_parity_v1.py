"""Tests for untouched website ranked/live price -> original premium ad parity."""
import copy
import unittest
from ads_qa.price_rank_parity_v1 import verify_ranked_price_pipeline


def sample():
    ids=["actual-id-"+str(i) for i in range(1,6)]
    prices=[4599,4999,4999,4897,4699]
    src=["website_live_price_api","website_live_price_api",
         "website_catalog","website_catalog","website_catalog"]
    source={"live_price_refresh_completed":True,
            "products":[{"rank":i,"product_id":k,"price_inr":v,"price_source":q}
                        for i,(k,v,q) in enumerate(zip(ids,prices,src),1)]}
    linked={"products":[{"rank":i,"product_id":k,"price_inr":v} for i,(k,v) in enumerate(zip(ids,prices),1)]}
    creative={"image_ad":{"products":[
        {"rank":i,"source_product_id":k,"price":v}
        for i,(k,v) in enumerate(zip(ids,prices),1)]}}
    infographic={"products":[{"rank":i,"source_product_id":k,"price_inr":v}
                            for i,(k,v) in enumerate(zip(ids,prices),1)]}
    return source,linked,creative,infographic


class RankedPriceParityTests(unittest.TestCase):
    def test_actual_website_mixed_live_and_catalog_fallback(self):
        chain=sample()
        result=verify_ranked_price_pipeline(*chain)
        self.assertEqual(result["displayed_prices_by_rank"],[4599,4999,4999,4897,4699])
        self.assertEqual(result["visual_prices_by_rank"],result["displayed_prices_by_rank"])
        self.assertEqual(result["live_api_priced_products"],2)
        self.assertEqual(result["catalog_fallback_products"],3)
        self.assertEqual(len(result["source_product_ids_by_rank"]),5)

    def test_source_rank_reordered_fails(self):
        chain=sample()
        chain[0]["products"][0]["rank"]=2
        with self.assertRaisesRegex(ValueError,"ranking reordered"):
            verify_ranked_price_pipeline(*chain)

    def test_renderer_price_changed_fails(self):
        chain=sample()
        chain[3]["products"][0]["price_inr"]=4598
        with self.assertRaisesRegex(ValueError,"displayed price changed"):
            verify_ranked_price_pipeline(*chain)

    def test_creator_price_changed_fails(self):
        chain=sample()
        chain[2]["image_ad"]["products"][1]["price"]=5000
        with self.assertRaisesRegex(ValueError,"displayed price changed"):
            verify_ranked_price_pipeline(*chain)

    def test_wrong_image_product_assignment_fails(self):
        chain=sample()
        chain[2]["image_ad"]["products"][2]["source_product_id"]="different-product"
        with self.assertRaisesRegex(ValueError,"product ID / displayed price changed"):
            verify_ranked_price_pipeline(*chain)

    def test_missing_live_price_proof_fails(self):
        chain=sample()
        chain[0]["live_price_refresh_completed"]=False
        with self.assertRaisesRegex(ValueError,"overlay not completed"):
            verify_ranked_price_pipeline(*chain)

    def test_unproven_price_source_fails(self):
        chain=sample()
        chain[0]["products"][2]["price_source"]="unknown"
        with self.assertRaisesRegex(ValueError,"Unverified product price source"):
            verify_ranked_price_pipeline(*chain)

    def test_fractional_prices_not_silently_rounded_in_art(self):
        chain=sample()
        for data,key in [(chain[0]["products"][0],"price_inr"),
                         (chain[1]["products"][0],"price_inr"),
                         (chain[2]["image_ad"]["products"][0],"price"),
                         (chain[3]["products"][0],"price_inr")]:
            data[key]=4599.50
        with self.assertRaisesRegex(ValueError,"fractional"):
            verify_ranked_price_pipeline(*chain)

    def test_truncated_list_fails(self):
        chain=sample()
        chain[1]["products"].pop()
        with self.assertRaisesRegex(ValueError,"exactly five"):
            verify_ranked_price_pipeline(*chain)


if __name__=="__main__":
    unittest.main()
