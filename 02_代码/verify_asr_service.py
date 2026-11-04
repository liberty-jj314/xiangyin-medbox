"""离线验证真实HTTP入口与ASR请求，不调用付费接口。"""
import base64,io,json,threading,unittest,urllib.error,urllib.request,wave
from pathlib import Path
from unittest.mock import patch
import asr_service as a

class Tests(unittest.TestCase):
 def call(self,response,audio=b'ab',fmt='wav'):
  handle=io.BytesIO(json.dumps(response).encode())
  with patch.object(a.urllib.request,'urlopen',return_value=handle) as mock:
   text=a.transcribe(audio,fmt,16000,'test-key','https://dashscope.aliyuncs.com/compatible-mode/v1')
   request=mock.call_args.args[0];body=json.loads(request.data)
  return text,body
 def test_native_response(self):
  text,body=self.call({'output':{'text':'这个药一天吃几次？'}})
  self.assertEqual(text,'这个药一天吃几次？');self.assertEqual(body['model'],a.MODEL)
  self.assertEqual(body['parameters']['sample_rate'],'16000')
  self.assertEqual(len(body['input']['messages']),1)
 def test_no_transcription_correction(self):
  self.assertEqual(self.call({'output':{'text':'原始错字'}})[0],'原始错字')
 def test_pcm_wrapper(self):
  _,b=self.call({'output':{'text':'吃几次'}},b'\0\0'*100,'pcm')
  data=base64.b64decode(b['input']['messages'][0]['content'][0]['input_audio']['data'].split(',')[1])
  with wave.open(io.BytesIO(data)) as w:self.assertEqual((w.getnchannels(),w.getframerate(),w.getnframes()),(1,16000,100))
 def test_empty_response(self):
  with self.assertRaises(a.RecognitionError):self.call({'output':{'text':' '}})
 def test_bad_response(self):
  with self.assertRaises(a.RecognitionError):self.call({'output':{}})
 def test_endpoint_guard(self):
  for url in ['http://dashscope.aliyuncs.com','https://example.com','https://dashscope.aliyuncs.com.evil.com','https://key@dashscope.aliyuncs.com']:
   with self.assertRaises(a.RecognitionError):a.endpoint(url)
 def test_http_error_safe(self):
  error=urllib.error.HTTPError('https://secret.invalid',401,'secret-token',{},io.BytesIO(b'{"message":"secret-token"}'))
  with patch.object(a.urllib.request,'urlopen',side_effect=error):
   with self.assertRaises(a.RecognitionError) as cm:a.transcribe(b'ab','wav',16000,'secret-token','https://dashscope.aliyuncs.com')
  self.assertNotIn('secret',str(cm.exception));self.assertIn('401',str(cm.exception))
 def test_validation(self):
  for audio,fmt,rate in [(b'','wav',16000),(b'ab','bad',16000),(b'ab','wav',123),(b'a','pcm',16000)]:
   with self.assertRaises(a.RecognitionError):a.transcribe(audio,fmt,rate,'test','https://dashscope.aliyuncs.com')
 def test_network_error(self):
  with patch.object(a.urllib.request,'urlopen',side_effect=urllib.error.URLError('secret')):
   with self.assertRaises(a.RecognitionError) as cm:a.transcribe(b'ab','wav',16000,'test','https://dashscope.aliyuncs.com')
  self.assertNotIn('secret',str(cm.exception))

if __name__=='__main__':unittest.main(verbosity=2)
