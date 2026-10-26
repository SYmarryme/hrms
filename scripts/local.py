"""Windows/local course runner. Explicit named demo only; never selects the old business DB."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'var/mvp'
PYTHON = RUNTIME / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
NODE = 'node'
NPM = 'npm.cmd' if os.name == 'nt' else 'npm'


def execute(args, **kwargs):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True, **kwargs)


def start(name, stop_file=None):
    from backend.course_demo import validate_demo
    path = validate_demo(name)
    ambient = os.environ.get('HRMS_DATABASE_PATH')
    if ambient and Path(ambient).resolve() != path:
        raise ValueError('HRMS_DATABASE_PATH 指向其他库；请先清除此变量，再显式启动命名演示库')
    origin = 'http://127.0.0.1:3000'
    configured = os.environ.get('HRMS_PUBLIC_ORIGIN')
    if configured and configured != origin:
        raise ValueError('本地入口只使用 http://127.0.0.1:3000，请先清除其他 HRMS_PUBLIC_ORIGIN')
    for port in (8000, 3000):
        with socket.socket() as probe:
            if os.name == 'nt': probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            probe.bind(('127.0.0.1',port))
    env={**os.environ,'HRMS_DATABASE_PATH':str(path),'HRMS_PUBLIC_ORIGIN':origin,'HRMS_LOCAL_ONLY':'1'}
    for key in ('PYTHONPATH','PYTHONHOME','__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS'):env.pop(key,None)
    logs=RUNTIME / 'run';logs.mkdir(parents=True,exist_ok=True)
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    processes=[]
    if stop_file and (not stop_file.resolve().is_relative_to(RUNTIME.resolve()) or stop_file.exists()):
        raise ValueError('无效的测试停止文件')
    with (logs/'backend.log').open('w',encoding='utf-8') as backend_log,(logs/'frontend.log').open('w',encoding='utf-8') as frontend_log:
        try:
            processes.append(subprocess.Popen([str(PYTHON),'-m','uvicorn','backend.app:create_app','--factory','--host','127.0.0.1','--port','8000',
                '--workers','1','--no-proxy-headers','--no-access-log'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=backend_log,stderr=subprocess.STDOUT,**flags))
            processes.append(subprocess.Popen([NODE,str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--config',str(ROOT/'frontend/vite.config.mjs')],
                cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=frontend_log,stderr=subprocess.STDOUT,**flags))
            print(f'虚构课程演示库：{path}\n浏览器打开 {origin}\nCtrl+C 停止；日志仅在 var/mvp/run/。',flush=True)
            while not (stop_file and stop_file.exists()):
                if any(p.poll() is not None for p in processes):raise RuntimeError('启动子进程退出，请查看私有日志')
                time.sleep(.3)
        except KeyboardInterrupt:
            pass
        finally:
            for process in processes:
                if process.poll() is None: process.terminate()
            for process in processes:
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()


def main():
    parser=argparse.ArgumentParser(description='HRMS 课程本地安装、测试与独立演示')
    parser.add_argument('action',choices=['setup','test','demo','start'])
    parser.add_argument('--name',help='命名隔离演示库，创建和启动时必须显式提供')
    parser.add_argument('--stop-file',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    os.chdir(ROOT);sys.path.insert(0,str(ROOT))
    RUNTIME.mkdir(parents=True,exist_ok=True)
    os.environ.update(TEMP=str(RUNTIME),TMP=str(RUNTIME))
    if args.action=='setup':
        if not PYTHON.exists(): execute([sys.executable,'-m','venv',RUNTIME/'venv'])
        execute([PYTHON,'-m','pip','install','-r','requirements/course.lock'])
        execute([NPM,'ci','--prefix','frontend'])
        execute([PYTHON,'-m','pip','check']);return
    if not PYTHON.exists():parser.error('请先执行 setup')
    if args.action=='test':
        execute([PYTHON,'-m','pytest','backend/tests','-q','--tb=short','--basetemp',str(RUNTIME/'tests')])
        for task in ('test','typecheck','build'):execute([NPM,'--prefix','frontend','run',task])
        return
    if not args.name:parser.error('必须显式提供 --name，不会默认选择任何数据库')
    if args.action=='demo':
        if os.environ.get('HRMS_DATABASE_PATH'):parser.error('请先清除 HRMS_DATABASE_PATH，避免配置混淆')
        execute([PYTHON,'-m','backend.course_demo','--name',args.name]);return
    if Path(sys.executable).resolve()!=PYTHON.resolve():
        execute([PYTHON,Path(__file__),'start','--name',args.name,*(['--stop-file',args.stop_file] if args.stop_file else [])]);return
    start(args.name,args.stop_file)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:sys.exit(130)
    except (ValueError,FileExistsError,RuntimeError,OSError,subprocess.CalledProcessError) as error:
        # Never print command arguments containing credentials (the runner accepts none).
        print(f'操作未完成：{error}',file=sys.stderr);sys.exit(1)
