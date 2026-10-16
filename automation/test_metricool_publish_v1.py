"""Publishing gate tests: never contact Metricool when disabled, wrong account or no media."""
import json
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from automation.metricool_publish_v1 import (
    _find_media_id, _require_env, _check_media, schedule_validated_post, ai_disclosure_for_manifest,
)


def manifest():
    return {
        "status":"ready_for_publishing_gate",
        "publication_status":"not_published","network":"instagram",
        "instagram_account":"trustfolio3","campaign_id":"tfauto-"+"a"*18,
        "ranked_product_ids":["a","b","c","d","e"],
        "geometry_errors":[],"caption":"TrustFolio Top 5",
    }


class MetricoolPublishGateTests(unittest.TestCase):
    def test_explicit_enable_required(self):
        with patch.dict(os.environ,{"TF_AUTO_POST_ENABLED":"false"},clear=True):
            with self.assertRaisesRegex(ValueError,"Posting disabled"):
                _require_env()
            with self.assertRaisesRegex(ValueError,"Posting disabled"):
                schedule_validated_post(manifest(),"https://media.trustfolio.in/trustfolio-auto/sample.jpg","doesnotexist")

    def test_expected_metricool_brand_required(self):
        with patch.dict(os.environ,{
            "TF_AUTO_POST_ENABLED":"true",
            "TF_METRICOOL_BLOG_ID":"00000",
            "TF_METRICOOL_USER_ID":"5635852"},clear=True):
            with self.assertRaisesRegex(ValueError,"brand IDs differ"):
                _require_env()

    def test_wrong_account_refused_before_http(self):
        m=manifest()
        m["instagram_account"]="joshierjayant"
        with self.assertRaisesRegex(ValueError,"not @trustfolio3"):
            schedule_validated_post(m,"https://media.trustfolio.in/trustfolio-auto/sample.jpg","doesnotexist")

    def test_invalid_qa_refused(self):
        m=manifest()
        m["geometry_errors"]=["overlap rank5"]
        with self.assertRaisesRegex(ValueError,"QA not clean"):
            schedule_validated_post(m,"https://media.trustfolio.in/trustfolio-auto/sample.jpg","doesnotexist")

    def test_media_must_be_public_trustfolio_url(self):
        with self.assertRaisesRegex(ValueError,"permanent public TrustFolio"):
            _check_media("https://evil.example.com/image.jpg","doesnotexist")

    def test_unknown_reference_provenance_discloses_ai(self):
        self.assertTrue(ai_disclosure_for_manifest(manifest()))

    def test_only_verified_human_artwork_allows_non_ai_label(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"provenance.json"
            file.write_text('{"master_artwork_origin":"human_designed_no_generative_ai","human_origin_verified":false}')
            with self.assertRaisesRegex(ValueError,"provenance verification"):
                ai_disclosure_for_manifest(manifest(),str(file))
            file.write_text('{"master_artwork_origin":"human_designed_no_generative_ai","human_origin_verified":true}')
            self.assertFalse(ai_disclosure_for_manifest(manifest(),str(file)))
            file.write_text('{"master_artwork_origin":"generative_ai","human_origin_verified":false}')
            self.assertTrue(ai_disclosure_for_manifest(manifest(),str(file)))

    def test_media_id_extracted_only_when_real(self):
        self.assertEqual(_find_media_id({"data":{"mediaId":"abc123"}}),"abc123")
        self.assertEqual(_find_media_id({"media":[{"id":456}]}),"456")
        self.assertIsNone(_find_media_id({"data":{"url":"https://cdn.example/photo.jpg"}}))


if __name__=="__main__":
    unittest.main()
