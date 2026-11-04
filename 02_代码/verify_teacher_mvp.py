"""五项MVP修复回归：使用临时资料，不调用付费接口或真实数据库。"""
import unittest,json,io,socket
from unittest.mock import patch
import verify_leaflet_profiles as base
class TeacherMVP(unittest.TestCase):
 @classmethod
 def setUpClass(cls):base.Profiles.setUpClass.__func__(cls)
 @classmethod
 def tearDownClass(cls):base.Profiles.tearDownClass.__func__(cls)
 def question(self,p,q):return '【药盒上识别到的文字】'+p['药名']+' '+p['规格']+' 国药准字'+p['_profile_id']+'\n【老人问的问题】'+q
 def refuse(self,p,q):
  full=self.question(p,q)
  with patch.object(self.a.urllib.request,'urlopen',side_effect=AssertionError('No cloud request allowed')) as cloud:
   answer,kind,cite=self.a.do_llm(full)
  cloud.assert_not_called();self.assertTrue(kind,q);self.assertIsNone(cite);self.assertIsNone(self.a.select_voice_plan(full,answer,kind,cite))
 def test_quantity_variants_never_play_routine_dose(self):
  for p in self.a.verified_product_profiles():
   for q in ['一次吃10包行不行？','一次吃十包行不行？','一次吃10颗行不行？','吃一整瓶行不行？','一整盒都吃了怎么办？','每天吃十支可以吗？','一次服用10袋可以吗？','一口气吞一把行吗？','一次吃10粒行不行？']:
    with self.subTest(drug=p['药名'],q=q):self.refuse(p,q)
 def test_twenty_cross_drug_pairs_and_unknown_drugs(self):
  profiles=self.a.verified_product_profiles()
  for p in profiles:
   for other in profiles:
    if p['_profile_id']!=other['_profile_id']:
     with self.subTest(photo=p['药名'],ask=other['药名']):self.refuse(p,other['药名']+'怎么吃？')
   for q in ['阿莫西林怎么吃？','请问阿莫西林一天吃几次？','头孢克肟胶囊怎么服用？','阿托伐他汀一天吃几片？','阿莫西林胶囊治什么？','阿司匹林能吃吗？','什么人不能吃阿司匹林？','阿司匹林治什么？','孕妇能吃阿莫西林吗？','孕妇能吃阿司匹林吗？','这个药和阿莫西林能一起吃吗？']:
    with self.subTest(drug=p['药名'],q=q):self.refuse(p,q)
 def test_normal_references_and_dose_queries_unchanged(self):
  for p in self.a.verified_product_profiles():
   for q in ['这个药怎么吃？','一天吃几次？',p['药名']+'怎么吃？','最多吃几天？','这个药饭前还是饭后服用？',p.get('品牌','')+p['药名']+'怎么吃？']:
    with self.subTest(drug=p['药名'],q=q):self.assertFalse(self.a.question_identity_issue(self.question(p,q),p))
  for q in ['一次10克的药袋','每袋装10克','最多吃几天？']:
   self.assertFalse(self.a.unsafe_quantity_question(q),q)
 def test_unicode_hostname_and_real_port_conflicts(self):
  error=UnicodeDecodeError('utf-8',b'\xff',0,1,'simulated GBK hostname')
  with patch.object(self.a.socket,'getfqdn',side_effect=error):
   srv=self.a.ThreadingHTTPServer(('127.0.0.1',0),self.a.Handler)
  try:
   self.assertEqual(srv.server_name,'127.0.0.1');self.assertGreater(srv.server_port,0)
   busy=socket.socket()
   try:
    if hasattr(socket,"SO_EXCLUSIVEADDRUSE"):busy.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    busy.bind(("127.0.0.1",0));busy.listen()
    with self.assertRaises(OSError):self.a.ThreadingHTTPServer(busy.getsockname(),self.a.Handler)
   finally:busy.close()
  finally:srv.server_close()
 def handler(self,raw,header=None):
  h=self.a.Handler.__new__(self.a.Handler);h.path='/api/ask';h.headers={'Content-Length':str(len(raw))} if header is None else header;h.rfile=io.BytesIO(raw);h.close_connection=False;return h
 def test_request_reader_rejects_before_body_allocation(self):
  class NoRead:
   def read(self,*args):raise AssertionError('must reject before reading')
  for n in ['-1','999999999','abc']:
   h=self.handler(b'',{'Content-Length':n});h.rfile=NoRead()
   with self.subTest(length=n),self.assertRaises(ValueError):h.read_json_body()
   self.assertTrue(h.close_connection)
  h=self.handler(b'',{'Content-Length':'2','Transfer-Encoding':'chunked'});h.rfile=NoRead()
  with self.assertRaises(ValueError):h.read_json_body()
  h=self.handler(json.dumps({'question':'这个药怎么吃？'}).encode());self.assertIn('question',h.read_json_body())
 def test_long_and_blank_questions_never_call_model_or_store(self):
  for q in ['', '  ', '【药盒上识别到的文字】感冒灵颗粒\n【老人问的问题】', '问'*501, '【药盒上识别到的文字】'+'字'*12000+'【老人问的问题】怎么吃？']:
   raw=json.dumps({'question':q}).encode();h=self.handler(raw);responses=[];h.send_json=lambda data,**kw:responses.append(data)
   with patch.object(self.a,'do_llm',side_effect=AssertionError('no model')) as model,patch.object(self.a.review_store,'answer',side_effect=AssertionError('no database')) as store:
    h.handle_ask()
   model.assert_not_called();store.assert_not_called();self.assertFalse(responses[-1]['ok'])
if __name__=='__main__':unittest.main(verbosity=2)
