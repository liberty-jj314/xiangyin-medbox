"""本机识别、问答与人工审核记录；与地图计数及模拟常量分开存储。"""
import datetime
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '01_资料', '统计', '问药实测.db')
STATES = ('pending', 'approved', 'rejected')

def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')

@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=2)
    c.row_factory = sqlite3.Row
    c.executescript('''
      CREATE TABLE IF NOT EXISTS recognition (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, ocr_text TEXT NOT NULL,
        drug_name TEXT NOT NULL, region TEXT NOT NULL, location_status TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS answer_record (
        id TEXT PRIMARY KEY, recognition_id TEXT, created_at TEXT NOT NULL,
        ocr_text TEXT NOT NULL, drug_name TEXT NOT NULL, question TEXT NOT NULL,
        answer TEXT NOT NULL, answer_status TEXT NOT NULL, refuse_kind TEXT NOT NULL,
        citation TEXT NOT NULL, voice_file TEXT NOT NULL, region TEXT NOT NULL,
        location_status TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'pending',
        review_note TEXT NOT NULL DEFAULT '', reviewed_at TEXT, revision INTEGER NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS answers_recognition ON answer_record(recognition_id);
      CREATE INDEX IF NOT EXISTS answers_status ON answer_record(review_status, created_at);
      CREATE TABLE IF NOT EXISTS review_history (
        id INTEGER PRIMARY KEY, answer_id TEXT NOT NULL, changed_at TEXT NOT NULL,
        review_status TEXT NOT NULL, review_note TEXT NOT NULL, revision INTEGER NOT NULL);
    ''')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def recognition(ocr_text, drug_name, region='', location_status='unavailable'):
    key = uuid.uuid4().hex
    with connect() as c:
        c.execute('INSERT INTO recognition VALUES(?,?,?,?,?,?)',
                  (key, now(), ocr_text[:24000], drug_name[:200], region, location_status))
    return key

def answer(recognition_id, ocr_text, drug_name, question, text, status, refuse_kind,
           citation, voice_file='', region='', location_status='unavailable'):
    key = uuid.uuid4().hex
    with connect() as c:
        known = c.execute('SELECT ocr_text FROM recognition WHERE id=?', (recognition_id,)).fetchone()
        if not known or known['ocr_text'] != ocr_text[:24000]:
            recognition_id = None
        c.execute('''INSERT INTO answer_record(id,recognition_id,created_at,ocr_text,drug_name,
          question,answer,answer_status,refuse_kind,citation,voice_file,region,location_status)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (key, recognition_id, now(), ocr_text[:24000],
          drug_name[:200], question[:6000], text[:24000], status, refuse_kind,
          json.dumps(citation,ensure_ascii=False), voice_file, region, location_status))
    return key

def listing(page=1, status='all', search=''):
    if status not in ('all', 'unasked') + STATES:
        raise ValueError('无效审核状态')
    page=max(1,min(int(page),100000)); search=search[:120]
    where=[];args=[]
    if status in STATES:
        where.append('review_status=?');args.append(status)
    if search:
        where.append('(drug_name LIKE ? OR question LIKE ? OR ocr_text LIKE ?)')
        args.extend(['%'+search+'%']*3)
    sql=' FROM answer_record'+(' WHERE '+' AND '.join(where) if where else '')
    with connect() as c:
        unasked=c.execute('SELECT COUNT(*) FROM recognition r WHERE NOT EXISTS(SELECT 1 FROM answer_record a WHERE a.recognition_id=r.id)').fetchone()[0]
        counts={r[0]:r[1] for r in c.execute('SELECT review_status,COUNT(*) FROM answer_record GROUP BY review_status')}
        if status=='unasked':
            q=' FROM recognition r WHERE NOT EXISTS(SELECT 1 FROM answer_record a WHERE a.recognition_id=r.id)'
            params=[]
            if search:q+=' AND (drug_name LIKE ? OR ocr_text LIKE ?)';params=['%'+search+'%']*2
            total=c.execute('SELECT COUNT(*)'+q,params).fetchone()[0]
            rows=[dict(r,review_status='unasked',question='',answer_status='unasked',revision=0) for r in c.execute('SELECT id,created_at,drug_name,ocr_text,region,location_status'+q+' ORDER BY created_at DESC,id DESC LIMIT 20 OFFSET ?',params+[(page-1)*20])]
        else:
            total=c.execute('SELECT COUNT(*)'+sql,args).fetchone()[0]
            rows=[dict(r) for r in c.execute('SELECT id,created_at,drug_name,question,answer_status,refuse_kind,review_status,region,location_status,revision'+sql+' ORDER BY created_at DESC,id DESC LIMIT 20 OFFSET ?',args+[(page-1)*20])]
    return dict(ok=True,rows=rows,total=total,page=page,page_size=20,counts=counts,unasked=unasked)

def detail(key, kind='answer'):
    with connect() as c:
        row=c.execute('SELECT * FROM '+('recognition' if kind=='unasked' else 'answer_record')+' WHERE id=?',(key,)).fetchone()
        if not row:return None
        result=dict(row)
        if kind!='unasked':
            result['citation']=json.loads(result['citation'])
            result['history']=[dict(r) for r in c.execute('SELECT changed_at,review_status,review_note,revision FROM review_history WHERE answer_id=? ORDER BY id DESC',(key,))]
        return result

def review(key, state, note, revision):
    if state not in STATES or not isinstance(note,str) or len(note)>2000:
        raise ValueError('审核状态或备注不正确（备注最多2000字）')
    with connect() as c:
        updated=c.execute('UPDATE answer_record SET review_status=?,review_note=?,reviewed_at=?,revision=revision+1 WHERE id=? AND revision=?', (state,note,now(),key,int(revision)))
        if updated.rowcount!=1:raise ValueError('记录不存在或已被修改，请刷新后再审核')
        c.execute('INSERT INTO review_history(answer_id,changed_at,review_status,review_note,revision) VALUES(?,?,?,?,?)',(key,now(),state,note,int(revision)+1))
    return detail(key)
