"""MVP真实do_llm路径回归；供应商仅回放所问栏目，绝不调用云接口。"""
import unittest,json,io,csv,re,copy,importlib.util
from pathlib import Path
from unittest.mock import patch
import verify_leaflet_profiles as base
class MVP(unittest.TestCase):
 @classmethod
 def setUpClass(cls):base.Profiles.setUpClass.__func__(cls)
 @classmethod
 def tearDownClass(cls):base.Profiles.tearDownClass.__func__(cls)
 q=base.Profiles.q
 def ask(self,ocr,text):
  a=self.a;q=self.q(ocr,text);normalized=a.normalize_product_names(q);rec=a.resolve_product_record(normalized,a.find_drug_record(normalized,a.load_drug_records(self.records)))
  def provider(request,*args,**kwargs):
   self.assertEqual(request.full_url,'https://provider.invalid/chat/completions')
   answer='[答] '+'；'.join(rec.get(f,'') for f in a.resolved_field_topics(normalized,rec))
   return io.BytesIO(json.dumps({'choices':[{'message':{'content':answer}}]},ensure_ascii=False).encode())
  with patch.object(a.urllib.request,'urlopen',provider):answer,kind,cite=a.do_llm(q)
  return answer,kind,a.select_voice_plan(q,answer,kind,cite)
 def test_csv_15_through_real_question_gates(self):
  with (base.SOURCE/'01_资料/测试集.csv').open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))[:15]
  for row in rows:
   approval=re.search(r'[HZ]\d{8}',row['出处（核对用）']).group();p=next(p for p in self.a.verified_product_profiles() if p['_profile_id']==approval)
   for suffix in [' 国药准字'+approval,'']:
    with self.subTest(id=row['题号'],approval=bool(suffix)):
     answer,kind,voice=self.ask(p['药名']+' '+p.get('品牌','')+' '+p['规格']+suffix,row['问题']);self.assertEqual(kind,'');self.assertIsNotNone(voice);self.assertEqual(voice['file'],row['对应录音文件']);self.assertEqual(int(row['题号']),int(voice['file'][:2]))
 def test_nif_aliases_in_question_do_not_change_identity(self):
  for name in ['硝苯地平缓释片Ⅱ','硝苯地平缓释片II','硝苯地平缓释片 II','硝苯地平缓释片(II)','硝苯地平缓释片（Ⅱ）','硝苯地平缓释片2','硝苯地平缓释片二','这个药']:
   with self.subTest(name=name):
    _,kind,voice=self.ask('硝苯地平缓释片(II) 诺贝华乐 20mg 国药准字H20083275',name+'治什么？');self.assertEqual(kind,'');self.assertEqual(voice['file'],'04_硝苯地平_治什么.mp3')
 def test_wrong_nif_forms_are_still_refused(self):
  for name in ['硝苯地平缓释片(I)','硝苯地平缓释片(III)','硝苯地平控释片','硝苯地平缓释片']:
   with self.subTest(name=name):
    _,kind,voice=self.ask(name+' 诺贝华乐 20mg 国药准字H20083275','一天几次？');self.assertTrue(kind);self.assertIsNone(voice)
 def test_overdose_chinese_and_digits_no_dose_or_voice(self):
  for q in ['一次吃十粒会怎么样？','一次吃10粒会怎么样？','一次吃二十粒会怎么样？','误服了一把怎么办？','吃了十粒怎么办？','一次吞十粒会怎样？','吃多了怎么办？','一次吃十粒','能不能多吃两粒？']:
   with self.subTest(q=q):
    answer,kind,voice=self.ask('布洛芬缓释胶囊 恒医森 0.3克 国药准字H22026812',q);self.assertEqual(kind,'scope');self.assertIsNone(voice);self.assertIsNone(self.a.DOSE_RE.search(answer))
 def test_risky_person_dose_never_uses_routine_dose(self):
  for ocr in ['布洛芬缓释胶囊 恒医森 0.3克 国药准字H22026812','盐酸二甲双胍片 诺贝华乐 0.25g 国药准字H35020664']:
   for q in ['小孩怎么吃？','我6岁，一次吃几粒？','我六岁，一次吃几粒？','孕妇一天吃几次？','哺乳期一次几粒？','老人怎么吃？','我有肝病，怎么吃？','我肾不好，一天吃几次？']:
    with self.subTest(ocr=ocr,q=q):
     answer,kind,voice=self.ask(ocr,q);self.assertEqual(kind,'safety');self.assertIsNone(voice);self.assertIsNone(self.a.DOSE_RE.search(answer))
 def test_unconfirmed_identity_asks_for_side_not_assumed_strength(self):
  for ocr in ['奥美拉唑肠溶胶囊 益君康 27粒','布洛芬缓释胶囊 恒医森','奥美拉唑肠溶胶囊 其他品牌 20mg']:
   with self.subTest(ocr=ocr):
    answer,kind,voice=self.ask(ocr,'一天几次？');self.assertTrue(kind);self.assertIsNone(voice);self.assertNotIn('一次1粒',answer)
 def test_stop_by_approval_and_field_overrides_current_profile(self):
  audit=copy.deepcopy(self.a.load_audit());audit['紧急停用']['批准文号']['H22026812']=['用法用量']
  with patch.object(self.a,'load_audit',lambda:audit):
   answer,kind,voice=self.ask('布洛芬缓释胶囊 恒医森 0.3克 国药准字H22026812','一天几次？');self.assertEqual(kind,'audit');self.assertIsNone(voice);self.assertFalse(self.a.verified_profile_audio('11_布洛芬_怎么吃.mp3'));self.assertTrue(self.a.emergency_audio_stopped('11_布洛芬_怎么吃.mp3'))
 def test_stop_file_global_and_malformed_rules_fail_closed(self):
  original=copy.deepcopy(self.a.load_audit())
  for changes in [dict(全部=True,批准文号={},录音文件=[]),dict(全部=False,批准文号={},录音文件=['11_布洛芬_怎么吃.mp3']),None]:
   data=copy.deepcopy(original);data['紧急停用']=changes
   with patch.object(self.a,'load_audit',lambda:data):
    self.assertTrue(self.a.emergency_audio_stopped('11_布洛芬_怎么吃.mp3'));self.assertFalse(self.a.verified_profile_audio('11_布洛芬_怎么吃.mp3'))
 def test_same_build_wrong_project_not_reused(self):
  path=base.SOURCE/'02_代码/ensure_service.py';sp=importlib.util.spec_from_file_location('instance_check',path);starter=importlib.util.module_from_spec(sp);sp.loader.exec_module(starter)
  class Reply(io.BytesIO):pass
  class Opener:
   def open(self,*a,**k):return Reply(json.dumps(dict(build=starter.BUILD,project_id='another-copy')).encode())
  with patch.object(starter.urllib.request,'build_opener',return_value=Opener()):self.assertEqual(starter.probe(1),2)
 def test_course_limit_not_mistaken_for_extra_dose(self):
  for q in ['最多吃几天？','最多能吃几天？','这个药最多吃多久？']:
   with self.subTest(q=q):
    answer,kind,voice=self.ask('奥美拉唑肠溶胶囊 益君康 20mg 国药准字H20103717',q);self.assertEqual(kind,'');self.assertIn('7天',answer);self.assertEqual(voice['file'],'15_奥美拉唑_最多吃几天.mp3')

if __name__=='__main__':unittest.main(verbosity=2)
