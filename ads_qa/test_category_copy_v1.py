"""Regression: static TrustFolio design must not inherit smartwatch copy."""
import unittest
from pathlib import Path

from ads_qa.category_copy_v1 import (
    _profile_copy, category_tagline, GENERIC, SAME_PRODUCT_COMPARISON,
)
from build_infographic_payload_v1 import build_payload


def sample_ad(category, ad_type="budget_recommendation"):
    return {
        "category":category,
        "ad_type":ad_type,
        "headline":"Best " + category + " Under ₹3,000",
        "image_ad":{"products":[{"rank":i,"full_title":"Item "+str(i),
            "price":1999,"platform":"amazon","image_url":"https://example.com/"+str(i)+".png"}
            for i in range(1,6)]},
    }


class CategorySpecificSubtitleTests(unittest.TestCase):
    def test_all_twenty_category_slugs_have_distinct_appropriate_source(self):
        profiles=_profile_copy()
        self.assertGreaterEqual(len(profiles),20)
        for slug,profile in profiles.items():
            with self.subTest(category=slug):
                self.assertEqual(category_tagline(slug),profile["tagline"])
                self.assertEqual(category_tagline(profile["label"]),profile["tagline"])
                self.assertTrue(profile["tagline"].startswith("Top 5 Picks"))

    def test_earbuds_no_fitness(self):
        subtitle=build_payload(sample_ad("headphones-earbuds"))["metadata"]["subtitle"]
        self.assertEqual(subtitle,"Top 5 Picks for Sound, Battery & Value")
        self.assertNotIn("Fitness",subtitle)

    def test_smartwatches_preserve_fitness(self):
        self.assertEqual(build_payload(sample_ad("smartwatches"))["metadata"]["subtitle"],
                         "Top 5 Picks for Style, Fitness & Value")

    def test_laptops_phones_and_fans_do_not_share_smartwatch_copy(self):
        for category,keywords in (
            ("laptops",("Work","Speed")),
            ("smart-phones",("Camera","Speed")),
            ("ceiling-fans",("Airflow","Efficiency")),
            ("speakers",("Sound","Bass")),
            ("smart-tvs",("Picture","Sound")),
        ):
            with self.subTest(category=category):
                subtitle=build_payload(sample_ad(category))["metadata"]["subtitle"]
                for word in keywords:self.assertIn(word,subtitle)
                self.assertNotIn("Fitness",subtitle)

    def test_price_comparison_has_appropriate_copy(self):
        ad=sample_ad("headphones-earbuds",ad_type="price_comparison")
        self.assertEqual(build_payload(ad)["metadata"]["subtitle"],SAME_PRODUCT_COMPARISON)

    def test_unknown_category_fails_to_generic_non_smartwatch_copy(self):
        self.assertEqual(category_tagline("new-unknown-product-category"),GENERIC)
        self.assertNotIn("Fitness",category_tagline("new-unknown-product-category"))

    def test_renderer_must_use_category_resolver_not_stale_metadata(self):
        source=(Path(__file__).resolve().parents[1] /
                "master_template_renderer_html_v4.py").read_text(encoding="utf8")
        self.assertIn("category_tagline(key",source)
        self.assertNotIn("get('subtitle') or ad.get('tagline')",source)


if __name__=="__main__":
    unittest.main()
