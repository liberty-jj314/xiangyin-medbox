# -*- coding: utf-8 -*-
r"""
乡音药箱 · 地区问药活跃度统计（D25 新增）

★★ 改这个文件之前先读懂下面五条，它们不是"实现细节"，是答辩口径 ★★

  1. 统计的单位是「问药完成次数」—— 不是"老人数量"，不是"用户数"。
     同一个人问 5 次，就记 5 次。重复使用本身就是需求信号。
  2. 本统计表只存日期、县代码、次数。识别和问答另存于review_store管理的问药实测.db。
  3. 经用户允许后浏览器自动定位并在内存转换为县区；拒绝或失败不计入地区统计。
     不保存坐标，也不作IP定位；所有使用仍可记录识别和问答用于人工审核。
  4. 真实数据和演示数据【物理隔离】：
     真实数据进 SQLite；演示样本是写死在本文件里的常量，
     【根本不进数据库】—— 所以不可能混算，也不可能有人"忘了标注"。
  5. 计数失败绝不能让老人收不到答案。
     本模块所有写库操作都由调用方用 try/except 包住（见 server.py）。

用法：
    import stat_store
    stat_store.add_count('450100')            # 南宁市 +1
    stat_store.summary(7)                     # 近 7 天真实数据
    stat_store.summary(7, kind='demo')        # 近 7 天演示数据
"""

import datetime
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE, '..', '01_资料'))
DB_DIR = os.path.join(DATA_DIR, '统计')
DB_PATH = os.path.join(DB_DIR, '问药统计.db')

# ==================== 一、广西 111 个县级行政区（固定白名单）====================
# 代码是国标行政区划代码（GB/T 2260）前 6 位。
# ★ 服务端只认这个名单里的值，别的值一律丢弃 —— 防止有人构造请求污染统计。
# ★ 县级统计：regionCode 存浏览器允许定位后匹配的县代码（6位）。
COUNTIES = (
    ('450102', '兴宁区'),
    ('450103', '青秀区'),
    ('450105', '江南区'),
    ('450107', '西乡塘区'),
    ('450108', '良庆区'),
    ('450109', '邕宁区'),
    ('450110', '武鸣区'),
    ('450123', '隆安县'),
    ('450124', '马山县'),
    ('450125', '上林县'),
    ('450126', '宾阳县'),
    ('450127', '横州市'),
    ('450202', '城中区'),
    ('450203', '鱼峰区'),
    ('450204', '柳南区'),
    ('450205', '柳北区'),
    ('450206', '柳江区'),
    ('450222', '柳城县'),
    ('450223', '鹿寨县'),
    ('450224', '融安县'),
    ('450225', '融水苗族自治县'),
    ('450226', '三江侗族自治县'),
    ('450302', '秀峰区'),
    ('450303', '叠彩区'),
    ('450304', '象山区'),
    ('450305', '七星区'),
    ('450311', '雁山区'),
    ('450312', '临桂区'),
    ('450321', '阳朔县'),
    ('450323', '灵川县'),
    ('450324', '全州县'),
    ('450325', '兴安县'),
    ('450326', '永福县'),
    ('450327', '灌阳县'),
    ('450328', '龙胜各族自治县'),
    ('450329', '资源县'),
    ('450330', '平乐县'),
    ('450332', '恭城瑶族自治县'),
    ('450381', '荔浦市'),
    ('450403', '万秀区'),
    ('450405', '长洲区'),
    ('450406', '龙圩区'),
    ('450421', '苍梧县'),
    ('450422', '藤县'),
    ('450423', '蒙山县'),
    ('450481', '岑溪市'),
    ('450502', '海城区'),
    ('450503', '银海区'),
    ('450512', '铁山港区'),
    ('450521', '合浦县'),
    ('450602', '港口区'),
    ('450603', '防城区'),
    ('450621', '上思县'),
    ('450681', '东兴市'),
    ('450702', '钦南区'),
    ('450703', '钦北区'),
    ('450721', '灵山县'),
    ('450722', '浦北县'),
    ('450802', '港北区'),
    ('450803', '港南区'),
    ('450804', '覃塘区'),
    ('450821', '平南县'),
    ('450881', '桂平市'),
    ('450902', '玉州区'),
    ('450903', '福绵区'),
    ('450921', '容县'),
    ('450922', '陆川县'),
    ('450923', '博白县'),
    ('450924', '兴业县'),
    ('450981', '北流市'),
    ('451002', '右江区'),
    ('451003', '田阳区'),
    ('451022', '田东县'),
    ('451024', '德保县'),
    ('451026', '那坡县'),
    ('451027', '凌云县'),
    ('451028', '乐业县'),
    ('451029', '田林县'),
    ('451030', '西林县'),
    ('451031', '隆林各族自治县'),
    ('451081', '靖西市'),
    ('451082', '平果市'),
    ('451102', '八步区'),
    ('451103', '平桂区'),
    ('451121', '昭平县'),
    ('451122', '钟山县'),
    ('451123', '富川瑶族自治县'),
    ('451202', '金城江区'),
    ('451203', '宜州区'),
    ('451221', '南丹县'),
    ('451222', '天峨县'),
    ('451223', '凤山县'),
    ('451224', '东兰县'),
    ('451225', '罗城仫佬族自治县'),
    ('451226', '环江毛南族自治县'),
    ('451227', '巴马瑶族自治县'),
    ('451228', '都安瑶族自治县'),
    ('451229', '大化瑶族自治县'),
    ('451302', '兴宾区'),
    ('451321', '忻城县'),
    ('451322', '象州县'),
    ('451323', '武宣县'),
    ('451324', '金秀瑶族自治县'),
    ('451381', '合山市'),
    ('451402', '江州区'),
    ('451421', '扶绥县'),
    ('451422', '宁明县'),
    ('451423', '龙州县'),
    ('451424', '大新县'),
    ('451425', '天等县'),
    ('451481', '凭祥市'),
)

# 县代码（6 位）-> 所属市名（4 位前缀 -> 市）
_CITY_PREFIX = {
    '4501': '南宁市', '4502': '柳州市', '4503': '桂林市', '4504': '梧州市',
    '4505': '北海市', '4506': '防城港市', '4507': '钦州市', '4508': '贵港市',
    '4509': '玉林市', '4510': '百色市', '4511': '贺州市', '4512': '河池市',
    '4513': '来宾市', '4514': '崇左市',
}

COUNTY_CODES = tuple(code for code, _ in COUNTIES)
COUNTY_NAMES = dict(COUNTIES)
# 县 -> 市 映射（后台按市分组、首页两级选单都用它）
COUNTY_CITY = {code: _CITY_PREFIX.get(code[:4], '未知') for code in COUNTY_CODES}
CITY_NAMES = dict((c, c) for c in sorted(set(_CITY_PREFIX.values())))
_SET = frozenset(COUNTY_CODES)

TABLE = 'ask_stat'


# ==================== 二、演示样本（★ 不进数据库）====================
# 只用于讲解"这套后台长什么样"。接口返回时会带上 is_demo=True，
# 页面上会挂常驻横幅，口播也必须说清"这是演示数据"。
# 取值刻意铺满四档颜色，好让图例都能看到效果；按市取几个代表县。
DEMO_SAMPLE = {
    '450102': 12,   # 南宁·兴宁区
    '450105': 9,    # 南宁·江南区
    '450202': 7,    # 柳州·城中区
    '450305': 8,    # 桂林·七星区
    '450324': 6,    # 桂林·全州县
    '450502': 2,    # 北海·海城区
    '450702': 4,    # 钦州·钦南区
    '450821': 5,    # 贵港·平南县
    '450923': 6,    # 玉林·博白县
    '451002': 3,    # 百色·右江区
    '451022': 1,    # 百色·田东县
    '451202': 7,    # 河池·金城江区
    '451302': 1,    # 来宾·兴宾区
    '451421': 2,    # 崇左·扶绥县
}


# ==================== 三、数据库 ====================

def _connect():
    """开一个连接，顺手把表和目录建好。

    每次请求开一个连接就关 —— 演示规模下这点开销可以忽略，
    换来的是不用操心连接池和线程安全。
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS %s (
            day  TEXT    NOT NULL,
            city TEXT    NOT NULL,
            n    INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, city)
        )
    ''' % TABLE)
    return conn


def is_valid_city(code):
    """城市代码必须在广西 111 县白名单里。"""
    return isinstance(code, str) and code in _SET


def add_count(city_code, when=None, amount=1):
    """给某个城市记一次"问药完成"。

    返回 True 表示记上了；False 表示城市代码不合法，什么都没做。

    ★ 用 INSERT ... ON CONFLICT DO UPDATE 做加法，是【一条 SQL 原子完成】的。
      两个人同时问药也不会少计（读-改-写分两步做就会漏）。
    """
    if not is_valid_city(city_code):
        return False

    day = when or datetime.date.today().isoformat()
    conn = _connect()
    try:
        conn.execute(
            'INSERT INTO %s (day, city, n) VALUES (?, ?, ?) '
            'ON CONFLICT(day, city) DO UPDATE SET n = n + ?' % TABLE,
            (day, city_code, amount, amount),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def _date_range(days):
    """返回 (起始日 strings, 结束日 string)。含今天，共 days 天。"""
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days - 1)
    return start.isoformat(), today.isoformat()


def summary(days=7, kind='real'):
    """汇总近 days 天各县的问药完成次数。

    返回的字典结构固定，前端直接照着渲染即可：
        {
          'ok': True,
          'kind': 'real' | 'demo',
          'is_demo': True/False,
          'days': 7,
          'date_from': '2026-10-09',
          'date_to':   '2026-10-15',
          'total': 65,
          'counties': {'450102': 12, ...},   # 111 个县，没数据的补 0
          'county_names': {'450102': '兴宁区', ...},
          'county_city': {'450102': '南宁市', ...},
          'updated_at': '2026-10-15 10:20:31',
        }
    """
    kind = 'demo' if kind == 'demo' else 'real'
    date_from, date_to = _date_range(days)

    if kind == 'demo':
        counties = {code: int(DEMO_SAMPLE.get(code, 0)) for code in COUNTY_CODES}
    else:
        counties = {code: 0 for code in COUNTY_CODES}
        try:
            conn = _connect()
            try:
                rows = conn.execute(
                    'SELECT city, SUM(n) FROM %s WHERE day >= ? AND day <= ? '
                    'GROUP BY city' % TABLE,
                    (date_from, date_to),
                ).fetchall()
            finally:
                conn.close()
            for code, n in rows:
                # 白名单外的历史脏数据也不显示（双保险）
                if code in counties:
                    counties[code] = int(n or 0)
        except Exception:
            # 库读不了也让页面能打开，显示全 0 + 空状态
            pass

    return {
        'ok': True,
        'kind': kind,
        'is_demo': (kind == 'demo'),
        'days': days,
        'date_from': date_from,
        'date_to': date_to,
        'total': sum(counties.values()),
        'counties': counties,
        'county_names': COUNTY_NAMES,
        'county_city': COUNTY_CITY,
        'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def has_real_data(days=30):
    """真实库里到底有没有东西 —— 页面用它决定显示"空状态"还是数据。"""
    date_from, date_to = _date_range(days)
    try:
        conn = _connect()
        try:
            row = conn.execute(
                'SELECT COUNT(*) FROM %s WHERE day >= ? AND day <= ?' % TABLE,
                (date_from, date_to),
            ).fetchone()
        finally:
            conn.close()
        return bool(row and row[0])
    except Exception:
        return False


def db_size_note():
    """给后台页脚用的一句话，说明数据存在哪。"""
    return '统计库：%s' % DB_PATH
