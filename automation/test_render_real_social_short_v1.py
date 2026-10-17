"""Offline regression checks for production QA-only short-form video renderer."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageDraw

from automation.render_real_social_short_v1 import (
    W,H,make_scene,render,fit_lines,font
)


def manifest(mode="budget"):
    key="tfauto-"+"a"*18
    return {
        "campaign_id":key,"mode":mode,"category":"smart-phones","budget_inr":15000,
        "brand":"Samsung" if mode=="brand_budget" else "",
        "instagram_account":"trustfolio3","network":"instagram",
        "source_renderer":"master_template_renderer_html_v4",
        "ranked_product_ids":["p1","p2","p3","p4","p5"],
        "size":[1080,1350],"geometry_errors":[],
        "status":"ready_for_publishing_gate",
        "publication_status":"not_published",
        "landing_url":"https://www.trustfolio.in/category/smart-phones/products?budget=15000",
        "caption":"Real website ranked Top Five under budget. Compare genuine products "
                  "and source prices at TrustFolio. "
                  "https://play.google.com/store/apps/details?id=com.trustfolio.app",
        "output_jpg":key+".jpg",
    }


class RealVideoRenderingTests(unittest.TestCase):
    def test_all_ad_modes_generate_1080x1920_storyboards(self):
        photo=Image.new("RGB",(1080,1350),(47,21,98))
        for mode in ("budget","brand_budget","comparison"):
            with self.subTest(mode=mode):
                frame=make_scene(manifest(mode),photo,0)
                self.assertEqual(frame.size,(W,H))
                self.assertEqual(frame.mode,"RGB")
                self.assertNotEqual(frame.getpixel((400,300)),frame.getpixel((20,1800)))

    def test_storyboard_has_four_different_real_image_views(self):
        photo=Image.new("RGB",(1080,1350),(23,83,123))
        m=manifest()
        # Full poster and focused details must produce visually distinct scenes.
        signatures=[]
        for i in range(4):
            scene=make_scene(m,photo,i)
            signatures.append(scene.tobytes()[::5001][:5000])
        self.assertEqual(len(set(signatures)),4)

    def test_reject_overlong_headline_instead_of_silent_clipping(self):
        image=Image.new("RGB",(W,H))
        draw=ImageDraw.Draw(image)
        with self.assertRaisesRegex(ValueError,"does not fit"):
            fit_lines(draw,"extravagantlylongcategory "*40,font(48,True),500,max_lines=2)

    def test_bad_ranked_product_source_never_generates_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            m=manifest()
            p=root/"post.json"
            p.write_text(json.dumps(m),"utf8")
            report={
                "source":"live_trustfolio_website_api",
                "source_product_ids_by_rank":m["ranked_product_ids"],
                "visual_product_ids_by_rank":["different","p2","p3","p4","p5"],
                "campaign_mode":m["mode"],"visual_geometry_errors":[],
                "dimensions":[1024,1536],
                "renderer":"master_template_renderer_html_v4",
            }
            q=root/"report.json";q.write_text(json.dumps(report),"utf8")
            jpg=root/m["output_jpg"]
            Image.new("RGB",(1080,1350)).save(jpg,format="JPEG")
            with self.assertRaisesRegex(ValueError,"website/render/top-five QA mismatch"):
                render(p,jpg,q,root/"video.mp4")
            self.assertFalse((root/"video.mp4").exists())

    def test_no_unapproved_brand_in_comparison_or_source_mutation(self):
        assert manifest("comparison")["brand"]==""
        assert manifest("brand_budget")["brand"]=="Samsung"
        source=Path(__file__).with_name("render_real_social_short_v1.py").read_text("utf8")
        self.assertIn("validate_approved_manifest(post)",source)
        self.assertIn("ranked_product_ids",source)
        self.assertIn("publishing_enabled",source)
        self.assertIn('"YOUTUBE_UPLOAD_ATTEMPTED=NO"',source)
        self.assertNotIn("videos.insert(",source)


if __name__=="__main__":
    unittest.main()
