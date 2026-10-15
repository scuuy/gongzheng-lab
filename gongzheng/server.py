"""Local review UI. Native work runs in disposable network-isolated containers."""
import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
JOBS = {}
LOCK = threading.Lock()
CAPACITY = threading.BoundedSemaphore(2)
CASES = {'normal', 'clearance', 'variant', 'stale-mesh', 'load-sign', 'report'}
IMAGE = os.environ.get('GONGZHENG_IMAGE', 'gongzheng-native:0.1.0')


def work(job, case, action):
    out = ROOT / 'runs' / job
    out.mkdir(parents=True)
    with CAPACITY:
        JOBS[job]['status'] = 'running'
        operation = 'apply-proposal' if action == 'model-proposal' else action
        inputs = [f'/app/examples/{case}']
        if action == 'model-proposal':
            inputs.append(f'/app/examples/{case}-model-proposal.json')
        cmd = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,size=256m',
               '--cpus', '2', '--memory', '4g', '--pids-limit', '128', '--user', '0:0',
               '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'OPENBLAS_NUM_THREADS=1', '-e', 'OMP_NUM_THREADS=1',
               '-v', f'{ROOT}:/app:ro', '-v', f'{out}:/output:rw', '-w', '/app',
               '--entrypoint', 'python', IMAGE, '-m', 'gongzheng.cli', operation,
               *inputs, '--out', '/output']
        started = time.monotonic()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            (out / 'process.log').write_text(p.stdout + '\n' + p.stderr)
            report_path = out / ('verification/acceptance.json' if action in ('repair', 'model-proposal') else 'acceptance.json')
            if p.returncode or not report_path.exists():
                raise RuntimeError('Native tool did not complete; see process.log')
            report = json.loads(report_path.read_text())
            JOBS[job].update(status='completed', report=report, duration_s=round(time.monotonic() - started, 2))
        except Exception as e:
            JOBS[job].update(status='infra_error', error=str(e), duration_s=round(time.monotonic() - started, 2))
        (out / 'job.json').write_text(json.dumps(JOBS[job], ensure_ascii=False, indent=2))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, data, status=200):
        blob = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(blob)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/cases':
            return self.send_json(json.loads((ROOT / 'examples/catalog.json').read_text()))
        if parsed.path == '/api/model-demos':
            path = ROOT / 'docs/evidence/model-demo.json'
            return self.send_json(json.loads(path.read_text()) if path.exists() else [])
        if parsed.path == '/api/job':
            job = parse_qs(parsed.query).get('id', [''])[0]
            return self.send_json(JOBS.get(job, {'status': 'not_found'}))
        if parsed.path == '/api/saved':
            case = parse_qs(parsed.query).get('case', ['normal'])[0]
            if case not in CASES:
                return self.send_json({'error': 'unknown case'}, 400)
            p = ROOT / 'runs/regression' / case / 'acceptance.json'
            return self.send_json({'mode': 'saved_native_run', 'report': json.loads(p.read_text())} if p.exists() else {'error': 'Run regression first'}, 200 if p.exists() else 404)
        if parsed.path.startswith('/artifacts/'):
            rel = parsed.path[len('/artifacts/'):]
            target = (ROOT / rel).resolve()
            if not target.is_relative_to(ROOT / 'examples') and not target.is_relative_to(ROOT / 'runs'):
                return self.send_json({'error': 'outside artifact roots'}, 403)
            if target.suffix not in ('.json', '.step', '.msh', '.inp', '.dat', '.frd', '.log', '.png'):
                return self.send_json({'error': 'unsupported artifact'}, 403)
        else:
            rel = parsed.path.lstrip('/') or 'index.html'
            target = (ROOT / 'web' / rel).resolve()
            if not target.is_relative_to(ROOT / 'web'):
                return self.send_json({'error': 'outside web root'}, 403)
        if not target.is_file():
            return self.send_json({'error': 'not found'}, 404)
        types = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml'}
        self.send_response(200); self.send_header('Content-Type', types.get(target.suffix, 'application/octet-stream'))
        self.end_headers(); self.wfile.write(target.read_bytes())

    def do_POST(self):
        origin = self.headers.get('Origin')
        host = self.headers.get('Host')
        if origin and origin != 'http://' + host:
            return self.send_json({'error': 'cross-origin request denied'}, 403)
        if self.path != '/api/run':
            return self.send_json({'error': 'unknown endpoint'}, 404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.send_json({'error': 'invalid content length'}, 400)
        if length < 0 or length > 1024:
            return self.send_json({'error': 'request too large'}, 413)
        try:
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('expected object')
        except Exception:
            return self.send_json({'error': 'invalid JSON'}, 400)
        case, action = data.get('case'), data.get('action', 'verify')
        if not isinstance(case, str) or not isinstance(action, str) or case not in CASES or action not in ('verify', 'repair', 'model-proposal'):
            return self.send_json({'error': 'unknown case/action'}, 400)
        if action == 'model-proposal' and case not in ('variant', 'clearance'):
            return self.send_json({'error': 'no saved model proposal for this case'}, 400)
        with LOCK:
            if sum(j['status'] in ('queued', 'running') for j in JOBS.values()) >= 4:
                return self.send_json({'error': 'Queue full; wait for active jobs'}, 429)
            job = uuid.uuid4().hex[:12]
            JOBS[job] = {'id': job, 'case': case, 'action': action, 'status': 'queued', 'image': IMAGE}
        threading.Thread(target=work, args=(job, case, action), daemon=True).start()
        self.send_json({'id': job, 'status': 'queued'}, 202)


def serve(port=8770):
    print(f'工证 Lab: http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
