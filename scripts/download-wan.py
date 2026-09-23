"""Download Wan 2.1 1.3B text-to-video weights that fit a 12 GB GPU."""
import concurrent.futures
import hashlib
from pathlib import Path
import shutil
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
REPO = "Comfy-Org/Wan_2.1_ComfyUI_repackaged"
BASE = f"https://www.modelscope.cn/models/{REPO}/resolve/master/"
MODELS = ROOT / ".local" / "ComfyUI" / "models"
WANTED = {
    "split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors": MODELS / "diffusion_models" / "wan2.1_t2v_1.3B_fp16.safetensors",
    "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors": MODELS / "text_encoders" / "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "split_files/vae/wan_2.1_vae.safetensors": MODELS / "vae" / "wan_2.1_vae.safetensors",
}


def part(url, path, start, end):
    expected = end - start + 1
    for attempt in range(6):
        try:
            offset = path.stat().st_size if path.exists() else 0
            if offset == expected:
                return
            if offset > expected:
                path.unlink()
                offset = 0
            with requests.get(url, headers={"Range": f"bytes={start + offset}-{end}"}, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                content_range = response.headers.get("Content-Range", "")
                if response.status_code not in (200, 206) or not content_range.startswith(f"bytes {start + offset}-{end}/"):
                    raise RuntimeError(f"Server did not honor byte range: {response.status_code} {content_range}")
                with path.open("ab") as handle:
                    for data in response.iter_content(1024 * 1024):
                        if data:
                            handle.write(data)
            if path.stat().st_size != expected:
                raise RuntimeError("Incomplete range")
            return
        except Exception:
            if attempt == 5:
                raise
            time.sleep(min(2 ** attempt, 15))


def listing():
    meta = requests.get(
        f"https://www.modelscope.cn/api/v1/models/{REPO}/repo/files",
        params={"Revision": "master", "Recursive": "True"},
        timeout=60,
    )
    meta.raise_for_status()
    found = {}
    for item in meta.json()["Data"]["Files"]:
        name = item.get("Path") or item.get("Name")
        if name in WANTED:
            found[name] = (int(item["Size"]), item.get("Sha256") or item.get("sha256") or "")
    missing = [name for name in WANTED if name not in found]
    if missing:
        raise RuntimeError("ModelScope listing missing: " + ", ".join(missing))
    return found


def fetch(remote, target, size, sha):
    marker = target.with_name(target.name + ".verified")
    if target.exists() and marker.exists() and target.stat().st_size == size:
        print(f"already verified {target.name}", flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    parts = MODELS / ".wan-parts" / target.name
    parts.mkdir(parents=True, exist_ok=True)
    url = BASE + remote
    block = 64 * 1024 * 1024
    jobs = [(url, parts / f"{i:04}.part", start, min(start + block, size) - 1) for i, start in enumerate(range(0, size, block))]
    print(f"downloading {target.name} ({size / 1024**3:.2f} GB)", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(part, *args) for args in jobs]
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            future.result()
            print(f"{target.name} {done}/{len(jobs)}", flush=True)
    digest = hashlib.sha256()
    temp = target.with_suffix(".incomplete")
    with temp.open("wb") as out:
        for _, path, _, _ in jobs:
            with path.open("rb") as inp:
                while chunk := inp.read(8 * 1024 * 1024):
                    digest.update(chunk)
                    out.write(chunk)
    actual = digest.hexdigest()
    if sha and actual != sha:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"SHA256 mismatch for {target.name}")
    temp.replace(target)
    marker.write_text((sha or actual) + "\n", encoding="utf-8")
    for _, path, _, _ in jobs:
        path.unlink(missing_ok=True)
    print(f"verified {target.name}", flush=True)


def main():
    free = shutil.disk_usage(MODELS if MODELS.exists() else ROOT).free
    if free < 20 * 1024**3:
        raise SystemExit(f"Need 20 GB free, found {free / 1024**3:.1f} GB")
    files = listing()
    for remote, target in WANTED.items():
        size, sha = files[remote]
        fetch(remote, target, size, sha)
    print("Wan 2.1 1.3B ready", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr, flush=True)
        raise
