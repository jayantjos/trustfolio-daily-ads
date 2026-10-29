"""Offline security tests for isolated LinkedIn price-drift recovery."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from automation import linkedin_fresh_recovery_v1 as recovery
from automation.linkedin_x_crosspost_v1 import ExtraSocialBlocked

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src=Path(self.tmp.name)/"source"
        self.src.mkdir()
        self.dst=Path(self.tmp.name)/"new"
        self.original={"campaign_id":"tfauto-"+"a"*18,
                       "mode":"comparison","date_ist":"2026-10-29"}
        self.plan=dict(self.original,status="eligible")
        (self.src/"plan.json").write_text(json.dumps(self.plan))
        self.new=dict(self.original,campaign_id="tfauto-"+"b"*18)
        self.report={"visual_product_ids_by_rank":["1","2","3","4","5"]}

    def test_denies_missing_meta_ledger_token_before_render(self):
        with self.assertRaisesRegex(ExtraSocialBlocked,"authentication"):
            recovery.recover(self.src,self.dst,token="",run_key="12345",
                            host="200.234.47.87",user="scraperuser")
        self.assertFalse(self.dst.exists())

    def test_denies_overwriting_original_folder(self):
        with self.assertRaisesRegex(ExtraSocialBlocked,"overwrite"):
            recovery.recover(self.src,self.src,token="GH",run_key="12345",
                            host="200.234.47.87",user="scraperuser")

    def test_provenance_records_original_meta_not_falsified_new_id(self):
        def build(plan,**kwargs):
            dest=kwargs["folder"]
            (dest/"website-top5-render-qa.json").write_text(json.dumps(self.report))
            return self.new,dict(self.new), "https://media.trustfolio.in/trustfolio-auto/"+self.new["campaign_id"]+".jpg"
        with patch.object(recovery,"validate_source",return_value=(self.original,None,None)),\
             patch.object(recovery,"check_meta_success") as meta,\
             patch.object(recovery,"verify_fresh_snapshot") as audit:
            result=recovery.recover(self.src,self.dst,token="GH",run_key="12345",
                            host="200.234.47.87",user="scraperuser",builder=build)
        meta.assert_called_once_with("GH",self.original)
        audit.assert_called_once()
        self.assertEqual(result["campaign_id"],self.new["campaign_id"])
        data=json.loads((self.dst/"post"/"linkedin-recovery-source.json").read_text())
        self.assertEqual(data["meta_original"]["campaign_id"],self.original["campaign_id"])
        self.assertEqual(data["new_campaign_id"],self.new["campaign_id"])
        self.assertEqual(json.loads((self.src/"plan.json").read_text()),self.plan)

    def test_denies_wrong_mode_after_rebuild(self):
        def build(plan,**kwargs):
            changed=dict(self.new,mode="budget")
            return changed,changed,"https://unused.invalid"
        with patch.object(recovery,"validate_source",return_value=(self.original,None,None)),\
             patch.object(recovery,"check_meta_success"):
            with self.assertRaisesRegex(ExtraSocialBlocked,"date/mode"):
                recovery.recover(self.src,self.dst,token="GH",run_key="12345",
                    host="200.234.47.87",user="scraperuser",builder=build)

    def test_denies_unconfirmed_meta_before_network_or_filesystem_mutation(self):
        with patch.object(recovery,"validate_source",return_value=(self.original,None,None)),\
             patch.object(recovery,"check_meta_success",side_effect=ExtraSocialBlocked("Missing Meta receipt")):
            with self.assertRaisesRegex(ExtraSocialBlocked,"Missing Meta receipt"):
                recovery.recover(self.src,self.dst,token="GH",run_key="12345",
                    host="200.234.47.87",user="scraperuser")
        self.assertFalse(self.dst.exists())

if __name__=="__main__":
    unittest.main()
