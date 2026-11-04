"""两盒新实物身份、说明书、旧录音隔离测试；虚拟密钥，禁止调用模型。"""
import unittest
from unittest.mock import patch
import verify_leaflet_profiles as base

class TwoProducts(base.Profiles):
 def test_nifedipine_ii_exact_approval_and_dose(self):
  answer,kind,voice=self.ask(self.q('硝苯地平缓释片（Ⅱ） 国药准字H20083275 规格20mg','一天吃几次？'))
  self.assertEqual(kind,'');self.assertIn('每天2次',answer);self.assertIn('每次口服20mg',answer);self.assertIn('勿嚼碎',answer);self.assertEqual(voice['file'],'05_硝苯地平_怎么吃.mp3')
 def test_nifedipine_front_and_unicode(self):
  for name in ['硝苯地平缓释片(II)','硝苯地平缓释片（Ⅱ）','硝苯地平缓释片 ( II )']:
   with self.subTest(name=name):
    answer,kind,_=self.ask(self.q(name+' 诺贝华乐 20mg×10片×4板','这个药一天吃几次？'));self.assertEqual(kind,'');self.assertIn('每天2次',answer)
 def test_nifedipine_incomplete_form_cannot_borrow_ii(self):
  for name in ['硝苯地平缓释片','硝苯地平缓释片(I)','硝苯地平缓释片(III)','硝苯地平控释片']:
   with self.subTest(name=name):
    answer,kind,voice=self.ask(self.q(name+' 诺贝华乐 20mg 国药准字H20083275','一天吃几次？'));self.assertTrue(kind);self.assertIsNone(voice);self.assertNotIn('每次口服20mg',answer)
 def test_front_identity_needs_brand_and_strength(self):
  for ocr in ['硝苯地平缓释片(II) 20mg','硝苯地平缓释片(II) 诺贝华乐','盐酸二甲双胍片 诺贝华乐','盐酸二甲双胍片 诺贝华乐 0.5g']:
   with self.subTest(ocr=ocr):
    _,kind,_=self.ask(self.q(ocr,'一天吃几次？'));self.assertTrue(kind)
 def test_metformin_new_strength_dose(self):
  for ocr in ['盐酸二甲双胍片 国药准字H35020664 规格0.25g','盐酸二甲双胍片 诺贝华乐 0.25g×48片']:
   answer,kind,voice=self.ask(self.q(ocr,'一次吃多少，一天吃几次？'));self.assertEqual(kind,'');self.assertIn('一日2—3次',answer);self.assertIn('餐中服用',answer);self.assertIn('不超过8片',answer);self.assertNotIn('0.85',answer);self.assertEqual(voice['file'],'08_二甲双胍_吃多少.mp3')
 def test_metformin_age_restriction_comes_from_new_leaflet(self):
  answer,kind,voice=self.ask(self.q('盐酸二甲双胍片 诺贝华乐 0.25g','老人能吃吗？'));self.assertEqual(kind,'');self.assertIn('70岁以上',answer);self.assertNotIn('80岁',answer);self.assertEqual(voice['file'],'09_二甲双胍_老人能吃吗.mp3')
 def test_new_profiles_do_not_call_generator(self):
  with patch.object(self.a.urllib.request,'urlopen',side_effect=AssertionError('model must not be called')):
   for ocr in ['硝苯地平缓释片(II) 诺贝华乐 20mg','盐酸二甲双胍片 诺贝华乐 0.25g']:
    for question in ['治什么病？','有什么副作用？','什么人不能吃？','老人能吃吗？','要注意什么？','一天吃几次？']:
     with self.subTest(ocr=ocr,question=question):
      answer,kind,_=self.ask(self.q(ocr,question));self.assertEqual(kind,'');self.assertTrue(answer.startswith('说明书原文：'))
 def test_wrong_approval_and_strength_still_blocked(self):
  for ocr in ['盐酸二甲双胍片 诺贝华乐 国药准字H20023371 规格0.25g','盐酸二甲双胍片 国药准字H35020664 规格0.85g','硝苯地平缓释片(II) 国药准字H20083275 规格30mg','硝苯地平缓释片(II) 诺贝华乐 20mg 国药准字H99999999']:
   with self.subTest(ocr=ocr):
    _,kind,voice=self.ask(self.q(ocr,'一天吃几次？'));self.assertTrue(kind);self.assertIsNone(voice)
 def test_other_photo_cannot_be_identified_from_question(self):
  _,kind,_=self.ask(self.q('未知药盒','盐酸二甲双胍片一天吃几次？'));self.assertTrue(kind)

 def test_actual_ocr_confusions_need_cross_evidence(self):
  cases = [('硝苯地平缓释片()\nNifedipine Sustained-release Tablets(Il\n诺贝华乐\n20mgX10片X4板', True),
           ('硝苯地平缓释片() 诺贝华乐 20mg', False),
           ('硝苯地平缓释片()\nNifedipine Sustained-release Tablets(III)\n诺贝华乐 20mg', False),
           ('盐酸二甲双胍片 NOBE诺页华乐 0.25g', True),
           ('盐酸二甲双胍片 诺页华乐 0.25g', False)]
  for ocr, allowed in cases:
   with self.subTest(ocr=ocr):
    answer,kind,_=self.ask(self.q(ocr,'一天吃几次？'));self.assertEqual(not bool(kind), allowed)

if __name__=='__main__':unittest.main(verbosity=2)
