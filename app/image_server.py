"""Local Dreamina image/video workstation; generation is never retried automatically."""
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'media-tasks/images'
CLI = ROOT / '.tools/dreamina.exe'
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
QUERY_LOCKS = {}
ACTIVE = {'new', 'submitting', 'waiting', 'downloading'}
VIDEO_MODELS = [
    {'id': 'seedance2.0fast_vip', 'label': 'Seedance 2.0 Fast · 会员', 'description': '使用会员模型验证短镜头；实际速度与用量以平台为准，仍可能排队'},
    {'id': 'seedance2.0_vip', 'label': 'Seedance 2.0 · 会员', 'description': '需账号具备权限，生成后可下载原始 MP4'},
    {'id': 'seedance1.0fast', 'label': 'Seedance 1.0 Fast', 'description': '较早的视频模型，适合简单动作；质量与速度需要实测'},
]


def cli(*args):
    result = subprocess.run([str(CLI), *args], capture_output=True, encoding='utf-8', errors='replace', timeout=120,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError((result.stderr or result.stdout or '即梦未返回有效结果')[:1000])
    if result.returncode:
        raise RuntimeError(json.dumps(data, ensure_ascii=False)[:1000])
    return data


def folder(key):
    if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{32}', key):
        raise ValueError('无效任务编号')
    path = STORE / key
    if path.is_symlink() or path.resolve().parent != STORE.resolve():
        raise ValueError('无效任务目录')
    return path


def read_job(key):
    with LOCK:
        return json.loads((folder(key) / 'job.json').read_text(encoding='utf-8'))


def save(job):
    with LOCK:
        job['updated'] = time.time()
        path = folder(job['id']) / 'job.json'
        tmp = path.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as output:
            json.dump(job, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)


def listing():
    with LOCK:
        jobs = []
        for path in STORE.glob('*/job.json'):
            try:
                job = json.loads(path.read_text(encoding='utf-8'))
                if (not isinstance(job, dict) or job.get('id') != path.parent.name
                        or not isinstance(job.get('created'), (int, float))
                        or not isinstance(job.get('status'), str)
                        or job.get('status') not in ACTIVE | {'done', 'failed', 'uncertain'}
                        or not isinstance(job.get('images', []), list)
                        or not isinstance(job.get('videos', []), list)
                        or not all(isinstance(name, str) for name in job.get('images', []) + job.get('videos', []))):
                    raise ValueError('无效任务记录')
                folder(job['id'])
                job.setdefault('kind', 'image')
                job.setdefault('videos', [])
                job.setdefault('request_id', job['id'])
                jobs.append(job)
            except (ValueError, OSError):
                # One damaged file must not stop polling all other paid tasks.
                jobs.append({'id': path.parent.name, 'kind': 'image', 'created': 0, 'status': 'uncertain',
                             'message': '本地任务记录无法读取，请检查 job.json；未重新提交', 'images': [], 'videos': []})
        return sorted(jobs, key=lambda job: job['created'], reverse=True)


def media_file(job, name):
    if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('无效媒体文件名')
    if name not in job.get('images', []) + job.get('videos', []) + [job.get('preview_video')]:
        raise ValueError('媒体文件不存在')
    path = (folder(job['id']) / name).resolve()
    if path.parent != folder(job['id']).resolve() or not path.is_file():
        raise ValueError('媒体文件不存在')
    return path


def query(job):
    with LOCK:
        query_lock = QUERY_LOCKS.setdefault(job['id'], threading.Lock())
    if not query_lock.acquire(blocking=False):
        return
    try:
        current = read_job(job['id'])
        if current['status'] not in ('waiting', 'downloading') or not current.get('submit_id'):
            return
        try:
            _query(current)
        except Exception as exc:
            current.update(query_error=str(exc), last_checked=time.time())
            save(current)
        job.update(current)
    finally:
        query_lock.release()


def _query(job):
    result = cli('query_result', '--submit_id=' + job['submit_id'])
    state = result.get('gen_status')
    if result.get('credit_count') is not None:
        job['credits'] = result['credit_count']
    job['last_checked'] = time.time()
    job.pop('query_error', None)
    if state == 'success':
        job.update(status='downloading', message='生成完成，正在下载到本机', queue_position=None)
        save(job)
        cli('query_result', '--submit_id=' + job['submit_id'], '--download_dir=' + str(folder(job['id'])))
        is_video = job.get('kind') == 'video'
        extensions = ('.mp4', '.webm', '.mov') if is_video else ('.png', '.jpg', '.jpeg', '.webp')
        files = sorted(p.name for p in folder(job['id']).iterdir() if p.is_file() and p.suffix.lower() in extensions and p.stat().st_size > 0 and not p.name.startswith('preview.'))
        if not files:
            raise RuntimeError('生成已完成，文件暂未下载成功；稍后只重试下载，不重新生成')
        job['videos' if is_video else 'images'] = files
        job.update(status='done', message='视频已完成，可播放和下载' if is_video else '图片已生成，可用于制作视频', completed_at=time.time())
    elif state == 'fail':
        job.update(status='failed', message=result.get('fail_reason') or '即梦返回生成失败', queue_position=None)
    else:
        queue = result.get('queue_info') or {}
        job.update(status='waiting', message='即梦排队中' if queue.get('queue_status') == 'Queueing' else '即梦正在生成',
                   queue_position=queue.get('queue_idx'), queue_length=queue.get('queue_length'))
    save(job)


def find_ffmpeg():
    candidates = [ROOT / '.tools/ffmpeg.exe']
    candidates += sorted((ROOT / '.local/venv/Lib/site-packages/imageio_ffmpeg/binaries').glob('ffmpeg-*.exe'))
    return next((path for path in candidates if path.is_file()), None)


def make_preview(job):
    """Local WebM browser copy; the original video remains the download deliverable."""
    with LOCK:
        preview_lock = QUERY_LOCKS.setdefault(job['id'], threading.Lock())
    if not preview_lock.acquire(blocking=False):
        return
    try:
        current = read_job(job['id'])
        if current.get('kind') != 'video' or current['status'] != 'done' or current.get('preview_status'):
            return
        try:
            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                raise RuntimeError('本机未安装视频兼容转换工具，可下载原始 MP4 在系统播放器播放')
            source = media_file(current, current['videos'][0])
            partial = folder(current['id']) / 'preview.part.webm'
            output = folder(current['id']) / 'preview.webm'
            current.update(preview_status='converting')
            save(current)
            result = subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                                     '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
                                     '-vf', 'scale=720:-2', '-r', '24', '-c:v', 'libvpx-vp9',
                                     '-deadline', 'realtime', '-cpu-used', '6', '-b:v', '1600k',
                                     '-pix_fmt', 'yuv420p', '-threads', '2', '-c:a', 'libopus', '-b:a', '96k', str(partial)],
                                    capture_output=True, encoding='utf-8', errors='replace', timeout=180,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode or not partial.is_file() or partial.stat().st_size == 0:
                raise RuntimeError((result.stderr or '视频预览转换失败')[-1000:])
            os.replace(partial, output)
            current.update(preview_status='ready', preview_video=output.name)
            current.pop('preview_error', None)
        except Exception as exc:
            current.update(preview_status='failed', preview_error=str(exc))
        save(current)
        job.update(current)
    finally:
        preview_lock.release()


def submission_args(job):
    if job.get('kind', 'image') == 'image':
        return ['text2image', '--prompt=' + job['prompt'], '--ratio=' + job['ratio'], '--model_version=5.0',
                '--resolution_type=2k', '--generate_num=1', '--poll=0']
    source = read_job(job['source_job'])
    reference = media_file(source, job['source_image'])
    return ['image2video', '--image=' + str(reference), '--prompt=' + job['prompt'],
            '--model_version=' + job['model'], '--duration=' + str(job['duration']), '--ratio=' + job['ratio'],
            '--video_resolution=720p', '--poll=0']


def submit(job):
    try:
        args = submission_args(job)
    except Exception as exc:
        job.update(status='failed', message='提交前检查失败，未调用生成接口', detail=str(exc))
        save(job)
        return
    try:
        job.update(status='submitting', message='正在提交给即梦')
        save(job)  # Must be durable before the non-idempotent remote call.
        result = cli(*args)
        if not result.get('submit_id'):
            if result.get('gen_status') == 'fail':
                job.update(status='failed', message=result.get('fail_reason') or '平台拒绝生成请求')
                save(job)
                return
            raise RuntimeError(json.dumps(result, ensure_ascii=False)[:1000])
        job.update(submit_id=result['submit_id'], status='waiting', message='已提交，等待即梦处理', credits=result.get('credit_count'))
        save(job)
    except Exception as exc:
        job.update(status='waiting' if job.get('submit_id') else 'uncertain',
                   message='任务已提交，将继续查询原任务' if job.get('submit_id') else '提交结果未确认，未自动重试以避免重复扣费。请核对即梦任务记录。', detail=str(exc))
        save(job)


def create_job(data, kind):
    """Validate, reserve and persist before dispatch; repeated HTTP requests return same job."""
    key = data.get('request_id', '')
    target = folder(key)
    prompt = data.get('prompt', '')
    if not isinstance(prompt, str) or not 2 <= len(prompt.strip()) <= 5000:
        raise ValueError('请输入 2 到 5000 字的画面或动作描述')
    fields = {'kind': kind, 'prompt': prompt.strip()}
    if kind == 'video':
        source = read_job(data.get('source_job', ''))
        if source.get('kind', 'image') != 'image' or source['status'] != 'done':
            raise ValueError('请先选择一张已生成的图片')
        name = data.get('source_image')
        if name not in source.get('images', []):
            raise ValueError('参考图不属于选中的图片任务')
        media_file(source, name)
        model = data.get('model', VIDEO_MODELS[0]['id'])
        if model not in {m['id'] for m in VIDEO_MODELS}:
            raise ValueError('不支持的视频模型')
        duration = data.get('duration', 5)
        if type(duration) is not int or duration not in (5, 10):
            raise ValueError('目前支持 5 秒或 10 秒短镜头')
        fields.update(source_job=source['id'], source_image=name, model=model, duration=duration, ratio=source['ratio'])
    else:
        ratio = data.get('ratio', '9:16')
        if ratio not in ('9:16', '16:9', '1:1', '3:4'):
            raise ValueError('不支持的比例')
        fields.update(ratio=ratio, model='5.0')
    fingerprint = hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    with LOCK:
        if (target / 'job.json').exists():
            existing = read_job(key)
            if existing.get('fingerprint') != fingerprint:
                raise ValueError('同一提交编号的内容发生变化，请刷新页面后重新确认')
            return existing, False
        existing_jobs = listing()
        for existing in existing_jobs:
            if existing.get('fingerprint') == fingerprint and existing['status'] in ACTIVE | {'uncertain'}:
                return existing, False
        for existing in existing_jobs:
            if existing.get('kind', 'image') == kind and existing['status'] in ACTIVE:
                raise ValueError('已有同类型任务在处理，请等待完成后再提交')
        target.mkdir(parents=True, exist_ok=True)
        job = dict(fields, id=key, request_id=key, created=time.time(), status='new', message='准备提交', images=[], videos=[], fingerprint=fingerprint)
        save(job)
        return job, True


def recover():
    for job in listing():
        if job.get('preview_status') == 'converting':
            job.pop('preview_status', None)
            save(job)
        if job['status'] in ('new', 'submitting') or (job['status'] == 'uncertain' and job.get('submit_id')):
            job.update(status='waiting' if job.get('submit_id') else 'uncertain',
                       message='恢复原任务查询' if job.get('submit_id') else '上次提交中断，请核对即梦任务记录；不会自动重复提交')
            save(job)


def poll_once():
    for job in listing():
        if job['status'] in ('waiting', 'downloading') and job.get('submit_id'):
            try:
                query(job)
            except Exception as exc:
                # A corrupt record must not stop the next task or write stale state.
                print(f"Query skipped for {job['id']}: {exc}", flush=True)
        if job.get('kind') == 'video' and job['status'] == 'done' and not job.get('preview_status'):
            try:
                make_preview(job)
            except Exception as exc:
                print(f"Preview skipped for {job['id']}: {exc}", flush=True)


def poll():
    while True:
        try:
            poll_once()
        except Exception as exc:
            print(f'Query loop will retry: {exc}', flush=True)
        time.sleep(15)


class Handler(BaseHTTPRequestHandler):
    def send(self, data, kind='application/json; charset=utf-8', code=200):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command == 'HEAD':
            return
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def valid_host(self):
        return self.headers.get('Host') in ('127.0.0.1:7861', 'localhost:7861')

    def send_file(self, path):
        total = path.stat().st_size
        start, end, code = 0, total - 1, 200
        byte_range = self.headers.get('Range')
        if byte_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', byte_range)
            if not match or not any(match.groups()):
                self.send_error(416)
                return
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), total - 1) if right else total - 1
            else:
                start = max(0, total - int(right))
            if start > end or start >= total:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{total}')
                self.end_headers()
                return
            code = 206
        self.send_response(code)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if code == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
        self.end_headers()
        if self.command == 'HEAD':
            return
        try:
            with path.open('rb') as stream:
                stream.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = stream.read(min(left, 65536))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.valid_host():
            return self.send({'error': '仅支持本机访问'}, code=403)
        try:
            route = urlsplit(self.path).path
            if route == '/':
                return self.send((ROOT / 'app/images.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN).encode(), 'text/html; charset=utf-8')
            if route == '/api/jobs':
                return self.send(listing())
            if route == '/api/models':
                return self.send(VIDEO_MODELS)
            if route == '/api/status':
                return self.send({'app': 'novel-film-studio', 'version': 2, 'cli_available': CLI.is_file()})
            if route == '/api/account':
                result = cli('user_credit')
                return self.send({'credits': result.get('total_credit'), 'membership': result.get('vip_level')})
            parts = route.split('/')
            if len(parts) == 4 and parts[1] in ('images', 'media'):
                return self.send_file(media_file(read_job(parts[2]), unquote(parts[3])))
            return self.send({'error': '页面不存在'}, code=404)
        except Exception as exc:
            return self.send({'error': str(exc)}, code=400)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Studio-Token') != TOKEN:
            return self.send({'error': '请刷新页面'}, code=403)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size < 40000:
                raise ValueError('请求大小超出限制')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('请求内容无效')
            route = urlsplit(self.path).path
            if route not in ('/api/generate', '/api/video'):
                return self.send({'error': '未知操作'}, code=404)
            job, created = create_job(data, 'video' if route == '/api/video' else 'image')
            if created:
                threading.Thread(target=submit, args=(job,), daemon=True).start()
            return self.send(job, code=201 if created else 200)
        except Exception as exc:
            return self.send({'error': str(exc)}, code=400)


if __name__ == '__main__':
    STORE.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer(('127.0.0.1', 7861), Handler)
    recover()
    threading.Thread(target=poll, daemon=True).start()
    httpd.serve_forever()
