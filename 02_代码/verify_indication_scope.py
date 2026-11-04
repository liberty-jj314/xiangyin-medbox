"""统一五药用途边界：真实do_llm入口，不允许越界题触发模型。"""
from pathlib import Path
import unittest
from unittest.mock import patch
import verify_leaflet_profiles as base
class Indications(unittest.TestCase):
 @classmethod
 def setUpClass(cls):base.Profiles.setUpClass.__func__(cls)
 @classmethod
 def tearDownClass(cls):base.Profiles.tearDownClass.__func__(cls)
 q=base.Profiles.q
 def ask_no_provider(self,profile,question):
  ocr=profile['药名']+' '+profile.get('品牌','')+' '+profile['规格']+' 国药准字'+profile['_profile_id'];q=self.q(ocr,question)
  with patch.object(self.a.urllib.request,'urlopen',side_effect=AssertionError('outside indication must not call model')) as provider:
   answer,kind,cite=self.a.do_llm(q)
  provider.assert_not_called();self.assertTrue(kind);self.assertIsNone(cite);self.assertIsNone(self.a.select_voice_plan(q,answer,kind,cite));return answer,kind
 def test_all_five_cancer_weight_and_unknown_disease_stop_before_model(self):
  for p in self.a.verified_product_profiles():
   for q in ['这个药能治癌症吗？','这个药能减肥吗？','这个药能治疗失眠吗？']:
    with self.subTest(drug=p['药名'],q=q):self.assertEqual(self.ask_no_provider(p,q)[1],'scope')
 def test_gml_three_reported_questions(self):
  p=next(p for p in self.a.verified_product_profiles() if p['_profile_id']=='Z44021940')
  for q in ['感冒灵能治癌症吗？','感冒灵治高血压吗？','感冒灵能减肥吗？','感冒灵对癌症有作用吗？','感冒灵能治感冒和失眠吗？','感冒灵治失眠吗？']:
   with self.subTest(q=q):self.assertEqual(self.ask_no_provider(p,q)[1],'scope')
 def test_personal_condition_not_mislabelled_as_treatment(self):
  for p in self.a.verified_product_profiles():
   for q in ['有高血压的人能吃这个药吗？','高血压能吃这个药吗？','有糖尿病的人能用这个药吗？','癌症患者可以服用这个药吗？']:
    with self.subTest(drug=p['药名'],q=q):
     answer,kind=self.ask_no_provider(p,q);self.assertEqual(kind,'safety');self.assertIn('是否适合您',answer)
 def test_supported_uses_have_source_evidence_and_are_not_rejected(self):
  examples={'Z44021940':['感冒灵能治疗感冒吗？','感冒灵能缓解感冒引起的头痛和发热吗？','感冒灵能缓解流鼻涕吗？','感冒灵是治什么的？'],
   'H20083275':['这个药能治高血压吗？','能治疗心绞痛吗？','这个药治什么病？'],
   'H35020664':['能治2型糖尿病吗？','这个药治什么？'],
   'H22026812':['布洛芬能缓解偏头痛吗？','这个药能缓解感冒引起的发热吗？','能退烧吗？','能止痛吗？'],
   'H20103717':['益君康奥美拉唑能缓解反酸烧心吗？','这盒益君康奥美拉唑肠溶胶囊是治什么的？']}
  for p in self.a.verified_product_profiles():
   for q in examples[p['_profile_id']]:
    with self.subTest(drug=p['药名'],q=q):self.assertIsNone(self.a.indication_boundary(q,p))
 def test_non_indication_queries_remain_untouched(self):
  for p in self.a.verified_product_profiles():
   for q in ['一天吃几次？','有什么副作用？','治疗期间有什么不良反应？','吃了会头晕头痛吗？','最多吃几天？','孕妇或哺乳期的人能吃布洛芬吗？','怀孕的人能吃这个药吗？','老人能吃这个药吗？']:
    with self.subTest(drug=p['药名'],q=q):self.assertIsNone(self.a.indication_boundary(q,p))
 def test_specific_cross_uses_blocked_consistently(self):
  qs={'Z44021940':'能降血压吗？','H20083275':'能降血糖吗？','H35020664':'能治1型糖尿病吗？','H22026812':'能治疗感冒吗？','H20103717':'治疗胃溃疡一天吃几次？'}
  for p in self.a.verified_product_profiles():
   with self.subTest(drug=p['药名']):self.assertTrue(self.ask_no_provider(p,qs[p['_profile_id']])[1])
 def test_changed_source_does_not_keep_an_old_permission(self):
  p=dict(next(p for p in self.a.verified_product_profiles() if p['_profile_id']=='H20083275'));p['适应症']='未完成核对';self.assertEqual(self.a.indication_boundary('能治高血压吗？',p)[1],'audit')
if __name__=='__main__':unittest.main(verbosity=2)
