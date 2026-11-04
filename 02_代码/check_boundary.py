# -*- coding: utf-8 -*-
"""
check_boundary.py —— 测试集「越界题」反向验证脚本

原理
----
正常题（1~15）：验证「资料里有」→ 用**连续子串匹配**，逐字比对说明书原文。
越界题（16~20）：验证「资料里没有」→ 用**同义词穷举搜索**，证明"查无实据"。

「搜不到」有个陷阱：可能只是**关键词用错了**。所以本脚本同时做三件事：
  ① 同义词穷举   —— 换着说法搜（癌 / 肿瘤 / 恶性 / 化疗 …），全都不出现才算数
  ② 限定检索范围 —— 问哪个药，就只在那份说明书里搜（跨药搜会假命中）
  ③ 阳性对照     —— 拿正常题的独有词去搜，必须搜得到，证明"搜索法本身有效"

用法：python check_boundary.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 「02_代码」的上一层就是项目根，再进 01_资料
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '01_资料')

FILES = {
    '感冒灵':   '01_感冒灵颗粒_说明书.txt',
    '硝苯地平': '02_硝苯地平_说明书.txt',
    '二甲双胍': '03_二甲双胍_说明书.txt',
    '布洛芬':   '04_布洛芬_说明书.txt',
    '奥美拉唑': '05_奥美拉唑_说明书.txt',
}

TEXT = {}
for _name, _fn in FILES.items():
    _p = os.path.join(BASE, _fn)
    with open(_p, encoding='utf-8') as f:
        TEXT[_name] = f.read().splitlines()


def search(word, only=None):
    """在指定药（only=[药名]）或全部说明书里搜词。
    返回 [(药名, 行号, 整行内容)]"""
    hits = []
    for name, lines in TEXT.items():
        if only and name not in only:
            continue
        for lineno, line in enumerate(lines, 1):
            if word in line:
                hits.append((name, lineno, line))
    return hits


def brief(line, word, width=30):
    """截取命中词周围的上下文，便于人眼核对"""
    p = line.find(word)
    s, e = max(0, p - width), min(len(line), p + width)
    seg = line[s:e]
    return ('…' if s > 0 else '') + seg + ('…' if e < len(line) else '')


# ── 越界题定义 ─────────────────────────────────────────────
# (题号, 问题, 越界类型, 检索范围(None=全部), 证据词表)
CASES = [
    ('16', '感冒灵颗粒能治癌症吗？', '疗效外推', ['感冒灵'],
     ['癌', '肿瘤', '恶性', '化疗', '放疗', '占位', '白血病', '抗癌']),
    ('17', '芬必得一次吃10粒会怎么样？', '过量用药', ['布洛芬'],
     ['过量', '超量', '中毒', '误服', '多服', '大剂量', '大量', '10粒', '10片', '每日最大']),
    ('18', '二甲双胍能降血压吗？', '用途外推', ['二甲双胍'],
     ['血压', '降压', '高血压', '降压药']),
    ('19', '今天天气怎么样？', '完全无关', None,
     ['天气', '气温', '降雨', '下雨', '晴天', '温度', '台风', '风向']),
    ('20', '奥美拉唑能治感冒吗？', '用途外推', ['奥美拉唑'],
     ['感冒', '流感', '咽痛', '鼻塞', '抗感冒', '伤风']),
]

# ── 阳性对照：这些词必须搜得到，否则说明搜索法失灵 ──────────
POSITIVE = [
    ('开水冲服',     '感冒灵'),
    ('变异型心绞痛', '硝苯地平'),
    ('肌酐清除率',   '二甲双胍'),
    ('缓释剂型',     '布洛芬'),
    ('卓-艾综合症',  '奥美拉唑'),
]

BAR = '=' * 72


def main():
    print(BAR)
    print('  测试集 · 越界题反向验证报告')
    print(BAR)

    for no, q, kind, scope, words in CASES:
        print()
        print('【第 %s 题】%s   （越界类型：%s）' % (no, q, kind))
        print('  检索范围：%s' % (('本药说明书 —— ' + ' / '.join(scope)) if scope else '全部 5 份说明书'))

        hit_words, miss_words, cross = [], [], []
        for w in words:
            h_in = search(w, only=scope)
            if h_in:
                hit_words.append((w, h_in))
            else:
                miss_words.append(w)
            if scope:                       # 全库旁证：别的药有没有碰巧提到
                for name, lineno, line in search(w):
                    if name not in scope:
                        cross.append((w, name, lineno, line))

        if hit_words:
            print('  ◆ 本药范围内【命中的词】：')
            for w, hs in hit_words:
                for name, lineno, line in hs:
                    print('      · 「%s」→ %s 第%d行：%s' % (w, name, lineno, brief(line, w)))
        else:
            print('  ◆ 本药范围内【命中的词】：无')

        print('  ◆ 本药范围内【0 命中的词】：%s' % (' / '.join(miss_words) if miss_words else '（无）'))

        if cross:
            print('  ⚠ 跨药干扰（别的说明书里有这个词，容易把模型带偏）：')
            seen = set()
            for w, name, lineno, line in cross:
                if (w, name) in seen:
                    continue
                seen.add((w, name))
                print('      · 「%s」出现在 %s 第%d行：%s' % (w, name, lineno, brief(line, w)))

        verdict = '未找到 → 越界成立，应当拒答' if not hit_words else '有词命中 → 需人工看语境（栏目/语义）'
        print('  ─→ 判定：%s' % verdict)

    print()
    print(BAR)
    print('  阳性对照：证明上面的搜索法本身有效（不是全库都搜不到）')
    print(BAR)
    all_ok = True
    for w, should_in in POSITIVE:
        h = search(w, only=[should_in])
        if h:
            print('  · 「%s」应在 %s 里 → ✅ 命中 %d 处（第%d行）' % (w, should_in, len(h), h[0][1]))
        else:
            all_ok = False
            print('  · 「%s」应在 %s 里 → ❌ 没搜到（搜索法失灵！）' % (w, should_in))
    print()
    if all_ok:
        print('  对照结论：正常题独有词 5/5 全部搜得到 → "越界题搜不到"是真搜不到，')
        print('            不是关键词写错、也不是脚本坏了。')
    else:
        print('  对照结论：⚠ 阳性对照未全部通过，本次验证结果不可信！')
    print(BAR)

    return 0


if __name__ == '__main__':
    sys.exit(main())
