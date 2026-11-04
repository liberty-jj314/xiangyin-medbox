"""现场本地体检：仅用Python标准库，不调用收费接口，不需要Node。"""
from pathlib import Path
import json,hashlib,sys,ssl
ROOT=Path(__file__).resolve().parent.parent
def main():
 errors=[]
 print('乡音药箱｜现场本地体检（不验证网络、额度或云识别准确率）')
 for rel in ['02_代码/server.py','02_代码/index.html','02_代码/admin.html','02_代码/phone.html','02_代码/voice_catalog.json','01_资料/药品数据.json','01_资料/药品审核状态.json','01_资料/实物药品资料.json','04_工具/证书/server.crt','04_工具/证书/server.key']:
  p=ROOT/rel
  if not p.is_file() or not p.stat().st_size:errors.append('缺少必要文件：'+rel)
 for name in ['百度智能云密钥.txt','百度语音识别密钥.txt','阿里云百炼密钥.txt']:
  p=ROOT/'01_资料'/name
  if not p.is_file() or p.stat().st_size==0:errors.append('缺少配置：'+name)
 try:
  manifest=json.loads((ROOT/'文件校验清单.json').read_text(encoding='utf-8'))
  for rel,digest in manifest['files'].items():
   p=ROOT/rel
   if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:errors.append('文件校验不一致：'+rel)
 except (OSError,ValueError,KeyError):errors.append('文件校验清单缺失或损坏')
 try:
  sys.path.insert(0,str(ROOT/'02_代码'));import server
  if not server.audit_available():errors.append('审核配置不可用')
  if len(server.verified_product_profiles())!=5:errors.append('实物说明书原图校验未通过，请重新完整解压')
 except Exception:errors.append('程序导入或资料检查失败')
 for message in errors:print('未通过：'+message)
 if not errors:print('通过：必要文件、配置文件存在、五种实物来源及文件校验完整。可从原三个入口启动。')
 return 1 if errors else 0
if __name__=='__main__':sys.exit(main())
