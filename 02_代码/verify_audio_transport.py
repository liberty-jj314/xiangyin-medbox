"""手机音频HTTP回归；隔离资料、虚拟密钥，不调用云端。"""
import unittest, threading, http.client, urllib.parse
from pathlib import Path
from unittest.mock import patch
import verify_leaflet_profiles as base

class AudioTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.Profiles.setUpClass.__func__(cls)
        cls.a.Handler.log_message=lambda *args:None
        cls.server=cls.a.ThreadingHTTPServer(('127.0.0.1',0),cls.a.Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        base.Profiles.tearDownClass.__func__(cls)
    def req(self,name,method='GET',headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=10)
        conn.request(method,'/audio/'+urllib.parse.quote(name),headers=headers or {})
        response=conn.getresponse();result=(response.status,dict(response.getheaders()),response.read())
        conn.close();return result
    def test_all20_initial_two_byte_probe_and_head(self):
        for f in sorted((self.root/'01_资料/方言录音').glob('*.mp3')):
            with self.subTest(file=f.name):
                raw=f.read_bytes();status,h,b=self.req(f.name,headers={'Range':'bytes=0-1'})
                self.assertEqual(status,206);self.assertEqual(b,raw[:2])
                self.assertEqual(h['Content-Range'],f'bytes 0-1/{len(raw)}')
                status,h,b=self.req(f.name,'HEAD');self.assertEqual(status,200)
                self.assertEqual(int(h['Content-Length']),len(raw));self.assertEqual(b,b'')
    def test_affected_four_recordings_can_be_reassembled(self):
        for number in ['07','08','09','14']:
            f=next((self.root/'01_资料/方言录音').glob(number+'_*.mp3'));raw=f.read_bytes();cut=len(raw)//2
            first=self.req(f.name,headers={'Range':f'bytes=0-{cut-1}'})
            last=self.req(f.name,headers={'Range':f'bytes={cut}-'})
            self.assertEqual(first[0],206);self.assertEqual(last[0],206);self.assertEqual(first[2]+last[2],raw)
            status,h,b=self.req(f.name,headers={'Range':'bytes=-100'});self.assertEqual(status,206);self.assertEqual(b,raw[-100:])
    def test_unsatisfied_and_if_range_behaviour(self):
        f=next((self.root/'01_资料/方言录音').glob('07_*.mp3'));raw=f.read_bytes()
        for spec in [f'{len(raw)}-','-0','5-1','bad']:
            status,h,b=self.req(f.name,headers={'Range':'bytes='+spec})
            self.assertEqual(status,416);self.assertEqual(h['Content-Range'],f'bytes */{len(raw)}');self.assertEqual(b,b'')
        status,h,b=self.req(f.name,headers={'Range':'bytes=0-1','If-Range':'"old"'})
        self.assertEqual(status,200);self.assertEqual(b,raw)
    def test_head_and_ranges_cannot_bypass_emergency_stop(self):
        name=next((self.root/'01_资料/方言录音').glob('07_*.mp3')).name
        with patch.object(self.a,'emergency_audio_stopped',return_value=True):
            self.assertEqual(self.req(name,'HEAD')[0],403)
            self.assertEqual(self.req(name,headers={'Range':'bytes=0-1'})[0],403)
    def test_range_cannot_bypass_recording_verification(self):
        name=next((self.root/'01_资料/方言录音').glob('14_*.mp3')).name
        with patch.object(self.a,'verified_profile_audio',return_value=False):
            self.assertEqual(self.req(name,headers={'Range':'bytes=0-1'})[0],403)

if __name__=='__main__':unittest.main(verbosity=2)
