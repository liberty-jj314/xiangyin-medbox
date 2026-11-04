import glob
import csv
import json
import os

# ★ 改成按脚本自身位置推算（2026-10-15 修）：原来写死 C:\Users\jay\Desktop\乡音药箱\...
#   项目文件夹一改名/搬家就失效。
folder = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '01_资料'))

# ★★ 2026-10-15 修（重要）：说明书**不在 01_资料 根目录**，而在 `01_资料\03_药品说明书\`。
#   原来这里只 glob 根目录 → 一个文件都抓不到 → 脚本**照常"成功"退出**，
#   却把 药品数据.json 写成 `[]`（空库！），大模型于是完全没有资料可用。
#   这种"跑通但结果为空"的坑比直接报错危险得多（不会有人注意到），
#   所以下面两处一起改：① 两个位置都找；② 抓不到文件/记录就**拒绝写盘**并报错退出。
SEARCH_DIRS = [os.path.join(folder, '03_药品说明书'), folder]
files = []
for d in SEARCH_DIRS:
    files = sorted(glob.glob(os.path.join(d, '*_说明书.txt')))
    if files:
        break
if not files:
    raise SystemExit('✗ 找不到任何 *_说明书.txt，已中止（不会覆盖现有药品数据）。\n'
                     '  找过这些位置：\n    ' + '\n    '.join(SEARCH_DIRS))

# ★ 2026-10-03（D13）扩充：原来只提取 4 个栏目，导致
#   「这药治什么病」「能吃几天」「80岁以上能吃吗」这类问题
#   在资料里查不到答案 —— D12 评测时 15 条正常题里有 6 条的
#   标准答案根本不在资料里（第 4/7/9/11/13/15 题）。
#   补上【适应症】【注意事项】【特殊人群用药】后，20 条题才真正可答。
WANT = [
    '【适应症】',
    '【规格】',
    '【用法用量】',
    '【禁忌】',
    '【不良反应】',
    '【注意事项】',
    '【特殊人群用药】',
]

# 写进 JSON / CSV 的字段顺序（也是喂给大模型时的顺序）
FIELD_ORDER = ['药名', '适应症', '规格', '用法用量', '禁忌', '不良反应',
               '注意事项', '特殊人群用药', '数据基准']

records = []

for f in files:
    data = {}
    cur = ''
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('※'):
            # ★★ 2026-10-15 修：原来这里一律 continue，把 ※ 备注整行丢掉 ——
            #   后果：说明书源文件里**早就写好了**的"原文在此截断"提示，
            #   永远传不到大模型那里。模型看到的是一段"看起来完整"的资料，
            #   于是照样按它回答（这正是外部核对查出来的那类问题）。
            #   现在：**还没补上的缺口**（含"截断"、且不含"补全"）附到它上面那个栏目末尾，
            #   跟二甲双胍那条既有的写法保持一致；
            #   已经补全的来源说明（如"已按百度百科…补全"）留在源文件即可，不进模型上下文。
            if '截断' in line and '补全' not in line and cur in WANT:
                data[cur] = data[cur] + '（' + line + '）'
            continue
        if line.startswith('【'):
            cur = line.split('】')[0] + '】'
            data[cur] = line.split('】', 1)[1].strip()
        elif cur in WANT:
            data[cur] = data[cur] + ' ' + line

    name = data['【药品名称】'].replace('通用名称：', '')
    maker = data['【生产企业】'].replace('企业名称：', '')
    basis = maker + ' / ' + data['【批准文号】']

    record = {
        '药名': name,
        '适应症': data.get('【适应症】', '（未收录）'),
        '规格': data.get('【规格】', '（未收录）'),
        '用法用量': data.get('【用法用量】', '（未收录）'),
        '禁忌': data.get('【禁忌】', '（未收录）'),
        '不良反应': data.get('【不良反应】', '（未收录）'),
        '注意事项': data.get('【注意事项】', '（未收录）'),
        '特殊人群用药': data.get('【特殊人群用药】', '（未收录）'),
        '数据基准': basis,
    }
    records.append(record)

# ★★ 写盘前的最后一道闸：一条记录都没解析出来 → 直接停手，绝不写空库。
#   否则一次"安静的失败"会把 5 种药的资料全部清空，而所有测试都还显示正常。
if not records:
    raise SystemExit('✗ 解析出 0 条药品记录，已中止（不会覆盖现有药品数据）。\n'
                     '  请检查说明书文件的【…】栏目名是否被改动。')
names = [r['药名'] for r in records]
if len(set(names)) != len(names) or any(not n for n in names):
    raise SystemExit('✗ 解析出的药名有空值或重复：%s' % names)

# ---------- 写 CSV（Excel 看） ----------
csv_path = folder + r'\药品数据.csv'
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as out:
    writer = csv.DictWriter(out, fieldnames=FIELD_ORDER)
    writer.writeheader()
    writer.writerows(records)

# ---------- 写 JSON（喂大模型） ----------
json_path = folder + r'\药品数据.json'
with open(json_path, 'w', encoding='utf-8') as out:
    json.dump(records, out, ensure_ascii=False, indent=2)

print('已写出 CSV ：', csv_path)
print('已写出 JSON：', json_path)
print('共', len(records), '条记录')
