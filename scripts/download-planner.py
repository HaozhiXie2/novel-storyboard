"""Download public Qwen model files with retries and resumable bounded ranges."""
import concurrent.futures
import hashlib
from pathlib import Path
import time
import requests
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = sys.argv[1] if len(sys.argv) > 1 else 'Qwen/Qwen2.5-1.5B-Instruct'
SOURCE = sys.argv[2] if len(sys.argv) > 2 else 'hf-mirror'


def dest_for(repo):
    if '14B' in repo:
        name = 'planner-14b'
    elif '7B' in repo or '8B' in repo:
        name = 'planner-7b'
    elif '4B' in repo:
        name = 'planner-4b'
    elif '3B' in repo:
        name = 'planner-3b'
    else:
        name = 'planner'
    return ROOT / '.local/models' / name


DEST = dest_for(REPO)
BASE = f'https://hf-mirror.com/{REPO}/resolve/main/'


def part(url, path, start, end):
    expected = end-start+1
    for attempt in range(6):
        try:
            offset = path.stat().st_size if path.exists() else 0
            if offset == expected:
                return
            with requests.get(url, headers={'Range':f'bytes={start+offset}-{end}'}, stream=True, timeout=(30,60)) as r:
                r.raise_for_status()
                content_range = r.headers.get('Content-Range', '')
                if r.status_code not in (200, 206) or not content_range.startswith(f'bytes {start+offset}-{end}/'):
                    raise RuntimeError(f'Server did not honor byte range: {r.status_code} {content_range}')
                with path.open('ab') as f:
                    for data in r.iter_content(1024*1024):
                        if data:
                            f.write(data)
            if path.stat().st_size != expected:
                raise RuntimeError('Incomplete range')
            return
        except Exception:
            if attempt == 5:
                raise
            time.sleep(min(2**attempt, 15))


def modelscope_files():
    meta = requests.get(f'https://www.modelscope.cn/api/v1/models/{REPO}/repo/files', params={'Revision': 'master', 'Recursive': 'True'}, timeout=60)
    meta.raise_for_status()
    files = []
    for item in meta.json()['Data']['Files']:
        name = item['Path']
        if '/' in name or not name.endswith(('.json', '.txt', '.safetensors')):
            continue
        if name == 'configuration.json':
            continue
        files.append((name, int(item['Size']), item.get('Sha256') or ''))
    return files


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    if SOURCE == 'modelscope':
        listing = modelscope_files()
        base = f'https://www.modelscope.cn/models/{REPO}/resolve/master/'
    else:
        meta = requests.get(f'https://hf-mirror.com/api/models/{REPO}?blobs=true', timeout=60)
        meta.raise_for_status()
        listing = []
        for item in meta.json()['siblings']:
            name = item['rfilename']
            if '/' in name or not name.endswith(('.json', '.txt', '.safetensors')):
                continue
            if name.endswith('.safetensors'):
                listing.append((name, item['lfs']['size'], item['lfs']['sha256']))
            else:
                listing.append((name, None, ''))
    for name, size, sha in listing:
        target = DEST/name
        url = base+name
        if name.endswith('.safetensors'):
            parts = DEST / '.parts' / name
            parts.mkdir(parents=True, exist_ok=True)
            block = 64*1024*1024
            jobs = [(url, parts/f'{i:04}.part', start, min(start+block,size)-1) for i,start in enumerate(range(0,size,block))]
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                futures = [executor.submit(part,*args) for args in jobs]
                for i,future in enumerate(concurrent.futures.as_completed(futures),1):
                    future.result()
                    print(f'Model pieces {i}/{len(jobs)}',flush=True)
            digest = hashlib.sha256()
            temp = target.with_suffix('.incomplete')
            with temp.open('wb') as out:
                for _, path, _, _ in jobs:
                    with path.open('rb') as inp:
                        while chunk := inp.read(8*1024*1024):
                            digest.update(chunk)
                            out.write(chunk)
            if digest.hexdigest() != sha:
                raise RuntimeError('Model SHA256 mismatch')
            temp.replace(target)
            for _,path,_,_ in jobs:
                path.unlink()
            print('Model SHA256 verified',flush=True)
        else:
            r = requests.get(url,timeout=60)
            r.raise_for_status()
            target.write_bytes(r.content)
            print(name,flush=True)
    (DEST/'READY').write_text(REPO+'\nSHA256 verified\n')


if __name__ == '__main__':
    main()
