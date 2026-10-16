"""Regression for TrustFolio premium artwork variant-specific hero copy."""
import unittest
from pathlib import Path
from ads_qa.campaign_display_v1 import campaign_hero, headline_font_size, campaign_subtitle
from build_infographic_payload_v1 import build_payload


def fake_ad(brand="", mode="brand_recommendation"):
    return {
      "ad_type":mode,"category":"smart-phones","brand":brand,"budget_inr":15000,
      "headline":"Test live website headline",
      "image_ad":{"products":[
        {"rank":i,"title":f"phone {i}","price":14999,"platform":"amazon",
         "image_url":f"https://images.example.com/{i}.png"} for i in range(1,6)]},
    }


class CampaignHeroTests(unittest.TestCase):
    def test_budget_headline_is_unchanged(self):
        self.assertEqual(campaign_hero("smart-phones","Smartphones","budget_recommendation"),"Best Smartphones")
        self.assertEqual(campaign_hero("headphones-earbuds","Headphones & Earbuds","budget_recommendation"),
                         "Best Headphones & Earbuds")

    def test_brand_visible_in_frozen_purple_title(self):
        for slug,label,brand,expected in (
            ("smart-phones","Smartphones","Samsung","Best Samsung Phones"),
            ("smart-tvs","Smart TVs","Onida","Best Onida TVs"),
            ("laptops","Laptops","HP","Best HP Laptops"),
            ("smartwatches","Smartwatches","Noise","Best Noise Watches"),
            ("washing-machines","Washing Machines","IFB","Best IFB Washers"),
            ("headphones-earbuds","Headphones & Earbuds","Noise","Best Noise Earbuds"),
        ):
            with self.subTest(slug=slug):
                self.assertEqual(campaign_hero(slug,label,"brand_recommendation",brand),expected)
                self.assertGreaterEqual(headline_font_size(expected),35)

    def test_compare_distinct_from_best_copy_and_keeps_category(self):
        self.assertEqual(campaign_hero("smart-phones","Smartphones","top5_comparison"),"Compare Smartphones")
        self.assertEqual(campaign_hero("smart-tvs","Smart TVs","top5_comparison"),"Compare Smart TVs")
        self.assertEqual(campaign_subtitle(
            "Top 5 Picks for Sound, Battery & Value","top5_comparison"),
            "Compare Picks for Sound, Battery & Value")

    def test_brand_creative_requires_real_brand(self):
        with self.assertRaisesRegex(ValueError,"missing"):
            campaign_hero("smart-phones","Smartphones","brand_recommendation","")
        with self.assertRaisesRegex(ValueError,"Unsafe"):
            campaign_hero("smart-phones","Smartphones","brand_recommendation","Bad<Name>")

    def test_infographic_payload_retains_brand(self):
        payload=build_payload(fake_ad("Samsung","brand_recommendation"))
        self.assertEqual(payload["metadata"]["campaign_brand"],"Samsung")
        self.assertEqual(payload["metadata"]["campaign_budget_inr"],15000)
        self.assertEqual(payload["source_ad_type"],"brand_recommendation")
        self.assertEqual(len(payload["products"]),5)

    def test_html_renderer_uses_copy_and_only_resizes_variant(self):
        source=(Path(__file__).resolve().parents[1]/"master_template_renderer_html_v4.py").read_text("utf8")
        self.assertIn("campaign_hero(key,profile['label'],ad_type,campaign_brand)",source)
        self.assertIn("'brand_recommendation','top5_comparison'",source)
        self.assertIn('<div class="hero hero1"{hero_style}>',source)
        self.assertNotIn("title=f'Best {profile[",source)


if __name__=="__main__":
    unittest.main()
