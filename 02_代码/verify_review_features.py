"""隔离临时数据库和HTTP；不调用真实OCR/模型，不修改用户数据库。"""
import base64
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parent
class Features(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='xy_review_');cls.root=Path(cls.temp.name);cls.code=cls.root/'02_代码';cls.data=cls.root/'01_资料';cls.code.mkdir();cls.data.mkdir()
  for name in ['asr_service.py','server.py','stat_store.py','review_store.py','region_lookup.py','gx_counties.json','index.html','admin.html','phone.html','voice_catalog.json','recorder.js','ui_presentation.js','sw.js','icon-192.png','icon-512.png']:shutil.copy2(SOURCE/name,cls.code/name)
  for name in ['药品数据.json','药品审核状态.json']:shutil.copy2(SOURCE.parent/'01_资料'/name,cls.data/name)
  (cls.data/'百度智能云密钥.txt').write_text('API Key: DUMMY\nSecret Key: DUMMY\n',encoding='utf-8')
  sys.path.insert(0,str(cls.code));sp=importlib.util.spec_from_file_location('review_test_server',cls.code/'server.py');cls.app=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.app)
  cls.app.do_ocr=lambda b:['感冒灵颗粒','国药准字Z44021940']
  cls.app.save_ocr_log=lambda lines:None
  cls.app.do_llm=lambda q:('[答] 严重肝肾功能不全者禁用。','',None)
  cls.app.select_voice_plan=lambda *a:None
  cls.http=cls.app.ThreadingHTTPServer(('127.0.0.1',0),cls.app.Handler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.url='http://127.0.0.1:'+str(cls.http.server_address[1])
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
 def req(self,path,payload=None,origin=None):
  headers={'Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  r=urllib.request.Request(self.url+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
  with urllib.request.urlopen(r,timeout=10) as response:return json.loads(response.read())
 def new_answer(self):
  r=self.req('/api/ocr',{'image':base64.b64encode(b'photo').decode(),'location_status':'denied'})
  q='【药盒上识别到的文字】感冒灵颗粒\n国药准字Z44021940\n【老人问的问题】什么人不能吃？'
  a=self.req('/api/ask',{'question':q,'recognition_id':r['recognition_id'],'location_status':'denied'})
  return a
 def test_01_ocr_only_record(self):
  r=self.req('/api/ocr',{'image':base64.b64encode(b'photo').decode()});self.assertTrue(r['recognition_id'])
  d=self.req('/api/reviews?status=unasked');self.assertTrue(any(x['id']==r['recognition_id'] for x in d['rows']))
 def test_02_denied_location_still_gets_answer_and_stores_it(self):
  a=self.new_answer();self.assertTrue(a['ok']);r=self.req('/api/reviews?id='+a['record_id'])['record'];self.assertEqual(r['answer'],a['answer']);self.assertEqual(r['location_status'],'denied');self.assertEqual(r['region'],'');self.assertIn('感冒灵',r['ocr_text']);self.assertEqual(r['question'],'什么人不能吃？')
 def test_03_review_persists_history_and_stale_edit_rejected(self):
  a=self.new_answer();key=a['record_id'];p=dict(id=key,review_status='rejected',review_note='需要补充核查 <script>bad()</script>',revision=0)
  saved=self.req('/api/reviews',p)['record'];self.assertEqual(saved['revision'],1);self.assertEqual(saved['review_status'],'rejected')
  self.assertEqual(self.req('/api/reviews?id='+key)['record']['review_note'],p['review_note']);self.assertEqual(len(saved['history']),1)
  with self.assertRaises(urllib.error.HTTPError) as error:self.req('/api/reviews',p)
  self.assertEqual(error.exception.code,409)
 def test_04_simulated_stats_do_not_enter_review_database(self):
  before=self.req('/api/reviews')['total'];self.req('/api/stat?kind=demo&days=7');self.assertEqual(self.req('/api/reviews')['total'],before)
 def test_05_outside_and_invalid_location(self):
  self.assertEqual(self.req('/api/region',{'longitude':116.4,'latitude':39.9,'accuracy':20})['location_status'],'outside')
  self.assertEqual(self.req('/api/region',{'longitude':108.36,'latitude':22.82,'accuracy':50000})['location_status'],'low_accuracy')
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/region',{'longitude':'bad','latitude':22,'accuracy':10})
 def test_06_guangxi_location_matches_existing_boundary(self):
  d=self.req('/api/region',{'longitude':108.366,'latitude':22.817,'accuracy':30});self.assertTrue(d['city'].startswith('4501'));self.assertEqual(d['location_status'],'candidate');self.assertTrue(d['candidate_only'])
 def test_07_storage_failure_does_not_block_ocr_or_answer(self):
  with patch.object(self.app.review_store,'recognition',side_effect=OSError('disk unavailable')):
   r=self.req('/api/ocr',{'image':base64.b64encode(b'photo').decode()});self.assertTrue(r['ok']);self.assertFalse(r['recognition_id'])
  with patch.object(self.app.review_store,'answer',side_effect=OSError('disk unavailable')):
   r=self.req('/api/ask',{'question':'测试问题'});self.assertTrue(r['ok']);self.assertFalse(r['record_id'])
 def test_08_local_only_access_and_cross_origin_edit(self):
  with patch.object(self.app.Handler,'is_local_request',return_value=False):
   for route in ['/api/reviews','/admin']:
    with self.assertRaises(urllib.error.HTTPError) as error:self.req(route)
    self.assertEqual(error.exception.code,403)
  with self.assertRaises(urllib.error.HTTPError) as error:self.req('/api/reviews',dict(id='x',review_status='approved',revision=0),origin='https://other.example')
  self.assertEqual(error.exception.code,403)
 def test_09_multiple_questions_remain_separate(self):
  store=self.app.review_store;rid=store.recognition('药盒','感冒灵颗粒');ids=[store.answer(rid,'药盒','感冒灵颗粒',q,'回答','answered','',None) for q in ['问题一','问题二']];self.assertNotEqual(*ids);self.assertEqual(store.detail(ids[1])['question'],'问题二')
 def test_10_empty_and_filtered_pagination(self):
  self.assertEqual(self.req('/api/reviews?search=absolutely-no-such-record')['total'],0)
  self.assertEqual(self.req('/api/reviews?status=rejected')['rows'][0]['review_status'],'rejected')
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/reviews?status=invalid')
 def test_11_no_coordinate_or_image_columns(self):
  with self.app.review_store.connect() as c:
   cols={r[1] for r in c.execute('PRAGMA table_info(answer_record)')}
  self.assertFalse(cols.intersection({'latitude','longitude','image','audio','ip','device_id'}))
 def test_12_public_region_options_are_whitelisted(self):
  result=self.req('/api/regions');counties=[county for city in result['cities'] for county in city['counties']]
  self.assertEqual({c['code'] for c in counties},set(self.app.stat_store.COUNTY_CODES));self.assertEqual(next(c['name'] for c in counties if c['code']=='450110'),'武鸣区')
 def test_13_manual_source_is_preserved_and_invalid_source_drops_county(self):
  self.assertEqual(self.app.location_meta({'city':'450110','location_status':'manual'}),('450110','manual'))
  self.assertEqual(self.app.location_meta({'city':'450110','location_status':'denied'}),('','denied'))
  self.assertEqual(self.app.location_meta({'city':'450110','location_status':'invented'}),('','unavailable'))
  self.assertEqual(self.app.location_meta({'city':'999999','location_status':'manual'}),('','manual'))
 def test_14_manual_region_in_actual_answer_record(self):
  rec=self.req('/api/ocr',{'image':base64.b64encode(b'photo').decode(),'city':'450110','location_status':'manual'})
  question='【药盒上识别到的文字】感冒灵颗粒\n国药准字Z44021940\n【老人问的问题】什么人不能吃？'
  answer=self.req('/api/ask',{'question':question,'city':'450110','location_status':'manual','recognition_id':rec['recognition_id']})
  saved=self.req('/api/reviews?id='+answer['record_id'])['record'];self.assertEqual(saved['region'],'450110');self.assertEqual(saved['location_status'],'manual')

if __name__=='__main__':unittest.main(verbosity=2)
