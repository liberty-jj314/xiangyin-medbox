# -*- coding: utf-8 -*-
"""三个启动入口共用的服务启动器；只检查本机，不调用供应商接口。"""
from contextlib import contextmanager
from pathlib import Path
import json
import hashlib
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

BUILD = '20261028-step1'
HERE = Path(__file__).resolve().parent


def probe(port=8000):
    """0: 当前版本；1: 空闲；2: 其他服务或版本。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open('http://127.0.0.1:%d/api/version' % port, timeout=2) as response:
            data = json.loads(response.read(4096))
        project_id = hashlib.sha256(os.path.normcase(os.path.realpath(str(HERE))).encode('utf-8')).hexdigest()
        return 0 if isinstance(data, dict) and data.get('build') == BUILD and data.get('project_id') == project_id else 2
    except Exception:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return 2
        except OSError:
            return 1


@contextmanager
def startup_lock(port=8000):
    import msvcrt
    lock_path = Path(tempfile.gettempdir()) / ('xiangyin_start_%d.lock' % port)
    with lock_path.open('a+b') as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b'0')
            handle.flush()
        acquired = False
        deadline = time.monotonic() + 45
        try:
            while not acquired:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('另一个入口仍在启动，请稍后重试。')
                    time.sleep(.15)
            yield
        finally:
            if acquired:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def spawn_service():
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 6  # 保留可关闭的最小化服务窗口。
    return subprocess.Popen([sys.executable, str(HERE / 'demo_server.py')],
                            cwd=str(HERE), startupinfo=info,
                            creationflags=subprocess.CREATE_NEW_CONSOLE)


def ensure_running(port=8000, start=None):
    with startup_lock(port):
        state = probe(port)
        if state != 1:
            return state
        process = (start or spawn_service)()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = probe(port)
            if state == 0:
                return 0
            if state == 2:
                return 2
            if process.poll() is not None:
                return 1
            time.sleep(.3)
        return 1


def main():
    try:
        result = ensure_running()
    except Exception as error:
        print('启动未完成：' + str(error))
        return 1
    if result == 0:
        print('后台已就绪，正在打开所选界面。')
    elif result == 2:
        print('8000端口已被其他程序或旧版本占用，请先关闭旧服务。')
    else:
        print('后台未启动成功，请查看最小化服务窗口后重试。')
    return result


if __name__ == '__main__':
    raise SystemExit(main())
