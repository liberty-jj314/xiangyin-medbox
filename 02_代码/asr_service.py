"""Fun-ASR-Flash短录音转写；复用百炼API Key，不保存录音、不修改转写内容。"""
import base64
import io
import json
import urllib.request
import urllib.error
import urllib.parse
import wave

MODEL='fun-asr-flash-2026-06-15'

class RecognitionError(RuntimeError):
    pass

def endpoint(base_url):
    parsed=urllib.parse.urlsplit(base_url)
    host=parsed.hostname or ''
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise RecognitionError('百炼语音地址必须为官方HTTPS地址')
    if host not in ('dashscope.aliyuncs.com','dashscope-intl.aliyuncs.com') and not host.endswith('.maas.aliyuncs.com'):
        raise RecognitionError('当前百炼地址不是官方语音服务地址，请配置语音接口地址')
    return 'https://'+host+'/api/v1/services/aigc/multimodal-generation/generation'

def transcribe(audio,fmt,rate,key,base_url,model=MODEL,context=''):
    if not key:raise RecognitionError('未找到阿里云百炼API Key，请检查本机密钥文件')
    if not isinstance(audio,bytes) or not audio or len(audio)>8*1024*1024:
        raise RecognitionError('录音为空或超过8MB，请缩短后重新说')
    if fmt not in ('wav','mp3','pcm','webm','ogg','opus','m4a','flac'):
        raise RecognitionError('不支持的录音格式')
    if rate not in (8000,16000,24000,32000,44100,48000):raise RecognitionError('录音采样率不支持')
    if fmt=='pcm':
        if len(audio)%2:raise RecognitionError('PCM录音数据不完整')
        output=io.BytesIO()
        with wave.open(output,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(audio)
        audio=output.getvalue();fmt='wav'
    messages=[]
    if context:
        messages.append({'role':'user','content':[{'type':'input_text','text':context[:400]}]})
    mime={'mp3':'audio/mp3','m4a':'audio/mp4'}.get(fmt,'audio/'+fmt)
    messages.append({'role':'user','content':[{'type':'input_audio','input_audio':{'data':'data:'+mime+';base64,'+base64.b64encode(audio).decode('ascii')}}]})
    body={'model':model,'input':{'messages':messages},'parameters':{'format':fmt,'sample_rate':str(rate),'language_hints':['zh']}}
    request=urllib.request.Request(endpoint(base_url),data=json.dumps(body).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-DashScope-SSE':'disable'},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=40) as response:data=json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        code=''
        try:code=str(json.loads(error.read().decode('utf-8')).get('code',''))[:100]
        except (ValueError,UnicodeError):pass
        # Never return supplier response bodies, authorization, URLs or raw audio.
        raise RecognitionError('Fun-ASR调用失败（HTTP %s%s）；请检查模型权限、地域或额度。'%(error.code,', '+code if code else '')) from None
    except (urllib.error.URLError,TimeoutError,OSError):
        raise RecognitionError('Fun-ASR连接超时或网络异常，请重试或改用普通话识别') from None
    except (ValueError,UnicodeError):raise RecognitionError('Fun-ASR返回格式异常，请重试') from None
    if data.get('code'):raise RecognitionError('Fun-ASR返回错误，请检查服务权限和额度')
    try:
        output=data['output']
        if isinstance(output.get('text'),str):text=output['text'].strip()
        else:
            parts=output['choices'][0]['message']['content']
            text=''.join(p['text'] for p in parts if isinstance(p,dict) and isinstance(p.get('text'),str)).strip()
    except (KeyError,IndexError,TypeError):raise RecognitionError('Fun-ASR返回缺少识别文本') from None
    if not text:raise RecognitionError('没有听清，请靠近麦克风再说一次')
    return text
