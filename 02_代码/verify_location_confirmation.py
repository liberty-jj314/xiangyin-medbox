"""未经确认的设备估计不得入县区统计；真实HTTP和临时SQLite，无付费调用。"""
import unittest
from unittest.mock import patch
import verify_review_features as base
class ConfirmedLocation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):base.Features.setUpClass.__func__(cls)
 @classmethod
 def tearDownClass(cls):base.Features.tearDownClass.__func__(cls)
 req=base.Features.req
 def total(self):return self.req('/api/stat?kind=real')['total']
 def test_a_unconfirmed_wrong_county_not_stored_or_counted(self):
  for source in ['granted','pending_confirmation','requesting','denied','timeout','boundary_uncertain']:
   before=self.total();d=self.req('/api/ask',{'question':'测试问题','city':'450107','location_status':source})
   self.assertTrue(d['ok']);row=self.req('/api/reviews?id='+d['record_id'])['record'];self.assertEqual(row['region'],'');self.assertEqual(self.total(),before)
 def test_b_confirmed_or_manual_county_and_source_preserved(self):
  for source in ['manual','confirmed']:
   before=self.total();d=self.req('/api/ask',{'question':'测试问题','city':'450110','location_status':source});self.assertTrue(d['ok'])
   row=self.req('/api/reviews?id='+d['record_id'])['record'];self.assertEqual(row['region'],'450110');self.assertEqual(row['location_status'],source);self.assertEqual(self.total(),before+1)
 def test_c_region_endpoint_returns_candidate_not_claimed_location(self):
  for lng,lat,code in [(108.305,22.833,'450107'),(108.366,22.854,'450102'),(108.277,23.157,'450110')]:
   d=self.req('/api/region',{'longitude':lng,'latitude':lat,'accuracy':5});self.assertEqual(d['city'],code);self.assertTrue(d['candidate_only']);self.assertEqual(d['location_status'],'candidate')
 def test_d_invalid_county_and_store_error_do_not_bypass_guard(self):
  self.assertEqual(self.app.location_meta({'city':'not-a-county','location_status':'manual'}),('','manual'))
  before=self.total()
  with patch.object(self.app.review_store,'answer',side_effect=OSError('temporary disk failure')):
   self.assertTrue(self.req('/api/ask',{'question':'测试问题','city':'450107','location_status':'granted'})['ok'])
  self.assertEqual(self.total(),before)
if __name__=='__main__':unittest.main(verbosity=2)
