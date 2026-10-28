"""Buffer Free automatic LinkedIn/X post scheduling regression tests. No network."""
import base64
from datetime import datetime,timezone
import unittest
from unittest.mock import Mock,patch
from automation import buffer_free_crosspost_v1 as buffer

def manifest():
    return {"campaign_id":"tfauto-"+"a"*18, "mode":"budget",
            "category":"laptops","brand":"","budget_inr":55000,
            "landing_url":"https://www.trustfolio.in/category/laptops/products?budget=55000",
            "caption":"TrustFolio website-ranked Top 5 laptops under ₹55,000. Details https://www.trustfolio.in/category/laptops/products?budget=55000"}

class TestBufferFree(unittest.TestCase):
    def test_free_buffer_uses_same_approved_jpeg_linkedin_caption_and_x_url(self):
        p=manifest(); calls=[]
        def graphql(token,query,variables=None):
            calls.append((query,variables))
            if "account {" in query:
                return {"account":{"organizations":[{"id":"org-123"}]}}
            if "channels(input" in query:
                return {"channels":[{"id":"linkedin-channel","name":"TrustFolio","service":"linkedin"},
                                    {"id":"twitter-channel","name":"Trustfolio","service":"twitter"}]}
            payload=variables["input"]
            return {"createPost":{"__typename":"PostActionSuccess","post":{
                    "id":"post-123","text":payload["text"],"dueAt":payload["dueAt"]}}}
        link="https://media.trustfolio.in/trustfolio-auto/"+p["campaign_id"]+".jpg"
        result=buffer.submit_to_buffer("token-of-adequate-length",p,"linkedin",
                    "linkedin-channel",link,now=datetime(2026,10,28,4,1,tzinfo=timezone.utc),
                    graphql_request=graphql)
        self.assertEqual(result["id"],"post-123")
        opts=calls[-1][1]["input"]
        self.assertEqual(opts["text"],buffer.linkedin_post_text(p))
        self.assertNotEqual(opts["text"],p["caption"])
        self.assertIn(p["landing_url"],opts["text"])
        self.assertNotIn("Instagram",opts["text"])
        self.assertEqual(opts["assets"],[{"image":{"url":link}}])
        self.assertEqual(opts["dueAt"],"2026-10-28T04:06:00.000Z")
        self.assertEqual(opts["mode"],"customScheduled")
        calls.clear()
        buffer.submit_to_buffer("token-of-adequate-length",p,"x",
                    "twitter-channel",link,graphql_request=graphql)
        self.assertIn(p["landing_url"],calls[-1][1]["input"]["text"])
        self.assertLessEqual(len(calls[-1][1]["input"]["text"]),280)

    def test_only_correct_connected_channel_is_accepted(self):
        def graphql(token,query,variables=None):
            if "account {" in query:return {"account":{"organizations":[{"id":"org_1"}]}}
            return {"channels":[{"id":"target-x","name":"Unknown","service":"twitter"}]}
        with self.assertRaisesRegex(buffer.BufferBlocked,"not the expected social"):
            buffer.verify_buffer_channel("key","linkedin","target-x",graphql_request=graphql)
        with self.assertRaisesRegex(buffer.BufferBlocked,"not uniquely"):
            buffer.verify_buffer_channel("key","x","wrong-channel",graphql_request=graphql)

    def test_disabled_default_never_reserves_nor_calls_api(self):
        with patch.object(buffer,"reserve_slot") as lock,patch.object(buffer,"submit_to_buffer") as post:
            value=buffer.schedule_if_enabled("x",manifest(),"https://unused.invalid/x",{},
                       gh_token="secret")
            self.assertEqual(value,"disabled")
            lock.assert_not_called()
            post.assert_not_called()

    def test_shared_per_mode_network_duplicate_lock(self):
        reserve=Mock(return_value=None)
        submit=Mock()
        env={"GITHUB_REPOSITORY":buffer.REPO,"TF_BUFFER_FREE_PUBLISH_ENABLED":"true",
             "TF_BUFFER_API_KEY":"A"*25,"TF_BUFFER_LINKEDIN_CHANNEL_ID":"li"}
        result=buffer.schedule_if_enabled("linkedin",manifest(),"https://media.trustfolio.in/x",
                                  env,gh_token="GH",reserve=reserve,do_submit=submit)
        self.assertEqual(result,"duplicate")
        submit.assert_not_called()

    def test_no_accepted_response_means_no_false_success(self):
        p=manifest()
        def graphql(token,query,variables=None):
            if "account {" in query:return {"account":{"organizations":[{"id":"org_1"}]}}
            if "channels(input" in query:return {"channels":[{"id":"123","service":"linkedin"}]}
            return {"createPost":{"__typename":"MutationError","message":"Queue full"}}
        with self.assertRaisesRegex(buffer.BufferBlocked,"rejected createPost"):
            buffer.submit_to_buffer("A"*25,p,"linkedin","123",
                 "https://media.trustfolio.in/trustfolio-auto/"+p["campaign_id"]+".jpg",
                 graphql_request=graphql)

    def test_noncanonical_media_url_refused_before_any_api_call(self):
        f=Mock()
        with self.assertRaisesRegex(buffer.BufferBlocked,"Media URL"):
            buffer.submit_to_buffer("A"*25,manifest(),"x","x-id",
                                    "https://untrusted.example.com/wrong.jpg",
                                    graphql_request=f)
        f.assert_not_called()

    def test_ledger_records_scheduled_not_published(self):
        p=manifest()
        encoded=base64.b64encode(__import__("json").dumps({
            "status":"reserved","campaign_id":p["campaign_id"]}).encode()).decode()
        calls=[]
        def github(token,path,method="GET",data=None):
            calls.append((path,method,data))
            if method=="GET":return {"content":encoded,"sha":"fileSHA"}
            return {"content":{}}
        with patch.object(buffer,"_github",side_effect=github):
            buffer.complete_scheduled("GH","extra-social-ledger/day/linkedin-mode-budget.json",
                                    p,{"id":"buffer-post-7","network":"linkedin","due_at":"2026-10-28T00:00:00Z"})
        status=__import__("json").loads(base64.b64decode(calls[-1][2]["content"]))
        self.assertEqual(status["status"],"buffer_api_accepted_scheduled")
        self.assertNotIn("api_accepted_published",str(status))

if __name__=="__main__":unittest.main()
