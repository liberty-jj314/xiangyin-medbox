# -*- coding: utf-8 -*-
"""一键执行离线检查，不读取真实接口凭证、不调用真实供应商。"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    output = args.output or here.parent / '01_资料/评测结果/20261019_离线回归'
    output.mkdir(parents=True, exist_ok=True)
    if not shutil.which('node'):
        print('前端回归需要Node.js；当前未找到node，检查未完成。应用本身不要求Node。')
        return 1
    critical = [here/'ui_presentation.js', here/'server.py', here/'index.html', here/'recorder.js', here/'review_store.py', here/'region_lookup.py', here/'admin.html',
                here.parent/'01_资料/药品数据.json', here.parent/'01_资料/药品审核状态.json', here.parent/'01_资料/实物药品资料.json', here/'voice_catalog.json']
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in critical}
    checks = [
        ['verify_audio_transport.py'],
        ['verify_location_confirmation.py'],
        ['verify_teacher_mvp.py'],
        ['verify_indication_scope.py'],
        ['verify_mvp.py'],
        ['verify_audio589.py'],
        ['verify_two_products.py'],
        ['verify_asr_service.py'],
        ['verify_location_accuracy.py'],
        ['verify_review_features.py'],
        ['verify_leaflet_profiles.py'],
        ['verify_current_testset.py'],
        ['verify_20261016.py'],
        ['verify_safety_20261019.py', '--json', str((output/'安全HTTP回归.json').resolve())],
    ]
    records = []
    for arguments in checks:
        result = subprocess.run([sys.executable, '-X', 'utf8', *arguments], cwd=here,
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        logfile = output/(Path(arguments[0]).stem+'.log')
        logfile.write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
        record = dict(command=' '.join(arguments), exit_code=result.returncode, log=logfile.name)
        records.append(record)
        print(('通过' if result.returncode == 0 else '失败') + '：' + arguments[0])
        if result.returncode:
            print((result.stdout + '\n' + result.stderr)[-1600:])
    unchanged = all(hashlib.sha256(path.read_bytes()).hexdigest() == before[str(path)] for path in critical)
    success = unchanged and all(record['exit_code'] == 0 for record in records)
    summary = dict(build='20261028-step1', passed=success, checks=records,
                   critical_files_unchanged=unchanged, paid_api_calls=0,
                   scope='判定器自检、原验证器、隔离HTTP与原JS状态模拟；不是临床或真实模型准确率')
    (output/'汇总.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('结果目录：' + str(output))
    print('不同检查存在重叠，不把通过数相加当作准确率。')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
