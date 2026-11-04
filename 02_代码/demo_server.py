# -*- coding: utf-8 -*-
"""
虚拟手机演示 —— 服务启动器（Demo Server）

它做的事情只有三件：
  1. 演示前自检：必需的密钥/资料在不在（换电脑演示最容易踩的坑）
  2. 确认 8000 端口空着（演示要的是可预测的地址）
  3. 启动 server.py，但★不自动弹出浏览器★

为什么不直接改 server.py：
  server.py 是正式程序，手机上跑的那套也用它。演示专用的行为
  （不弹浏览器）不该写进正式程序里 —— 所以在这里用猴子补丁拦掉
  webbrowser.open 就行，server.py 一个字都不用动。

用法（一般由 start_phone_demo.bat / start_app.bat 自动调用）：
    python demo_server.py          正常起服务
    python demo_server.py --check   只做自检，不起服务（退出码 0=通过 1=缺东西）
    python demo_server.py --open    缺文件时自动弹出 01_资料 文件夹
"""

import os
import json
import runpy
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8000
DATA_DIR = os.path.abspath(os.path.join(HERE, '..', '01_资料'))

# ★ 这几份因为「文件名含密钥」被排除在备份包之外（防外泄），
#   所以换电脑演示时它们一定不在 —— 自检就是专门盯这一件事。
NEEDED = (
    ('百度智能云密钥.txt',   '拍照识药（OCR）'),
    ('百度语音识别密钥.txt', '按住说话（语音转文字）'),
    ('阿里云百炼密钥.txt',   '问药（大模型答题）'),
    ('药品数据.json',        '5 种药的说明书资料'),
    ('药品审核状态.json',    '自动回答的审核保护'),
)

# ★ 可选件：缺了不影响老人问药，所以不拦、不算失败，只提示一句。
#   同样因为"文件名含密钥"而进不了备份包。
OPTIONAL = (
    ('高德地图密钥.txt', '后台「地区问药活跃度」的联网地图（没有就自动用方块地图兜底）'),
)


def preflight(verbose=False):
    """检查必需文件在不在。返回缺失清单 [(文件名, 用途), ...]。"""
    missing = []
    if verbose:
        print('')
        print('  ── 演示前自检 ────────────────────────────────')
        print('  资料目录：' + DATA_DIR)
        print('')
    if not os.path.isdir(DATA_DIR):
        if verbose:
            print('  ✗ 连 01_资料 目录都找不到 —— 包可能没解压完整。')
        return [('01_资料（整个目录）', '所有资料')]
    for name, why in NEEDED:
        path = os.path.join(DATA_DIR, name)
        ok = os.path.isfile(path) and os.path.getsize(path) > 0
        if verbose:
            print('   %s %-22s %s' % ('✓' if ok else '✗', name, why))
        if not ok:
            missing.append((name, why))
    for name, why in OPTIONAL:
        path = os.path.join(DATA_DIR, name)
        ok = os.path.isfile(path) and os.path.getsize(path) > 0
        if verbose:
            print('   %s %-22s %s' % ('○' if not ok else '✓', name, why))
    if not any(name in ('药品数据.json', '药品审核状态.json') for name, _ in missing):
        try:
            with open(os.path.join(DATA_DIR, '药品数据.json'), encoding='utf-8-sig') as stream:
                records = json.load(stream)
            with open(os.path.join(DATA_DIR, '药品审核状态.json'), encoding='utf-8-sig') as stream:
                audit = json.load(stream)
            if not isinstance(records, list) or not records:
                raise ValueError('药品数据必须是非空列表')
            drugs = audit.get('药品') if isinstance(audit, dict) else None
            if not isinstance(drugs, dict) or not drugs:
                raise ValueError('审核药品对象为空或格式不正确')
            fields = ('适应症', '用法用量', '禁忌', '不良反应', '注意事项', '特殊人群用药')
            for record in records:
                if not isinstance(record, dict) or not record.get('药名'):
                    raise ValueError('药品记录缺少名称')
                statuses = drugs.get(record['药名'])
                if not isinstance(statuses, dict) or any(statuses.get(field) not in ('passed', 'caution', 'blocked') for field in fields):
                    raise ValueError('审核记录缺少栏目或含非法状态：' + record['药名'])
            if verbose:
                print('   ✓ 药品数据及审核记录结构有效；caution/blocked字段保持暂停')
        except (OSError, ValueError, TypeError, AttributeError) as error:
            missing.append(('药品数据 / 审核记录格式', str(error)))
            if verbose:
                print('   ✗ ' + str(error))
    if verbose:
        print('')
    return missing


def show_missing(missing):
    """把"缺什么、去哪拿、放到哪"讲清楚。"""
    print('')
    print('  ✗ 缺 %d 个文件，演示起不来。' % len(missing))
    print('')
    print('    这几个文件因为含密钥，★故意没放进备份包★，')
    print('    换电脑演示时要单独拷过来：')
    print('')
    for name, why in missing:
        print('      · %-22s %s' % (name, why))
    print('')
    print('    放到这个目录里（文件名一个字都不能改）：')
    print('      ' + DATA_DIR)
    print('')
    print('    来源：原来那台电脑的项目目录 01_资料\\ 里就有。')
    print('')


def open_data_dir():
    """在资源管理器里打开资料目录，省得用户自己找。
    用 Python 调 explorer：路径含中文，交给 Python 传参不会乱码。"""
    try:
        os.startfile(DATA_DIR)
    except Exception:
        pass


def countdown(seconds=20):
    for i in range(seconds, 0, -1):
        sys.stdout.write('  %d 秒后自动关闭这个窗口…\r' % i)
        sys.stdout.flush()
        time.sleep(1)
    print('')


def port_in_use(port):
    """8000 上有没有人在监听。

    ★ 为什么不用 bind 试：Windows 和 Linux 不一样 —— 设了 SO_REUSEADDR 之后
      Windows 允许两个程序绑同一个端口（不报错），所以 bind 成功并不代表没人用。
      "连一下"最准：连得上就说明有服务在跑。
    """
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(('127.0.0.1', port))
        return True
    except Exception:
        return False
    finally:
        s.close()


if __name__ == '__main__':
    args = sys.argv[1:]

    # ---------- 模式一：只自检 ----------
    if '--check' in args:
        missing = preflight(verbose=True)
        if missing:
            show_missing(missing)
            if '--open' in args:
                open_data_dir()
            sys.exit(1)
        print('  ✓ 文件与数据结构检查通过。实际接口、手机HTTPS与声音仍需现场验收。')
        print('')
        sys.exit(0)

    # ---------- 模式二：正常起服务 ----------
    if port_in_use(PORT):
        print('')
        print('  ✗ 端口 %d 被占用了，演示起不来。' % PORT)
        print('')
        print('    最常见的原因：已经有一个演示（或 server.py）在跑。')
        print('    把它们关掉，再双击一次就行。')
        print('')
        print('    想看看是谁占着：在命令行里执行')
        print('        netstat -ano | findstr :8000')
        print('')
        countdown(8)
        sys.exit(1)

    # ★ 起服务之前先自检：缺文件就别打印"服务已启动"，
    #   否则用户会以为成功了，然后看着它莫名其妙退出。
    missing = preflight(verbose=False)
    if missing:
        show_missing(missing)
        open_data_dir()
        countdown(20)
        sys.exit(1)

    # ★ 关键一步：把"自动打开浏览器"这个动作变成空操作。
    #   必须在 server.py 跑起来之前打补丁，因为它在文件顶部就 import 了 webbrowser。
    import webbrowser
    webbrowser.open = lambda *a, **k: None
    webbrowser.open_new = lambda *a, **k: None
    webbrowser.open_new_tab = lambda *a, **k: None

    server_py = os.path.join(HERE, 'server.py')
    if not os.path.isfile(server_py):
        print('  ✗ 没找到 server.py，这个脚本要放在 02_代码 目录里。')
        time.sleep(8)
        sys.exit(1)

    print('')
    print('  ┌──────────────────────────────────────────────┐')
    print('  │  乡音药箱 · 虚拟手机演示 —— 服务已启动        │')
    print('  │                                              │')
    print('  │  ★ 这个窗口不要关，关了虚拟手机就没网了。    │')
    print('  │    演示结束后，直接关掉这个窗口即可。        │')
    print('  └──────────────────────────────────────────────┘')
    print('')

    sys.argv = [server_py]
    runpy.run_path(server_py, run_name='__main__')
