"""No-network LinkedIn/X posting safety regression tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from datetime import datetime
from zoneinfo import ZoneInfo
from automation import linkedin_x_crosspost_v1 as social

def sample():
    return {"status":"ready_for_publishing_gate","publication_status":"not_published",
      "instagram_account":"trustfolio3","source_renderer":"master_template_renderer_html_v4",
      "size":[1080,1350],"geometry_errors":[],"ranked_product_ids":["p1","p2","p3","p4","p5"],
      "campaign_id":"tfauto-"+"a"*18,"date_ist":datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
      "mode":"comparison","category":"laptops","budget_inr":55000,"brand":"",
      "landing_url":"https://www.trustfolio.in/category/laptops/products?budget=55000",
      "caption":"TrustFolio real Top-5 under budget: https://www.trustfolio.in/category/laptops/products?budget=55000. Full selection and official mobile app: https://play.google.com/store/apps/details?id=com.trustfolio.app"}

class SocialTests(unittest.TestCase):
    def test_linkedin_uploads_same_bytes_and_actual_caption(self):
        p=sample()
        with tempfile.TemporaryDirectory() as root:
            file=Path(root)/"one.jpg";file.write_bytes(b"\xff\xd8\xff"+b"0"*2000)
            calls=[]
            def fake(url,token,**kw):
                calls.append((url,kw))
                if "initializeUpload" in url:
                    return (200,{"value":{"uploadUrl":"https://www.linkedin.com/dms-uploads/test",
                         "image":"urn:li:image:Photo55"}},{})
                if url.endswith("/rest/posts"):
                    return (201,{},{"x-restli-id":"urn:li:ugcPost:1234567890"})
                return (200,{}, {})
            ident=social.linkedin_image_post(p,file,"TOKEN","urn:li:organization:123",
                                              requester=fake)
            self.assertEqual(ident,"urn:li:ugcPost:1234567890")
            self.assertEqual(calls[1][1]["raw"],file.read_bytes())
            self.assertEqual(calls[2][1]["payload"]["commentary"],p["caption"])
            self.assertEqual(calls[2][1]["payload"]["content"]["media"]["id"],"urn:li:image:Photo55")

    def test_linkedin_upload_host_is_pinned(self):
        with tempfile.TemporaryDirectory() as root:
            jpg=Path(root)/"ad.jpg";jpg.write_bytes(b"\xff\xd8\xff")
            def fake(url,token,**kw):
                return (200,{"value":{"uploadUrl":"https://evil.invalid/private",
                    "image":"urn:li:image:Photo55"}},{})
            with self.assertRaisesRegex(social.ExtraSocialBlocked,"Unexpected LinkedIn"):
                social.linkedin_image_post(sample(),jpg,"TOKEN","urn:li:organization:123",requester=fake)

    def test_x_binds_exact_account_and_attaches_image(self):
        with tempfile.TemporaryDirectory() as root:
            jpg=Path(root)/"ad.jpg";jpg.write_bytes(b"\xff\xd8\xff"+b"0"*2500)
            calls=[]
            def fake(url,token,**kw):
                calls.append((url,kw))
                if url.endswith("/users/me"):return (200,{"data":{"id":"777"}},{})
                if url.endswith("/initialize"):return (202,{"data":{"id":"888"}},{})
                if url.endswith("/2/tweets"):return (201,{"data":{"id":"999"}},{})
                return (200,{}, {})
            ident=social.x_image_post(sample(),jpg,"TOKEN","777",requester=fake)
            self.assertEqual(ident,"999")
            self.assertEqual(len(calls),5)
            self.assertIn(b"\xff\xd8\xff",calls[2][1]["raw"])
            self.assertEqual(calls[4][1]["payload"]["media"]["media_ids"],["888"])
            self.assertIn(sample()["landing_url"],calls[4][1]["payload"]["text"])

    def test_x_wrong_token_identity_blocks_before_media_write(self):
        calls=[]
        def fake(url,token,**kw):
            calls.append(url);return (200,{"data":{"id":"999"}},{})
        with self.assertRaisesRegex(social.ExtraSocialBlocked,"not belong"):
            social.x_image_post(sample(),Path("not-used.jpg"),"TOKEN","777",requester=fake)
        self.assertEqual(len(calls),1)

    def test_no_publication_when_disabled_and_no_unapproved_x_spend(self):
        p=sample()
        with patch.object(social,"reserve_slot") as reserve:
            self.assertEqual(social.publish_network("linkedin",p,Path("x"),{},
                                                    gh_token="GHTOKEN"),"disabled")
            self.assertEqual(social.publish_network("x",p,Path("x"),{},
                                                    gh_token="GHTOKEN"),"disabled")
            reserve.assert_not_called()
            env={"TF_X_DIRECT_PUBLISH_ENABLED":"true","GITHUB_REPOSITORY":social.REPO,
                 "TF_X_USER_ACCESS_TOKEN":"A"*30,"TF_X_USER_ID":"777"}
            with self.assertRaisesRegex(social.ExtraSocialBlocked,"Paid X API"):
                social.publish_network("x",p,Path("x"),env,gh_token="GH")
            reserve.assert_not_called()

    def test_dedupe_ledger_is_per_network_per_mode_per_day(self):
        a=sample()
        self.assertNotEqual(social.ledger_path("linkedin",a),social.ledger_path("x",a))
        self.assertIn(a["date_ist"],social.ledger_path("linkedin",a))
        with self.assertRaises(social.ExtraSocialBlocked):
            social.ledger_path("instagram",a)

    def test_only_exact_same_campaign_crossposts_after_both_meta_networks(self):
        p=sample()
        def get(token,branch,path):
            return {"status":"api_accepted_published","campaign_id":p["campaign_id"]}
        with patch.object(social,"get_ledger",side_effect=get) as fetch:
            self.assertTrue(social.check_meta_success("GH",p))
            self.assertEqual(fetch.call_count,2)
        with patch.object(social,"get_ledger",side_effect=lambda *args:
                          {"status":"api_accepted_published","campaign_id":"different"}):
            with self.assertRaisesRegex(social.ExtraSocialBlocked,"both Meta"):
                social.check_meta_success("GH",p)

    def test_only_full_manifest_jpeg_and_verified_five_rank_records(self):
        p=sample()
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)/"campaign";(base/"post").mkdir(parents=True)
            (base/"post"/"post.json").write_text(json.dumps(p),encoding="utf8")
            (base/"post"/(p["campaign_id"]+".jpg")).write_bytes(b"\xff\xd8\xff"+b"0"*2000)
            (base/"plan.json").write_text(json.dumps({"campaign_id":p["campaign_id"]}),encoding="utf8")
            (base/"website-top5-render-qa.json").write_text(json.dumps({
                "visual_product_ids_by_rank":p["ranked_product_ids"]}),encoding="utf8")
            with patch.object(social,"check_report",return_value=p["ranked_product_ids"]) as qa:
                res=social.validate_source(base)
                self.assertEqual(res[0]["campaign_id"],p["campaign_id"])
                qa.assert_called_once()
            (base/"post"/(p["campaign_id"]+".jpg")).unlink()
            with self.assertRaisesRegex(social.ExtraSocialBlocked,"JPEG missing"):
                social.validate_source(base)

if __name__=="__main__":
    unittest.main()
