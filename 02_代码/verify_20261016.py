# -*- coding: utf-8 -*-
r"""
verify_20261016.py —— 2026-10-16 四项 P0 缺陷的离线验证

【为什么要有这个脚本】
    清单上写的"目前的问题"都是**已复现的故障**，不是猜测。
    修完必须能重新证明：这些故障不再发生，且没顺手搞坏别的。
    所以每一项都写成**可执行的断言**，跑挂了就是没修好。

【原则】
    · 不联网、不调任何 API、不花一分钱。
    · 测的是"这次改动"；完整 20 题评测是另一件事（见 d12_eval.py）。
    · 前端的逻辑**从 index.html 原样抽出来**交给 node 跑 —— 不重抄一遍。
      重抄就等于测了另一份代码，是这类验证最常见的自欺。

用法：
    python 02_代码/verify_20261016.py
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, '01_资料')
HTML = os.path.join(HERE, 'index.html')

sys.stdout.reconfigure(encoding='utf-8')

PASS, FAIL = [], []


def check(name, got, want):
    ok = (got == want)
    (PASS if ok else FAIL).append(name)
    print('  %s %-50s 实得=%s' % ('✅' if ok else '❌', name, repr(got)[:30]))
    return ok


def title(t):
    print()
    print('=' * 72)
    print('  ' + t)
    print('=' * 72)


def load_py(file_name, assigns, funcs, extra=''):
    """提取原函数及其全局依赖，避免新增依赖后验证脚本漏同步。"""
    import ast
    source = open(os.path.join(HERE, file_name), encoding='utf-8-sig').read()
    tree = ast.parse(source)
    definitions = {}
    for item in tree.body:
        if isinstance(item, ast.FunctionDef):
            definitions[item.name] = item
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = item
    required, pending = set(), list(assigns | funcs)
    while pending:
        name = pending.pop()
        if name in required or name not in definitions:
            continue
        required.add(name)
        pending.extend(value.id for value in ast.walk(definitions[name])
                       if isinstance(value, ast.Name) and isinstance(value.ctx, ast.Load))
    nodes = [item for item in tree.body if any(definitions.get(name) is item for name in required)]
    env = {'re': re, 'json': json, 'os': os, 'DATA_DIR': DATA,
           '__file__': os.path.join(HERE, file_name),
           'print': lambda *args, **kwargs: None}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<original server functions>', 'exec'), env)
    if extra:
        exec(extra, env)
    return env


# =====================================================================
# ① 拒答状态（缺陷 3）
# =====================================================================
title('① 缺陷3 · 拒答状态不能只靠"模型逐字说出固定句"')

E = load_py('server.py',
            assigns={'REFUSE_NOTFOUND', 'REFUSE_SCOPE', 'REFUSE_SEMANTIC',
                     'ANSWER_TAG_ANSWERED', 'ANSWER_TAG_REFUSED'},
            funcs={'classify_answer'})
ca = E['classify_answer']

check('原话"这个我不清楚，要问医生" → 拒',
      ca('这个我不清楚，要问医生'), 'scope')
check('★改一个字"这个我不清楚，请问医生" → 仍拒（原版漏判）',
      ca('这个我不清楚，请问医生'), 'scope')
check('★"这个情况我不清楚，建议咨询医生" → 仍拒',
      ca('这个情况我不清楚，建议咨询医生'), 'scope')
check('★"说明书上没有这一条，我不敢乱说" → 仍拒',
      ca('说明书上没有这一条，我不敢乱说'), 'scope')
check('★"我没法回答这个问题" → 仍拒',
      ca('我没法回答这个问题'), 'scope')
check('没认出药 → notfound',
      ca('我没认出这是什么药，能再拍一张吗？'), 'notfound')
check('空答案 → 拒（不再当成正常）', ca(''), 'scope')

check('模型标 [答] 且正文有依据 → 放行',
      ca('[答] 一次吃一片，一天吃三回。'), '')
check('模型标 [拒] → 拒',
      ca('[拒] 这个我不清楚，要问医生。'), 'scope')
check('★标 [答] 但正文说资料没写 → 文字优先判拒',
      ca('[答] 这个我不清楚，要问医生。'), 'scope')

for a in ['[答] 这个药是治感冒的，头痛发烧鼻塞流涕咽痛都可以吃。',
          '[答] 严重肝肾功能不全的人不能吃这个药。']:
    check('正常回答不被误拒：%s' % a[4:20], ca(a), '')

check('★无标注的正常回答 → 判不采信（保守；文字仍显示）',
      ca('感冒灵颗粒是治感冒的。'), 'unknown')
check('★无标注 + 含剂量 → 判不采信（保守）',
      ca('这个药说明书上写的是一天吃三次。'), 'unknown')

check('剂型不符 → mismatch', ca('任意文字', mismatch_hit=True), 'mismatch')
check('资料审核未通过 → audit', ca('任意文字', audit_hit=True), 'audit')

print('\n  → 换 5 种说法都仍判拒；标 [答] 且有依据的正常回答全部放行（没有过度拒答）')


# =====================================================================
# ② 录音选择（缺陷 2）：用 node 跑 index.html 的原逻辑
# =====================================================================
title('② 完整页面脚本的异步与播报回归')
HTMLSRC = open(HTML, encoding='utf-8').read()
JS = '\n'.join(re.findall(r'<script>([\s\S]*?)</script>', HTMLSRC))
result = subprocess.run(['node', os.path.join(HERE, 'verify_frontend_20261019.js')],
                        capture_output=True, text=True, encoding='utf-8', timeout=60)
if result.returncode:
    print(result.stdout, result.stderr)
    raise RuntimeError('前端回归未通过')
front = json.loads(result.stdout)
for item in front['tests']:
    check(item['name'], item['passed'], True)

# =====================================================================
# ③ 资料审核拦截（缺陷 1）
# =====================================================================
title('③ 缺陷1 · 审核表登记的冲突字段，后端必须真的拦住')

audit_file = os.path.join(DATA, '药品审核状态.json')
check('药品审核状态.json 存在', os.path.isfile(audit_file), True)

if os.path.isfile(audit_file):
    audit = json.load(open(audit_file, encoding='utf-8'))
    drugs = audit.get('药品', {})
    check('覆盖 5 种药', len(drugs), 5)
    blocked = [(k, f) for k, v in drugs.items()
               for f, st in v.items() if st == 'blocked']
    print('  登记为 blocked 的字段：')
    for k, f in blocked:
        print('     · %s · %s' % (k, f))
    check('★确有 blocked 字段被登记', len(blocked) > 0, True)

    m = re.search(r'var VOICE_DISABLED = \{[\s\S]*?\n    \};', JS)
    disabled = set(re.findall(r"'([^']+\.mp3)':", m.group(0)))
    declared = set()
    for v in audit.get('拦截理由', {}).values():
        declared.update(v.get('播报禁用', []))

    files = os.listdir(os.path.join(DATA, '方言录音'))
    for f in sorted(declared):
        check('停用「%s」在录音目录中真实存在' % f, f in files, True)
    check('★前后端停用清单完全一致（改一处必须同时改两处）',
          disabled, declared)
    check('停用清单非空', len(disabled) > 0, True)

    E2 = load_py('server.py',
                 assigns={'FIELD_TOPICS', 'AUDIT_BLOCK_REPLY', 'QUESTION_LABELS', 'CITE_FIELDS', 'CITE_LABEL', 'CITE_HINTS', 'CITE_MAX_CHARS'},
                 funcs={'load_audit', 'match_audit_drug', 'strip_labels', 'only_question',
                        'which_field_topic', 'check_audit_block',
                        'load_drug_records', 'find_drug_record',
                        'truncate_cite', 'build_citation', 'cn_to_arabic'},
                 extra="AUDIT_FILE = %r\nAUDIT = {'loaded': False, 'data': None, 'ok': False}\n"
                       % audit_file)
    cab = E2['check_audit_block']
    wft = E2['which_field_topic']
    strip = E2['strip_labels']

    # ★ 回归：标签里的"老人"两个字曾被误判成"在问特殊人群用药"，
    #   害得一道题都拦不住。这一条必须钉死。
    check('★剥标签后不再把「老人问」当成"老人能不能吃"',
          '老人' in strip('【药盒上识别到的文字】布洛芬缓释胶囊\n\n'
                          '【老人问的问题】这个药怎么吃'), False)
    check('★剥标签后仍能认出"老人能不能吃"',
          wft('【药盒上识别到的文字】二甲双胍片\n\n【老人问的问题】老人能不能吃'),
          '特殊人群用药')

    # ★★ 回归（真打接口测出来的）：OCR 药盒文字里的**栏目标题**
    #   （[规格]、[适应症]）曾抢在问句之前被命中 → 布洛芬无论问什么都误拦。
    #   这一条钉死"栏目判定只能看老人问的那部分"。
    oq = E2['only_question']
    check('★只取老人问句：丢掉药盒那一半',
          oq('【药盒上识别到的文字】布洛芬缓释胶囊\n[规格]0.3克\n\n'
             '【老人问的问题】什么人不能吃').strip(),
          '什么人不能吃')
    check('★问句无标签时退化为剥标签全文',
          '老人能不能吃' in oq('老人能不能吃'), True)
    for q, want in [('什么人不能吃', '禁忌'),
                    ('吃了有什么副作用', '不良反应'),
                    ('这个药治什么病', '适应症'),
                    ('一次吃多少', '用法用量'),
                    ('最多能吃几天', '注意事项')]:
        payload = ('【药盒上识别到的文字】布洛芬缓释胶囊\n'
                   '[规格]0.3克\n[适应症]缓解疼痛\n\n'
                   '【老人问的问题】' + q)
        check('  └ 栏目判定不受 OCR 栏名干扰：%s' % q,
              wft(oq(payload)), want)
    check('★★布洛芬问副作用不该被拦（误拦回归）',
          cab('【药盒上识别到的文字】布洛芬缓释胶囊\n[规格]0.3克\n\n'
              '【老人问的问题】吃了有什么副作用', '') is None, True)
    check('★★布洛芬问禁忌不该被拦（误拦回归）',
          cab('【药盒上识别到的文字】布洛芬缓释胶囊\n[规格]0.3克\n\n'
              '【老人问的问题】什么人不能吃', '') is None, True)
    check('★★布洛芬问治什么病不该被拦（误拦回归）',
          cab('【药盒上识别到的文字】布洛芬缓释胶囊\n[规格]0.3克\n\n'
              '【老人问的问题】这个药治什么病', '') is None, True)
    check('★★但布洛芬问剂量仍必须拦（防"修过头"）',
          '拦截' if cab('【药盒上识别到的文字】布洛芬缓释胶囊\n[规格]0.3克\n\n'
                         '【老人问的问题】一次吃多少', '') else '★没拦',
          '拦截')

    BLOCK = [
        ('【药盒上识别到的文字】盐酸二甲双胍片 0.85克\n\n【老人问的问题】这个药一天吃几次',
         '二甲双胍·用法用量'),
        ('【药盒上识别到的文字】布洛芬缓释胶囊 0.3克\n\n【老人问的问题】这个药怎么吃',
         '布洛芬·用法用量'),
        ('【药盒上识别到的文字】奥美拉唑肠溶胶囊 10毫克\n\n【老人问的问题】这个药一次吃多少',
         '奥美拉唑·用法用量'),
        ('【药盒上识别到的文字】奥美拉唑肠溶胶囊 10毫克\n\n【老人问的问题】这个药最多能吃几天',
         '奥美拉唑·疗程'),
        ('【药盒上识别到的文字】奥美拉唑肠溶胶囊\n\n【老人问的问题】这个药怎么吃，一天吃几回',
         '奥美拉唑·剂量（两栏都问，优先拦剂量）'),
    ]
    for q, why in BLOCK:
        r = cab(q, '')
        check('拦截：%s' % why, '拦截' if r else '★没拦', '拦截')
        if r:
            nums = re.findall(r'\d+\s*(?:mg|毫克|克|片|粒|袋|天|次|周)', r)
            check('  └ 拦截句不含任何剂量数字', nums, [])

    ALLOW = [
        ('【药盒上识别到的文字】感冒灵颗粒\n\n【老人问的问题】这个药治什么病',
         '感冒灵·适应症 放行'),
        ('【药盒上识别到的文字】感冒灵颗粒\n\n【老人问的问题】这个药怎么吃',
         '感冒灵·用法用量 放行'),
        
        ('【药盒上识别到的文字】布洛芬缓释胶囊\n\n【老人问的问题】什么人不能吃',
         '布洛芬·禁忌 放行'),
        ('【药盒上识别到的文字】布洛芬缓释胶囊\n\n【老人问的问题】吃了有什么副作用',
         '布洛芬·不良反应 放行'),
        ('【药盒上识别到的文字】盐酸二甲双胍片\n\n【老人问的问题】老人能不能吃',
         '二甲双胍·特殊人群 放行'),
        ('【药盒上识别到的文字】盐酸二甲双胍片\n\n【老人问的问题】这个药治什么病',
         '二甲双胍·适应症 放行'),
        
    ]
    for q, why in ALLOW:
        check(why, bool(cab(q, '')), False)


# =====================================================================
# ④ 异步过期保护（缺陷 4）
# =====================================================================
title('④ 缺陷4 · 换药后旧结果 / 旧声音一律作废')

check('清空时连player 音频源一起扔',
      "player.removeAttribute('src')" in HTMLSRC, True)
check('清空时连乡音播放器音频源一起扔',
      "voicePlayer.removeAttribute('src')" in HTMLSRC, True)
check('清空时丢弃旧音频缓存 lastAudioUrl',
      "lastAudioUrl = '';" in HTMLSRC, True)
check('OCR/ASR/问答/TTS 回调均验号',
      HTMLSRC.count('if (myTask !== taskSeq) return;') >= 5, True)
check('过期音频有专门告警而非静默',
      '音频回来时已经换药了' in HTMLSRC, True)
check('★丢弃分支里不会再 player.play()',
      re.search(r'已经换药了[\s\S]{0,400}?player\.play\(\)',
                HTMLSRC) is None, True)
check('问药按钮防连点', 'btnAsk.disabled = true' in HTMLSRC, True)

# 实际页面异步回归已在第②组执行，不复制另一套任务函数冒充原逻辑。

# =====================================================================
# ★★ P1-7 答案出处（2026-10-16 新增）
# =====================================================================
# 目标：让"只依据说明书作答"这条红线**可以被当场核对**，
#   而不是只能口头声明。只给"确实答了"的回答出处；定位不到就如实说定位不到。
if True:
    title('P1-7 答案出处')

    drugs_file = os.path.join(DATA, '药品数据.json')
    # 出处相关函数是从 server.py 原样抽出来的（E2），不另抄一份。
    # ★ E2 定义在上一个代码块里，同为模块级 → 这里可以直接用。
    assert 'load_drug_records' in E2, '出处函数没抽出来，检查 funcs/assigns 名单'
    load_drug_records = E2['load_drug_records']
    find_drug_record = E2['find_drug_record']
    truncate_cite = E2['truncate_cite']
    build_citation = E2['build_citation']
    with open(drugs_file, encoding='utf-8') as f:
        recs = load_drug_records(f.read())

    check('药品记录已按固定编号排列（评委可拿编号去核）',
          [r['药品编号'] for r in recs],
          ['药品#%02d' % i for i in range(1, len(recs) + 1)])

    # 认药：认不出 / 多个都像 → None（不许瞎标）
    check('认得出唯一药名', find_drug_record('感冒灵颗粒一天吃几次', recs)['药名'],
          '感冒灵颗粒')
    check('★认不出药时不出处（不猜）',
          find_drug_record('这个药怎么吃', recs), None)

    # 拒答一律不出处：拒答句是程序固定生成的，本来就没有栏目可引
    check('★拒答不出处',
          build_citation('【药盒上识别到的文字】感冒灵颗粒\n\n【老人问的问题】感冒灵颗粒一天吃几次', recs, '随便吃', 'audit'), None)
    check('★拒答不出处（越界）',
          build_citation('【药盒上识别到的文字】感冒灵颗粒\n\n【老人问的问题】感冒灵颗粒一天吃几次', recs, '这个我不清楚', 'scope'), None)

    # 栏目定位：命中即列出，附真实原文
    c = build_citation('【药盒上识别到的文字】感冒灵颗粒\n\n【老人问的问题】感冒灵颗粒一天吃几次', recs,
                       '[答] 一天吃三次，每次用开水冲一袋（10克）。')
    used = [x['栏目'] for x in c['引用栏目']]
    check('剂量问题定位到【用法用量】', '用法用量' in used, True)
    check('★原文必须是资料里的真话，不是生成的',
          any('开水冲服' in x['原文'] for x in c['引用栏目']), True)
    check('未收录栏目如实标出', c['未收录栏目'], ['特殊人群用药'])

    c2 = build_citation('【药盒上识别到的文字】感冒灵颗粒\n\n'
                        '【老人问的问题】吃了有什么副作用',
                        recs, '[答] 少数人吃了可能会恶心、呕吐、肚子不舒服。')
    check('副作用问题定位到【不良反应】',
          '不良反应' in [x['栏目'] for x in c2['引用栏目']], True)

    # ★ 原文过长必须标明截断，不静默截断
    long_txt = '很长的原文' * 40
    cut, cut_flag = truncate_cite(long_txt)
    check('★过长原文被截断', cut_flag, True)
    check('★截断后明确标注', '截取前段' in cut, True)
    check('短原文不标截断', truncate_cite('一次10克')[1], False)

    # 出处必须带上药品身份，否则"换规格套错服法"无法发现
    c3 = build_citation('【药盒上识别到的文字】感冒灵颗粒\n\n【老人问的问题】感冒灵颗粒一天吃几次', recs, '[答] 一天吃三次。')
    for k in ('药品编号', '药名', '规格', '数据基准'):
        check('出处带「%s」' % k, bool(c3.get(k)), True)


# =====================================================================
# ★★ 拒答句里的剂量泄漏（2026-10-16 独立验收 V05/V06 挖出）
# =====================================================================
# 现象：模型判了拒答，却顺手把对照剂量写出来
#   V05 "和资料里的 10克/袋 规格对不上"
#   V06 "用法用量是一次1片，一日2次"
# 为什么危险：屏幕写着"我不清楚"、耳朵里已拿到剂量
#            → 老人会理解成"吃法我记住了"，比直接答错更容易出事。
if True:
    title('拒答句剂量擦除')

    E3 = load_py('server.py',
                 assigns={'DOSE_RE', 'SAFE_REFUSE_REPLY', 'OCR_LOG_KEEP_DAYS'},
                 funcs={'scrub_refuse_dose', 'ocr_log_status',
                        'ocr_log_enabled', 'set_ocr_log', 'purge_ocr_log'},
                 extra="DATA_DIR = os.path.join(%r, '01_资料')\n"
                       "OCR_LOG_DIR = os.path.join(DATA_DIR, 'ocr日志')\n"
                       "OCR_LOG_FLAG = os.path.join(DATA_DIR, 'ocr日志开关.txt')\n"
                       % ROOT)
    scrub = E3['scrub_refuse_dose']

    # ① 真实两起：都必须被替换掉，且替换后零剂量
    V05 = ('[拒] 您手上这一盒是5克一袋的感冒灵颗粒，和我资料里的"10克/袋"'
           '规格对不上，我不能照着它的说明书告诉您怎么吃。')
    V06 = ('[拒] 您手上这一盒是"缓释胶囊"，用法用量是"一次1片，一日2次"，'
           '可我没在资料里看到。')
    for nm, raw in (('V05 规格不符', V05), ('V06 药名不全', V06)):
        safe, did = scrub(raw, 'scope')
        check('%s 检出并替换' % nm, did, True)
        check('  └ %s 替换后不含剂量数字' % nm,
              re.findall(r'\d+\s*(?:mg|毫克|克|片|粒|袋)|[一二三四五六七八九十]+\s*(?:片|粒|袋|次|天|周)', safe or ''), [])
        check('  └ %s 替换后仍保留"问医生/药师"' % nm,
              ('医生' in (safe or '')) or ('药师' in (safe or '')), True)

    # ② 即使当前句子看起来干净，也不继续信任模型的自由拒答措辞。
    check('★所有拒答统一固定模板',
          scrub('[拒] 这个我不清楚，要问医生。', 'scope'),
          (E3['SAFE_REFUSE_REPLY']['scope'], True))

    # ③ ★正常回答里的剂量是应该有的，绝不能被误擦（防修过头）
    check('★正常回答的剂量不被擦除',
          scrub('[答] 一次吃10克（1袋），一天吃三次。', ''), (None, False))

    # ④ ★中文数字也要算（两边必须同一套正则）
    #   踩坑经过：先只认阿拉伯数字，真打接口时"一天吃三次、冲一袋"被判成"没剂量"，
    #   顺着查才发现**拒答侧同样漏中文数字** —— 拒答说"一天三次"和"一日3次"
    #   泄漏的是同一个信息。两边不一致 = 一边假绿。
    check('★拒答句里的中文数字同样要擦除',
          scrub('[拒] 这盒是缓释胶囊，一天吃三次。', 'scope')[1], True)
    check('★正常回答里的中文数字不被误擦',
          scrub('[答] 一天吃三次，每次冲一袋。', ''), (None, False))

    # ④ 各类拒答都要有安全句兜底
    for k in ('notfound', 'scope', 'unknown'):
        check('%s 类拒答有安全句且零剂量' % k,
              re.findall(r'\d+\s*(?:mg|毫克|克|片|粒|袋)|[一二三四五六七八九十]+\s*(?:片|粒|袋|次|天|周)',
                         E3['SAFE_REFUSE_REPLY'][k]), [])

    # ⑤ 提示词里必须写死这条规矩（双保险，代码是主防线）
    #    ★ 提示词在 server.py 里，不在 index.html —— 一开始查错文件了。
    with open(os.path.join(HERE, 'server.py'), encoding='utf-8') as f:
        srctxt = f.read()
    check('★提示词已写明"拒答时一个剂量数字都不许出现"',
          '不得生成、换算或补充资料没有的剂量' in srctxt, True)

    # ⑥ OCR 日志开关与保留期
    check('OCR 日志有保留期限', E3['OCR_LOG_KEEP_DAYS'] <= 90, True)
    check('OCR 日志状态可查', sorted(E3['ocr_log_status']()),
          ['count', 'enabled', 'keep_days'])

    # ⑦ ★认不出药就不许给剂量（独立验收 V06 挖出，比拒答泄漏更严重）
    #    实测：药盒只读到"……缓释胶囊"，模型自己猜出是布洛芬并给了吃法。
    #    提示词写了"药名整名照抄"，但提示词稳不住这种行为 → 必须代码兜底。
    load_drug_records = E2['load_drug_records']
    find_drug_record = E2['find_drug_record']
    check('★药名不全是认不出（不能靠剂型猜）',
          find_drug_record('【药盒上识别到的文字】……缓释胶囊\n[规格]0.3克\n\n'
                           '【老人问的问题】这个药怎么吃', recs), None)
    nf = E3.get('NOTFOUND_REPLY') if 'NOTFOUND_REPLY' in E3 else None
    if nf is None:
        with open(os.path.join(HERE, 'server.py'), encoding='utf-8') as f:
            m = re.search(r"NOTFOUND_REPLY = \((.*?)\n\)", f.read(), re.S)
        nf = eval('(' + m.group(1) + ')')
    check('★认不出药的固定句零剂量',
          re.findall(r'\d+\s*(?:mg|毫克|克|片|粒|袋)|[一二三四五六七八九十]+\s*(?:片|粒|袋|次|天|周)', nf), [])
    check('★认不出药的固定句含"再拍一张"',
          ('拍' in nf) and ('张' in nf), True)


# =====================================================================
title('汇总')
print('  通过 %d 项，失败 %d 项' % (len(PASS), len(FAIL)))
if FAIL:
    print()
    for f in FAIL:
        print('  ❌ ' + f)
    print('\n  ⚠ 有失败项 = 这次修复没到位，先别重打包。')
sys.exit(1 if FAIL else 0)
