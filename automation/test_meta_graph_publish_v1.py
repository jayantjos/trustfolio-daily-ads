"""Fail-closed offline tests for official Meta Graph publishing bridge.

No test reaches Meta, GitHub API, social accounts, or real website.
"""
from datetime import date
import os
import unittest
from unittest.mock import patch

from automation import meta_graph_publish_v1 as m


def qa_manifest():
    return {
        "status":"ready_for_publishing_gate",
        "publication_status":"not_published",
        "instagram_account":"trustfolio3",
        "source_renderer":"master_template_renderer_html_v4",
        "geometry_errors":[],
        "size":[1080,1350],
        "ranked_product_ids":["p1","p2","p3","p4","p5"],
        "campaign_id":"tfauto-"+"b"*18,
        "landing_url":"https://www.trustfolio.in/category/smart-phones/products?budget=15000",
        "caption":"✨ Best Smartphones Under ₹15,000. "
                  "Compare the real Top 5 website picks; latest prices can change. "
                  "https://play.google.com/store/apps/details?id=com.trustfolio.app",
    }


def enabled_env():
    return {
        "TF_META_DIRECT_PUBLISH_ENABLED":"true",
        "TF_AUTO_POST_ENABLED":"false",
        "GITHUB_REPOSITORY":"jayantjos/trustfolio-daily-ads",
        "TF_META_PAGE_ACCESS_TOKEN":"a"*30,
        "GITHUB_TOKEN":"g"*35,
        "TF_META_PAGE_ID":m.EXPECTED_PAGE_ID,
        "TF_META_START_DATE":"2020-01-01",
        "TF_META_POST_NETWORKS":"instagram,facebook",
        "TF_META_MAX_POSTS_PER_DAY_PER_NETWORK":"2",
    }


from automation.meta_readonly_preflight import run_read_only


class DirectMetaSafetyTests(unittest.TestCase):
    def test_readonly_connection_check_requires_page_token(self):
        with self.assertRaisesRegex(m.PublishingBlocked,"secret missing"):
            run_read_only({})

    def test_readonly_connection_check_never_attempts_publication(self):
        with patch("automation.meta_readonly_preflight.confirm_page_token_type",
                    return_value=m.EXPECTED_PAGE_ID) as page_token, \
             patch("automation.meta_readonly_preflight.confirm_page_identity",
                    return_value="1780000000123") as identity, \
             patch("automation.meta_readonly_preflight.check_instagram_quota",
                    return_value={"quota_usage":1,"quota_total":50,"quota_duration":86400}) as quota, \
             patch.object(m,"publish_instagram") as ig, \
             patch.object(m,"publish_facebook") as fb:
            out=run_read_only({"TF_META_PAGE_ACCESS_TOKEN":"a"*35,
                                "TF_META_PAGE_ID":m.EXPECTED_PAGE_ID})
            self.assertFalse(out["publication_attempted"])
            self.assertEqual(out["instagram_username_verified"],"trustfolio3")
            self.assertEqual(out["instagram_quota"]["quota_total"],50)
            page_token.assert_called_once()
            identity.assert_called_once()
            quota.assert_called_once()
            ig.assert_not_called()
            fb.assert_not_called()


    def test_disabled_by_default(self):
        with self.assertRaisesRegex(m.PublishingBlocked,"OFF"):
            m.load_env(env={})

    def test_missing_token_fails_without_meta_write(self):
        env=enabled_env()
        env.pop("TF_META_PAGE_ACCESS_TOKEN")
        with self.assertRaisesRegex(m.PublishingBlocked,"Missing Meta"):
            m.load_env(env=env)

    def test_wrong_repostarget_and_facebook_page_blocked(self):
        bad=enabled_env()
        bad["TF_META_PAGE_ID"]="123"
        with self.assertRaisesRegex(m.PublishingBlocked,"Page ID"):
            m.load_env(env=bad)
        bad=enabled_env()
        bad["GITHUB_REPOSITORY"]="other/repo"
        with self.assertRaisesRegex(m.PublishingBlocked,"Wrong GitHub repository"):
            m.load_env(env=bad)

    def test_existing_metricool_api_not_allowed_together(self):
        e=enabled_env()
        e["TF_AUTO_POST_ENABLED"]="true"
        with self.assertRaisesRegex(m.PublishingBlocked,"cannot both"):
            m.load_env(env=e)

    def test_early_crossposting_date_does_not_reuse_old_metricool_queue(self):
        e=enabled_env()
        e.pop("TF_META_START_DATE")
        with patch.object(m,"datetime") as dt:
            dt.now.return_value.date.return_value=date(2026,10,17)
            with self.assertRaisesRegex(m.PublishingBlocked,"2026-10-21"):
                m.load_env(env=e)

    def test_account_or_product_identity_invalid_fails_closed(self):
        for field,value in (
            ("instagram_account","joshierjayant"),
            ("source_renderer","unverified"),
            ("publication_status","published"),
            ("size",[1024,1536]),
            ("geometry_errors",["overlap"]),
            ("ranked_product_ids",["p1"]*5),
            ("landing_url","https://evil.example.com/"),
        ):
            with self.subTest(field=field):
                item=qa_manifest()
                item[field]=value
                with self.assertRaises(m.PublishingBlocked):
                    m.validate_approved_manifest(item)
        self.assertEqual(m.validate_approved_manifest(qa_manifest()),
                         "tfauto-"+"b"*18)

    def test_access_token_type_must_be_actual_page_not_user(self):
        cfg={"version":"v25.0","page_id":m.EXPECTED_PAGE_ID,"page_token":"secret"}
        with patch.object(m,"_graph",return_value={"id":m.EXPECTED_PAGE_ID,
                                                   "name":"Trustfolio"}) as graph:
            self.assertEqual(m.confirm_page_token_type(cfg),m.EXPECTED_PAGE_ID)
            self.assertEqual(graph.call_args.args[1],"me")
            self.assertEqual(graph.call_args.kwargs["fields"],"id,name")
        with patch.object(m,"_graph",return_value={"id":"29193850746900249",
                                                   "name":"Facebook User"}):
            with self.assertRaisesRegex(m.PublishingBlocked,"not the Trustfolio Page token"):
                m.confirm_page_token_type(cfg)

    def test_facebook_identity_must_link_right_instagram(self):
        cfg={"version":"v25.0","page_id":m.EXPECTED_PAGE_ID,"page_token":"secret"}
        def good(version,path,token,**kw):
            if path==m.EXPECTED_PAGE_ID:
                return {"id":m.EXPECTED_PAGE_ID,"name":"Trustfolio",
                        "instagram_business_account":{"id":"179999992399"}}
            return {"id":"179999992399","username":"trustfolio3"}
        with patch.object(m,"_graph",side_effect=good):
            self.assertEqual(m.confirm_page_identity(cfg),"179999992399")
        def wrong(version,path,token,**kw):
            if path==m.EXPECTED_PAGE_ID:
                return {"id":m.EXPECTED_PAGE_ID,
                        "instagram_business_account":{"id":"179999992399"}}
            return {"id":"179999992399","username":"wrongprofile"}
        with patch.object(m,"_graph",side_effect=wrong):
            with self.assertRaisesRegex(m.PublishingBlocked,"not @trustfolio3"):
                m.confirm_page_identity(cfg)

    def test_dynamic_publishing_quota_from_actual_graph_response(self):
        cfg={"version":"v25.0","page_token":"secret"}
        response={"data":[{"quota_usage":15,"config":{
            "quota_total":50,"quota_duration":86400}}]}
        with patch.object(m,"_graph",return_value=response) as graph:
            status=m.check_instagram_quota(cfg,"1791")
            self.assertEqual(status["quota_total"],50)
            self.assertEqual(status["quota_usage"],15)
            self.assertEqual(status["quota_duration"],86400)
            self.assertEqual(graph.call_args.kwargs["fields"],"quota_usage,config")
        response={"data":[{"quota_usage":50,"config":{
            "quota_total":50,"quota_duration":86400}}]}
        with patch.object(m,"_graph",return_value=response):
            with self.assertRaisesRegex(m.PublishingBlocked,"limit reached"):
                m.check_instagram_quota(cfg,"1791")
        for response in (
            {"data":[{"quota_usage":1}]},
            {"data":[{"quota_usage":1,"config":{"quota_total":50}}]},
            {"data":[]},
        ):
            with self.subTest(response=response),patch.object(m,"_graph",return_value=response):
                with self.assertRaisesRegex(m.PublishingBlocked,"unreadable"):
                    m.check_instagram_quota(cfg,"1791")

    def test_ledger_already_reserved_never_posts_twice(self):
        cfg={"github_token":"gh","today":"2026-10-27"}
        key="tfauto-"+"a"*18
        with patch.object(m,"ensure_ledger"),patch.object(
            m,"ledger_list",return_value=[
                {"name":"instagram-"+key+".json"}
            ]),patch.object(m,"_github") as h:
            self.assertIsNone(m.reserve(cfg,"instagram",key,"https://media.trustfolio.in",max_posts=2))
            h.assert_not_called()

    def test_daily_cap_blocks_network_after_two(self):
        cfg={"github_token":"gh","today":"2026-10-27"}
        with patch.object(m,"ensure_ledger"),patch.object(
            m,"ledger_list",return_value=[
                {"name":"instagram-tfauto-"+"a"*18+".json"},
                {"name":"instagram-tfauto-"+"b"*18+".json"},
            ]),patch.object(m,"_github") as h:
            with self.assertRaisesRegex(m.PublishingBlocked,"cap already reached"):
                m.reserve(cfg,"instagram","tfauto-"+"c"*18,
                          "https://media.trustfolio.in/trustfolio-auto/x.jpg",max_posts=2)
            h.assert_not_called()

    def test_facebook_publish_uses_only_page_photo_endpoint(self):
        cfg={"version":"v25.0","page_id":m.EXPECTED_PAGE_ID,"page_token":"t"}
        with patch.object(m,"_graph",return_value={"id":"123456"} ) as graph, \
             patch.object(m,"record_status",return_value="newsha") as r:
            output=m.publish_facebook(cfg,"https://example.com/product.jpg",
                       "TrustFolio linked budget list","facebook","tfauto-"+"c"*18,"a"*40)
            self.assertEqual(output["status"],"api_accepted_published")
            self.assertEqual(graph.call_args.args[1],m.EXPECTED_PAGE_ID+"/photos")
            self.assertEqual(graph.call_args.kwargs["post"]["published"],"true")
            r.assert_called_once()

    def test_instagram_container_and_media_publish_sequence(self):
        cfg={"version":"v25.0","page_token":"t"}
        calls=[]
        def graph(version,path,token,**kw):
            calls.append(path)
            if path=="1791/media": return {"id":"1000"}
            if path=="1000": return {"status_code":"FINISHED"}
            if path=="1791/media_publish": return {"id":"2000"}
            raise RuntimeError("Unexpected Graph path")
        with patch.object(m,"_graph",side_effect=graph), \
             patch.object(m,"record_status",return_value="b"*40):
            output=m.publish_instagram(cfg,"1791","https://example.com/test.jpg",
                        "caption","instagram","tfauto-"+"c"*18,"a"*40)
        self.assertEqual(calls,["1791/media","1000","1791/media_publish"])
        self.assertEqual(output["media_id"],"2000")

    def test_approved_media_byte_check_before_any_graph_calls(self):
        with patch.object(m,"_check_media",side_effect=m.PublishingBlocked("SHA mismatch")), \
             patch.object(m,"confirm_page_identity") as identity:
            with patch.object(m,"load_env",return_value={"networks":()}):
                with self.assertRaisesRegex(m.PublishingBlocked,"SHA mismatch"):
                    m.publish_verified(qa_manifest(),"https://media.trustfolio.in/trustfolio-auto/test.jpg",
                                       "approved.jpg")
            identity.assert_not_called()

    def test_no_media_write_without_enabled_token(self):
        with patch.object(m,"_check_media") as media, \
             patch.object(m,"confirm_page_identity") as identity:
            with self.assertRaisesRegex(m.PublishingBlocked,"OFF"):
                m.publish_verified(qa_manifest(),
                    "https://media.trustfolio.in/trustfolio-auto/t.jpg","local.jpg",env={})
            media.assert_not_called()
            identity.assert_not_called()


if __name__=="__main__":
    unittest.main()
