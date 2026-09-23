"""Install and verify only the two public model files required by the studio."""
import concurrent.futures
import hashlib
from pathlib import Path
import runpy
import requests

ROOT = Path(__file__).resolve().parents[1]
part = runpy.run_path(str(Path(__file__).with_name('download-planner.py')))['part']
MODELS = [
    ('stable-diffusion-v1-5/stable-diffusion-v1-5', 'v1-5-pruned-emaonly.safetensors', 'checkpoints'),
    ('guoyww/animatediff', 'mm_sd_v15_v2.ckpt', 'animatediff_models'),
    ('Lykon/DreamShaper', 'DreamShaper_8_pruned.safetensors', 'checkpoints'),
]

for repo, name, directory in MODELS:
    r = requests.get(f'https://hf-mirror.com/api/models/{repo}?blobs=true', timeout=60)
    r.raise_for_status()
    info = next(x for x in r.json()['siblings'] if x['rfilename'] == name)
    size, sha = info['lfs']['size'], info['lfs']['sha256']
    target = ROOT / '.local/ComfyUI/models' / directory / name
    marker = target.with_suffix(target.suffix+'.verified')
    if target.exists() and target.stat().st_size == size and marker.exists() and marker.read_text() == sha:
        print(f'{name}: already verified',flush=True)
        continue
    parts = ROOT / '.local/downloads' / name
    parts.mkdir(parents=True, exist_ok=True)
    block = 64*1024*1024
    jobs = [(f'https://hf-mirror.com/{repo}/resolve/main/{name}', parts/f'{i:04}.part', start, min(start+block,size)-1) for i,start in enumerate(range(0,size,block))]
    # Reuse fully downloaded blocks from a previous sequential download.
    if target.exists() and target.stat().st_size < size:
        with target.open('rb') as old:
            for _,p,start,end in jobs:
                data = old.read(end-start+1)
                if len(data) != end-start+1:
                    break
                if not p.exists():
                    p.write_bytes(data)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(part,*args) for args in jobs]
        for i,future in enumerate(concurrent.futures.as_completed(futures),1):
            future.result()
            print(f'{name}: {i}/{len(jobs)} blocks',flush=True)
    digest = hashlib.sha256()
    temp = target.with_suffix('.incomplete')
    with temp.open('wb') as out:
        for _,p,_,_ in jobs:
            with p.open('rb') as inp:
                while chunk := inp.read(8*1024*1024):
                    out.write(chunk)
                    digest.update(chunk)
    if digest.hexdigest() != sha:
        raise RuntimeError(f'SHA256 mismatch: {name}')
    temp.replace(target)
    target.with_suffix(target.suffix+'.verified').write_text(sha)
    for _,p,_,_ in jobs:
        p.unlink()
    print(f'{name}: SHA256 verified',flush=True)
