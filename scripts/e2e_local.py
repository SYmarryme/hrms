"""Allocate a new disposable fictional DB and run actual installed Edge against live Vite/FastAPI."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import socket
from urllib.request import urlopen
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    # Each spec gets a new random fictional database/server and the unchanged login limiter.
    # This also prevents one spec's organization or role changes affecting the next spec.
    if len(sys.argv)==1:
        for spec in sorted((ROOT/'frontend/e2e').glob('*.spec.ts')):
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),spec.name],cwd=ROOT)
            if result.returncode:return result.returncode
        return 0
    import json
    from backend.course_demo import create_demo, demo_path
    from backend.settings import Settings
    from scripts.local import PYTHON
    web_port=int(os.environ.get('HRMS_E2E_FRONTEND_PORT','3000'))
    api_port=int(os.environ.get('HRMS_E2E_BACKEND_PORT','8000'))
    if not (1024<=web_port<=65535 and 1024<=api_port<=65535 and web_port!=api_port):raise ValueError('Use two distinct unprivileged local test ports')
    origin=f'http://127.0.0.1:{web_port}'
    # Never accept a stale server's health response with a different fixture/password set.
    for port in (web_port,api_port):
        with socket.socket() as probe:
            if os.name=='nt':probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            probe.bind(('127.0.0.1',port))
    name='e2e-'+uuid4().hex[:12]
    passwords={role:secrets.token_urlsafe(24) for role in ('admin','hr','manager','employee')}
    create_demo(Settings(demo_path(name),origin),passwords)
    env=dict(os.environ)
    env.pop('HRMS_DATABASE_PATH',None);env.pop('HRMS_PUBLIC_ORIGIN',None)
    folder=ROOT/'var/mvp';folder.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(folder),TMP=str(folder))
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    run=folder/name;run.mkdir(exist_ok=False)
    # Only the disposable test server changes ports; the application config stays unchanged.
    config=run/'vite.config.mjs'
    base_config=(ROOT/'frontend/vite.config.mjs').as_uri()
    config.write_text('import base from '+json.dumps(base_config)+';\nbase.server.port='+str(web_port)+';\nbase.server.proxy["/api/"].target='+json.dumps(f'http://127.0.0.1:{api_port}')+';\nexport default base;\n',encoding='utf-8')
    env.update(HRMS_DATABASE_PATH=str(demo_path(name)),HRMS_PUBLIC_ORIGIN=origin,HRMS_LOCAL_ONLY='1')
    for key in ('PYTHONPATH','PYTHONHOME','__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS'):env.pop(key,None)
    processes=[]
    with (run/'backend.log').open('w',encoding='utf-8') as backend_log,(run/'frontend.log').open('w',encoding='utf-8') as frontend_log:
        try:
            processes.append(subprocess.Popen([str(PYTHON),'-m','uvicorn','backend.app:create_app','--factory','--host','127.0.0.1','--port',str(api_port),'--workers','1','--no-proxy-headers','--no-access-log'],cwd=ROOT,env=env,stdout=backend_log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,**flags))
            processes.append(subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--config',str(config)],cwd=ROOT,env=env,stdout=frontend_log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,**flags))
            for _ in range(100):
                if any(p.poll() is not None for p in processes):raise RuntimeError('E2E server exited')
                try:
                    with urlopen(origin+'/api/v1/health',timeout=1) as response:
                        if response.status==200:break
                except OSError:time.sleep(.2)
            else:raise RuntimeError('E2E server not ready')
            result=subprocess.run(['node',str(ROOT/'frontend/node_modules/@playwright/test/cli.js'),'test','--config',str(ROOT/'frontend/playwright.config.ts'),*sys.argv[1:]],
                cwd=ROOT/'frontend',env={**env,'HRMS_E2E_BASE_URL':origin,'HRMS_E2E_PASSWORDS':json.dumps(passwords)})
            return result.returncode
        finally:
            for process in processes:
                if process.poll() is None:process.terminate()
            for process in processes:
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()



if __name__=='__main__':sys.exit(main())
