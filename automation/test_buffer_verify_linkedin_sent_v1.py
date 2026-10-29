"""Offline tests: never confuse scheduled with Buffer sent."""
import base64,json,unittest
from unittest.mock import Mock,patch
from automation import buffer_verify_linkedin_sent_v1 as v
from automation.buffer_free_crosspost_v1 import BufferBlocked

class TestBufferSent(unittest.TestCase):
    def test_scheduled_is_not_published(self):
        def fake(token,q,vars):
            return {"post":{"id":"abc123","channelId":"li-1","status":"scheduled","sentAt":None}}
        self.assertEqual(v.inspect_provider("KEY","abc123","li-1",request=fake)["status"],"scheduled")

    def test_wrong_channel_or_missing_sent_time_is_blocked(self):
        with self.assertRaisesRegex(BufferBlocked,"identity/channel"):
            v.inspect_provider("KEY","abc123","li-1",request=lambda *x: {
                "post":{"id":"abc123","channelId":"li-other","status":"sent","sentAt":"now"}})
        with self.assertRaisesRegex(BufferBlocked,"timestamp"):
            v.inspect_provider("KEY","abc123","li-1",request=lambda *x: {
                "post":{"id":"abc123","channelId":"li-1","status":"sent","sentAt":None}})

    def test_sent_updates_only_matching_locked_ledger(self):
        path="extra-social-ledger/2026-10-29/linkedin-mode-budget.json"
        old={"network":"linkedin","mode":"budget","status":"buffer_api_accepted_scheduled",
             "campaign_id":"tfauto-"+"a"*18,"buffer_post_id":"abc123"}
        calls=[]
        def github(token,path,method="GET",data=None):
            calls.append((method,data))
            return {"content":base64.b64encode(json.dumps(old).encode()).decode(),"sha":"sameSHA"}
        def fake(token,q,vars):
            return {"post":{"id":"abc123","channelId":"li-1","status":"sent",
                            "sentAt":"2026-10-29T15:10:00Z",
                            "externalLink":"https://www.linkedin.com/feed/update/urn:li:activity:123"}}
        with patch.object(v,"get_ledger",return_value=old):
            result=v.reconcile("budget","2026-10-29","KEY","GH","li-1",
                               request=fake,github=github)
        self.assertEqual(result,"sent")
        self.assertEqual(len([x for x in calls if x[0]=="PUT"]),1)
        updated=json.loads(base64.b64decode(calls[-1][1]["content"]))
        self.assertEqual(updated["status"],"buffer_confirmed_sent")
        self.assertEqual(updated["buffer_post_id"],"abc123")

    def test_scheduled_provider_keeps_ledger_unchanged(self):
        old={"status":"buffer_api_accepted_scheduled","buffer_post_id":"abc123"}
        with patch.object(v,"get_ledger",return_value=old):
            github=Mock()
            result=v.reconcile("budget","2026-10-29","KEY","GH","li-1",
                request=lambda *x:{"post":{"id":"abc123","channelId":"li-1","status":"scheduled"}},github=github)
        self.assertEqual(result,"scheduled")
        github.assert_not_called()

if __name__=="__main__":unittest.main()
