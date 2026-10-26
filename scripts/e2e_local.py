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
    # Never accept a stale server's health response with a different fixture/password set.
    for port in (3000,8000):
        with socket.socket() as probe:
            if os.name=='nt':probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            probe.bind(('127.0.0.1',port))
    name='e2e-'+uuid4().hex[:12]
    passwords={role:secrets.token_urlsafe(24) for role in ('admin','hr','manager','employee')}
    create_demo(Settings(demo_path(name),'http://127.0.0.1:3000'),passwords)
    env=dict(os.environ)
    env.pop('HRMS_DATABASE_PATH',None);env.pop('HRMS_PUBLIC_ORIGIN',None)
    folder=ROOT/'var/mvp';folder.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(folder),TMP=str(folder))
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    stop_file=folder/(name+'.stop')
    # Private completion file avoids Windows console/stdin ownership races.
    with (folder/'e2e-server.log').open('w',encoding='utf-8') as log:
        server=subprocess.Popen([str(PYTHON),'scripts/local.py','start','--name',name,'--stop-file',str(stop_file)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,**flags)
        try:
            for _ in range(100):
                if server.poll() is not None:raise RuntimeError('E2E server exited')
                try:
                    with urlopen('http://127.0.0.1:3000/api/v1/health',timeout=1) as response:
                        if response.status==200:break
                except OSError:time.sleep(.2)
            else:raise RuntimeError('E2E server not ready')
            result=subprocess.run(['node',str(ROOT/'frontend/node_modules/@playwright/test/cli.js'),'test','--config',str(ROOT/'frontend/playwright.config.ts'),*sys.argv[1:]],
                cwd=ROOT/'frontend',env={**env,'HRMS_E2E_PASSWORDS':json.dumps(passwords)})
            return result.returncode
        finally:
            if server.poll() is None:
                stop_file.touch();server.wait(timeout=20)


if __name__=='__main__':sys.exit(main())
