"""No-network regression tests for exact Meta source discovery."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from automation.linkedin_find_published_source_v1 import meta_identity,source_candidates,locate,NoCrossHostAuthRedirect
from urllib.request import Request

def record(network,cid="tfauto-"+"a"*18):
    return {"network":network,"mode":"budget","campaign_id":cid,"status":"api_accepted_published"}

class TestSourceDiscovery(unittest.TestCase):
    def test_signed_redirect_does_not_leak_github_token(self):
        request=Request("https://api.github.com/repos/owner/repo/actions/artifacts/1/zip",
                        headers={"Authorization":"Bearer SECRET"})
        redirected=NoCrossHostAuthRedirect().redirect_request(
            request,None,302,"Found",{},
            "https://pipelines.actions.githubusercontent.com/signed.zip?sig=opaque")
        self.assertNotIn("authorization", {k.lower() for k in redirected.headers})
        self.assertNotIn("authorization", {k.lower() for k in redirected.unredirected_hdrs})


    def test_requires_both_matching_meta_campaign_ids(self):
        def fetch(path,token):
            network="instagram" if "instagram" in path else "facebook"
            obj=record(network, "tfauto-"+("a" if network=="instagram" else "b")*18)
            return {"content":base64.b64encode(json.dumps(obj).encode()).decode()}
        with self.assertRaisesRegex(ValueError,"Different Meta campaign"):
            meta_identity("budget","2026-10-29","GH",fetch=fetch)

    def test_source_candidates_skip_push_and_skipped_crons(self):
        def fetch(path,token):
            return {"workflow_runs":[
                {"id":1,"name":"TrustFolio automated Instagram campaigns","event":"push","head_branch":"main","conclusion":"success"},
                {"id":2,"name":"TrustFolio automated Instagram campaigns","event":"schedule","head_branch":"main","conclusion":"success"}]}
        self.assertEqual([x["id"] for x in source_candidates("GH",fetch=fetch)],[2])

    def test_fails_closed_if_no_matching_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("automation.linkedin_find_published_source_v1.meta_identity",return_value="tfauto-"+"a"*18),\
                 patch("automation.linkedin_find_published_source_v1.source_candidates",return_value=[{"id":123}]):
                def fetch(path,token,**kwargs):
                    return {"artifacts":[]}
                with self.assertRaisesRegex(ValueError,"No exact approved"):
                    locate("budget","2026-10-29","GH",Path(tmp)/"source",fetch=fetch)
            self.assertFalse((Path(tmp)/"source").exists())

if __name__=="__main__":unittest.main()
