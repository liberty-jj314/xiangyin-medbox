"""真实项目目录的隔离录音匹配回归；不调用供应商。"""
import unittest,json,re,threading,urllib.request,urllib.error,urllib.parse
from pathlib import Path
import verify_leaflet_profiles as base

class AudioMapping(unittest.TestCase):
 @classmethod
 def setUpClass(cls):base.Profiles.setUpClass.__func__(cls)
 @classmethod
 def tearDownClass(cls):base.Profiles.tearDownClass.__func__(cls)
 q=base.Profiles.q
 def plan(self,ocr,question):
  a=self.a;q=self.q(ocr,question);q=a.normalize_product_names(q)
  rec=a.resolve_product_record(q,a.find_drug_record(q,a.load_drug_records(self.records)))
  if not rec or a.check_audit_block(q,'',rec):return None
  fields=a.resolved_field_topics(q,rec)
  if not fields:return None
  prefix='说明书原文：' if '用法用量' in fields or '自我用药期限' in fields else '[答] '
  answer=prefix+'；'.join('【'+f+'】'+rec[f] for f in fields)
  return a.select_voice_plan(q,answer,'',a.build_citation(q,[rec],answer,''))
 def test_all_verified_recordings_map_to_correct_drug_and_field(self):
  cases=[('感冒灵颗粒','治什么病？','01'),('感冒灵颗粒','一天吃几次？','02'),('感冒灵颗粒','什么人不能吃？','03'),
   ('硝苯地平缓释片(II) 诺贝华乐 20mg','治什么病？','04'),('硝苯地平缓释片(II) 诺贝华乐 20mg','一天吃几次？','05'),('硝苯地平缓释片(II) 诺贝华乐 20mg','有什么副作用？','06'),
   ('盐酸二甲双胍片 诺贝华乐 0.25g','治什么病？','07'),('盐酸二甲双胍片 诺贝华乐 0.25g','一次吃多少？','08'),('盐酸二甲双胍片 诺贝华乐 0.25g','老人能吃吗？','09'),
   ('布洛芬缓释胶囊 国药准字H22026812','治什么病？','10'),('布洛芬缓释胶囊 国药准字H22026812','一天吃几次？','11'),('布洛芬缓释胶囊 国药准字H22026812','孕妇能吃吗？','12'),
   ('奥美拉唑肠溶胶囊 国药准字H20103717','治什么病？','13'),('奥美拉唑肠溶胶囊 国药准字H20103717','一天吃几次？','14'),('奥美拉唑肠溶胶囊 国药准字H20103717','最多吃几天？','15')]
  for ocr,q,prefix in cases:
   with self.subTest(prefix=prefix):
    plan=self.plan(ocr,q);self.assertIsNotNone(plan);self.assertTrue(plan['file'].startswith(prefix+'_'))
 def test_elderly_clip_not_used_for_other_populations(self):
  ocr='盐酸二甲双胍片 诺贝华乐 0.25g'
  for q in ['孕妇能吃吗？','儿童能吃吗？','老人和孕妇能吃吗？','老人和小孩能吃吗？']:
   with self.subTest(q=q):self.assertIsNone(self.plan(ocr,q))
 def test_numeric_age_can_get_the_elderly_clip(self):
  for q in ['我75岁能吃吗？','八十岁的能吃吗？']:
   plan=self.plan('盐酸二甲双胍片 诺贝华乐 0.25g',q);self.assertIsNotNone(plan);self.assertTrue(plan['file'].startswith('09_'))
 def test_pregnancy_clip_not_used_for_mixed_population(self):
  for q in ['孕妇和儿童能吃吗？','老人和孕妇能吃吗？']:
   self.assertIsNone(self.plan('布洛芬缓释胶囊 国药准字H22026812',q))
 def test_initial_dose_clip_does_not_answer_maximum_or_adjustment(self):
  for q in ['最大剂量是多少？','一天最多吃几片？','要怎么加量？']:
   with self.subTest(q=q):self.assertIsNone(self.plan('盐酸二甲双胍片 诺贝华乐 0.25g',q))
 def test_meal_question_only_uses_a_clip_with_meal_information(self):
  p=self.plan('盐酸二甲双胍片 诺贝华乐 0.25g','饭前还是饭后吃？');self.assertIsNotNone(p);self.assertTrue(p['file'].startswith('08_'))
  for ocr in ['硝苯地平缓释片(II) 诺贝华乐 20mg','布洛芬缓释胶囊 国药准字H22026812','感冒灵颗粒']:
   with self.subTest(ocr=ocr):self.assertIsNone(self.plan(ocr,'饭前还是饭后吃？'))
 def test_wrong_product_cannot_use_new_recordings(self):
  for ocr in ['硝苯地平片 国药准字H37022634','硝苯地平缓释片(I) 诺贝华乐 20mg','盐酸二甲双胍片 国药准字H20023371 规格0.85g']:
   with self.subTest(ocr=ocr):self.assertIsNone(self.plan(ocr,'一天吃几次？'))
 def test_new_files_have_one_current_approval_binding(self):
  catalog=json.loads((Path(self.a.BASE)/'voice_catalog.json').read_text(encoding='utf-8'))
  for prefix,approval in [('07','H35020664'),('05','H20083275'),('08','H35020664'),('09','H35020664')]:
   entries=[e for e in catalog if e['file'].startswith(prefix+'_')];self.assertEqual(len(entries),1);self.assertEqual(entries[0]['approval'],approval);self.assertTrue(self.a.verified_profile_audio(entries[0]['file']))
 def test_frontend_transcripts_match_current_catalog(self):
  html=(base.SOURCE/'02_代码/index.html').read_text(encoding='utf-8')
  transcripts=json.loads(re.search(r'var VOICE_TRANSCRIPTS = (\{.*?\});',html,re.S).group(1))
  catalog=json.loads((Path(self.a.BASE)/'voice_catalog.json').read_text(encoding='utf-8'))
  for entry in catalog:
   with self.subTest(file=entry['file']):self.assertEqual(transcripts.get(entry['file']),entry['text'])
 def test_changed_audio_invalidates_plan(self):
  p=Path(self.a.DATA_DIR)/'方言录音/05_硝苯地平_怎么吃.mp3';raw=p.read_bytes()
  try:
   p.write_bytes(b'wrong audio');self.assertIsNone(self.plan('硝苯地平缓释片(II) 诺贝华乐 20mg','一天吃几次？'));self.assertFalse(self.a.verified_profile_audio(p.name))
  finally:p.write_bytes(raw)
 def test_real_http_audio_route_checks_current_binding(self):
  server=self.a.ThreadingHTTPServer(('127.0.0.1',0),self.a.Handler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  origin='http://127.0.0.1:'+str(server.server_address[1])+'/audio/'
  p=Path(self.a.DATA_DIR)/'方言录音/05_硝苯地平_怎么吃.mp3';raw=p.read_bytes()
  try:
   for name in ['07_二甲双胍_治什么.mp3','05_硝苯地平_怎么吃.mp3','08_二甲双胍_吃多少.mp3','09_二甲双胍_老人能吃吗.mp3']:
    with opener.open(origin+urllib.parse.quote(name),timeout=5) as response:
     self.assertEqual(response.status,200);self.assertEqual(response.read(),(Path(self.a.DATA_DIR)/'方言录音'/name).read_bytes())
   p.write_bytes(b'substituted')
   with self.assertRaises(urllib.error.HTTPError) as cm:opener.open(origin+urllib.parse.quote(p.name),timeout=5)
   self.assertEqual(cm.exception.code,403)
  finally:p.write_bytes(raw);server.shutdown();server.server_close()
 def test_changed_source_invalidates_plan(self):
  p=Path(self.a.DATA_DIR)/'实物药品资料.json';raw=p.read_bytes()
  try:
   data=json.loads(raw);entry=next(e for e in data['profiles'] if e['_profile_id']=='H35020664');entry['用法用量']+=' changed';p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');self.assertIsNone(self.plan('盐酸二甲双胍片 诺贝华乐 0.25g','一天吃几次？'))
  finally:p.write_bytes(raw)

 def test_new07_wrong_product_or_audio_cannot_play(self):
  self.assertIsNone(self.plan('盐酸二甲双胍片 国药准字H20023371 规格0.85g','治什么病？'))
  p=Path(self.a.DATA_DIR)/'方言录音/07_二甲双胍_治什么.mp3';raw=p.read_bytes()
  try:
   p.write_bytes(b'substituted');self.assertIsNone(self.plan('盐酸二甲双胍片 诺贝华乐 0.25g','治什么病？'));self.assertFalse(self.a.verified_profile_audio(p.name))
  finally:p.write_bytes(raw)

if __name__=='__main__':unittest.main(verbosity=2)
