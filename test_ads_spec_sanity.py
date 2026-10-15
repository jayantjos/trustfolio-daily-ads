"""No-network, data-preserving tests for ad-only spec claim hygiene."""
import unittest
from ads_qa.spec_sanity import is_sane_spec


class AdSpecSanityTests(unittest.TestCase):
    def test_smartwatch_obviously_wrong_inches_rejected(self):
        self.assertFalse(is_sane_spec("Smartwatches", "Display", "35.3 Inch Display"))
        self.assertFalse(is_sane_spec("smartwatches", "Display", "40 Inch Display"))
        self.assertFalse(is_sane_spec("Smartwatches", "Screen", '9.1"'))
        self.assertFalse(is_sane_spec("smartwatches", "", "40 inch display"))

    def test_realistic_display_claims_preserved(self):
        self.assertTrue(is_sane_spec("Smartwatches", "Display", '1.83" Display'))
        self.assertTrue(is_sane_spec("Smartwatches", "Display", "4.6 cm Display"))
        self.assertTrue(is_sane_spec("Smartwatches", "Display", "46 mm"))
        self.assertTrue(is_sane_spec("Smartwatches", "Bluetooth", "Bluetooth Calling"))
        self.assertTrue(is_sane_spec("Smartwatches", "Battery", "9 Hours Battery"))

    def test_other_categories_not_smartwatch_specific(self):
        self.assertTrue(is_sane_spec("Smart TVs", "Display", "55 Inch Display"))
        self.assertTrue(is_sane_spec("Desktop Computers", "Screen", '27"'))
        self.assertTrue(is_sane_spec("Headphones & Earbuds", "Driver", "40 mm"))
        self.assertTrue(is_sane_spec("Ceiling Fans", "Size", "120 cm"))

    def test_obviously_wrong_metric_watch_sizes(self):
        self.assertFalse(is_sane_spec("smartwatches", "Display", "35.3 cm"))
        self.assertFalse(is_sane_spec("smartwatches", "Display", "400 mm"))
        self.assertTrue(is_sane_spec("smartwatches", "Display", "3.5 cm"))

    def test_no_claim_is_not_filled_with_fake_data(self):
        self.assertFalse(is_sane_spec("smartwatches", "Display", ""))
        self.assertFalse(is_sane_spec("smartwatches", "Battery", None))


if __name__ == "__main__":
    unittest.main()
