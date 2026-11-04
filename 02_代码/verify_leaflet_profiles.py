from pathlib import Path
import json,tempfile,shutil,sys,importlib.util,unittest,copy
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parent.parent
class Profiles(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='leaflet_regression_');cls.root=Path(cls.temp.name);code=cls.root/'02_代码';data=cls.root/'01_资料';code.mkdir();data.mkdir()
  for name in ['asr_service.py','server.py','stat_store.py','voice_catalog.json','review_store.py','region_lookup.py','gx_counties.json']:shutil.copy2(SOURCE/'02_代码'/name,code/name)
  for name in ['药品数据.json','药品审核状态.json','实物药品资料.json']:shutil.copy2(SOURCE/'01_资料'/name,data/name)
  (data/'百度智能云密钥.txt').write_text('API Key: DUMMY\nSecret Key: DUMMY\n',encoding='utf-8')
  profiles=json.loads((data/'实物药品资料.json').read_text(encoding='utf-8'))['profiles']
  for profile in profiles:
   for image in profile['_source_images']:
    dest=data/image['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SOURCE/'01_资料'/image['path'],dest)
  shutil.copytree(SOURCE/'01_资料/方言录音',data/'方言录音')
  sys.path.insert(0,str(code));sp=importlib.util.spec_from_file_location('isolated_leaflet',code/'server.py');cls.a=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.a)
  cls.records=(data/'药品数据.json').read_text(encoding='utf-8');cls.a.load_llm_keys=lambda:dict(apikey='DUMMY',drugs=cls.records,model='mock',url='https://provider.invalid')
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def q(self,drug,question):return '【药盒上识别到的文字】'+drug+'\n【老人问的问题】'+question
 def ask(self,text):
  answer,kind,cite=self.a.do_llm(text);return answer,kind,self.a.select_voice_plan(text,answer,kind,cite)
 def test_exact_product_dose_restores_11(self):
  q=self.q('布洛芬缓释胶囊 国药准字H22026812 规格0.3克','一天吃几次？');answer,kind,voice=self.ask(q)
  self.assertEqual(kind,'');self.assertIn('成人一次1粒',answer);self.assertIn('整粒吞服',answer);self.assertEqual(voice['file'],'11_布洛芬_怎么吃.mp3')
 def test_pregnancy_question_uses_verified_prohibition_and_12(self):
  q=self.q('布洛芬缓释胶囊 国药准字H22026812','怀孕的人能吃这个药吗？');answer,kind,voice=self.ask(q);self.assertEqual(kind,'');self.assertIn('禁用',answer);self.assertEqual(voice['file'],'12_布洛芬_什么人不能吃.mp3')
 def test_old_product_dose_stays_blocked(self):
  answer,kind,voice=self.ask(self.q('布洛芬缓释胶囊 国药准字H20013062','一天吃几次？'));self.assertEqual(kind,'audit');self.assertIsNone(voice)
 def test_explicit_wrong_strength_is_not_normalized(self):
  answer,kind,voice=self.ask(self.q('布洛芬缓释胶囊 国药准字H22026812 规格3克','一天吃几次？'));self.assertEqual(kind,'product');self.assertIsNone(voice)
 def test_new_omeprazole_dose_and_time_limit(self):
  q=self.q('奥美拉唑肠溶胶囊 国药准字H20103717','一天吃几次？');answer,kind,voice=self.ask(q)
  self.assertEqual(kind,'');self.assertIn('一日1次',answer);self.assertIn('每24小时',answer);self.assertEqual(voice['file'],'14_奥美拉唑_怎么吃.mp3')
  answer,kind,voice=self.ask(self.q('奥美拉唑肠溶胶囊 国药准字H20103717','最多吃几天？'))
  self.assertIn('不得超过7天',answer);self.assertIn('两个月以内不得再次服用',answer);self.assertEqual(voice['file'],'15_奥美拉唑_最多吃几天.mp3')
 def test_otc_profile_cannot_answer_another_ulcer_regimen(self):
  answer,kind,voice=self.ask(self.q('奥美拉唑肠溶胶囊 国药准字H20103717','治疗胃溃疡一天吃几次？'));self.assertEqual(kind,'product');self.assertIsNone(voice)
 def test_numeric_overdose_does_not_get_routine_dose(self):
  answer,kind,voice=self.ask(self.q('布洛芬缓释胶囊 国药准字H22026812','一次吃10粒会怎么样？'));self.assertEqual(kind,'scope');self.assertFalse(self.a.DOSE_RE.search(answer));self.assertIsNone(voice)
 def test_generic_contraindication_does_not_shrink_to_pregnancy_only(self):
  a=self.a;records=a.load_drug_records(self.records);q=self.q('布洛芬缓释胶囊 国药准字H22026812','什么人不能吃？');record=a.resolve_product_record(q,a.find_drug_record(q,records));answer=record['禁忌'];cite=a.build_citation(q,[record],answer,'')
  self.assertIsNone(a.select_voice_plan(q,answer,'',cite));self.assertIn('肝病、肾病及心脏疾病',answer)
 def test_missing_source_photo_blocks_profile_selection(self):
  a=self.a;entries=a.verified_product_profiles();entry=next(e for e in entries if e['_profile_id']=='H22026812');p=Path(a.DATA_DIR)/entry['_source_images'][0]['path'];raw=p.read_bytes()
  try:
   p.write_bytes(b'changed source photo');q=self.q('布洛芬缓释胶囊 国药准字H22026812','怎么吃？');record=a.resolve_product_record(q,a.find_drug_record(q,a.load_drug_records(self.records)));self.assertNotEqual(record.get('_profile_id'),'H22026812')
  finally:p.write_bytes(raw)
 def test_gml_photo_distinguishes_severe_contraindication_and_caution(self):
  q=self.q('感冒灵颗粒','什么人不能吃？');a=self.a;rec=a.resolve_product_record(q,a.find_drug_record(q,a.load_drug_records(self.records)));self.assertEqual(rec['禁忌'],'严重肝肾功能不全者禁用。');self.assertIn('肝、肾功能不全者慎用',rec['注意事项']);self.assertIn('年老体弱者应在医师指导下服用',rec['特殊人群用药'])
 def test_new_gml_contraindication_recording(self):
  a=self.a;q=self.q('感冒灵颗粒 国药准字Z44021940','什么人不能吃？');record=a.resolve_product_record(q,a.find_drug_record(q,a.load_drug_records(self.records)));answer='[答] '+record['禁忌'];cite=a.build_citation(q,[record],answer,'');voice=a.select_voice_plan(q,answer,'',cite)
  self.assertEqual(voice['file'],'03_感冒灵_什么人不能吃.mp3');self.assertIn('严重',voice['text']);self.assertEqual(voice['answer_text'],answer)
 def test_new_omeprazole_indication_recording_and_legacy_scope(self):
  a=self.a;q=self.q('奥美拉唑肠溶胶囊 国药准字H20103717','是治什么的？');record=a.resolve_product_record(q,a.find_drug_record(q,a.load_drug_records(self.records)));answer='[答] '+record['适应症'];cite=a.build_citation(q,[record],answer,'');voice=a.select_voice_plan(q,answer,'',cite)
  self.assertEqual(voice['file'],'13_奥美拉唑_治什么.mp3');self.assertNotIn('溃疡',voice['text']);self.assertEqual(voice['answer_text'],answer)
  legacy=next(r for r in a.load_drug_records(self.records) if r['药名']=='奥美拉唑肠溶胶囊');q=self.q('奥美拉唑肠溶胶囊 国药准字H20065369','是治什么的？');cite=a.build_citation(q,[legacy],legacy['适应症'],'');self.assertIsNone(a.select_voice_plan(q,legacy['适应症'],'',cite))
 def test_substituted_audio_cannot_get_verified_plan(self):
  a=self.a;name='14_奥美拉唑_怎么吃.mp3';p=Path(a.DATA_DIR)/'方言录音'/name;raw=p.read_bytes()
  try:
   p.write_bytes(b'wrong recording');answer,kind,voice=self.ask(self.q('奥美拉唑肠溶胶囊 国药准字H20103717','一天吃几次？'));self.assertEqual(kind,'');self.assertIsNone(voice);self.assertFalse(a.verified_profile_audio(name))
  finally:p.write_bytes(raw)
if __name__=='__main__':unittest.main(verbosity=2)
