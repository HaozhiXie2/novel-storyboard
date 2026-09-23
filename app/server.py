"""Local-only novel video workstation. Start with the project Python environment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "media-tasks" / "studio"
COMFY = "http://127.0.0.1:8188"
LOCK = threading.Lock()
TOKEN = secrets.token_urlsafe(32)
SD15 = "v1-5-pruned-emaonly.safetensors"
DREAMSHAPER = "DreamShaper_8_pruned.safetensors"
MOTION = "mm_sd_v15_v2.ckpt"
STYLE = "medium shot, subject large in the foreground, Chinese illustration, detailed face and clothing"
MOTION_FPS = 8
MAX_FRAMES = 48
WAN_UNET = "wan2.1_t2v_1.3B_fp16.safetensors"
WAN_CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
WAN_VAE = "wan_2.1_vae.safetensors"
WAN_FPS = 16
WAN_PREFIX = "电影级写实摄影，竖屏，连贯自然的动作，人物在画面中清楚可见，衣物、雨水和地面有真实质感。"
WAN_NEGATIVE = "text, subtitles, watermark, logo, blurry, deformed, extra limbs, bad anatomy, cartoon, illustration, anime, static slideshow"


def api(path, data=None, timeout=20):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(COMFY + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read()
            return json.loads(payload) if payload.strip() else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ComfyUI {e.code}: {e.read().decode('utf-8', 'replace')[:2000]}") from e


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def job_dir(job_id):
    if not re.fullmatch(r"[a-f0-9]{16}", job_id):
        raise ValueError("无效任务编号")
    return JOBS / job_id


def read_job(job_id):
    return json.loads((job_dir(job_id) / "job.json").read_text(encoding="utf-8"))


def update(job, **fields):
    job.update(fields)
    job["updated"] = time.time()
    write_json(job_dir(job["id"]) / "job.json", job)


def active_checkpoint():
    folder = ROOT / ".local/ComfyUI/models/checkpoints"
    for name in (DREAMSHAPER, SD15):
        if (folder / name).exists() and (folder / (name + ".verified")).exists():
            return name
    return SD15


def wan_installed():
    root = ROOT / ".local/ComfyUI/models"
    files = (
        root / "diffusion_models" / WAN_UNET,
        root / "text_encoders" / WAN_CLIP,
        root / "vae" / WAN_VAE,
    )
    return all(path.exists() and path.with_name(path.name + ".verified").exists() for path in files)


def names_of(info, node, field):
    spec = info[node]["input"]["required"][field]
    return spec[0] if isinstance(spec[0], list) else spec[1].get("options", [])


def health():
    result = {"comfy": False, "checkpoint": False, "motion": False, "planner": False, "engine": "animatediff", "ready": False}
    result["planner"] = (ROOT / ".local/models/planner/READY").exists() or (ROOT / ".local/models/planner-4b/READY").exists()
    try:
        info = api("/object_info", timeout=8)
        result["comfy"] = True
        model_root = ROOT / ".local/ComfyUI/models"
        if wan_installed() and WAN_UNET in names_of(info, "UNETLoader", "unet_name") and WAN_CLIP in names_of(info, "CLIPLoader", "clip_name") and WAN_VAE in names_of(info, "VAELoader", "vae_name"):
            result["engine"] = "wan"
            result["checkpoint"] = True
            result["motion"] = True
        else:
            ckpts = names_of(info, "CheckpointLoaderSimple", "ckpt_name")
            checkpoint = active_checkpoint()
            result["checkpoint"] = checkpoint in ckpts and (model_root / "checkpoints" / (checkpoint + ".verified")).exists()
            if "ADE_AnimateDiffLoaderGen1" in info:
                result["motion"] = MOTION in names_of(info, "ADE_AnimateDiffLoaderGen1", "model_name") and (model_root / "animatediff_models" / (MOTION + ".verified")).exists()
        result["ready"] = all(result[x] for x in ("comfy", "checkpoint", "motion", "planner"))
    except Exception as e:
        result["detail"] = str(e)[:300]
    return result


def clip_text(prompt, anchor):
    # SD 1.5 only reads about 77 tokens and drops the end, so framing stays at the front.
    scene = prompt.strip().rstrip(".")
    extra = anchor.strip()
    for noise in ("unspecified setting", "unspecified", "historical period:", "region:"):
        extra = extra.replace(noise, " ")
    body = " ".join(f"{scene}, {extra}".split())
    return f"{STYLE}, {' '.join(body.split()[:32])}"


def shot_frames(slot_seconds):
    frames = int(round(slot_seconds * MOTION_FPS))
    frames = max(16, min(MAX_FRAMES, frames))
    if frames > 16:
        frames = min(MAX_FRAMES, 16 + ((frames - 16 + 7) // 8) * 8)
    return frames


def wan_length(slot_seconds):
    # Wan needs 4n+1 frames. 16 fps, capped at about five seconds so 12 GB can finish a shot.
    target = int(round(slot_seconds * WAN_FPS))
    target = max(33, min(81, target))
    return 1 + 4 * ((target - 1) // 4)


def wan_prompt(prompt):
    text = " ".join((WAN_PREFIX + prompt.strip()).split())
    return text[:480]


def workflow(prompt, anchor, seed, frames=16, steps=20):
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": active_checkpoint()}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": clip_text(prompt, anchor)}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "text, watermark, blurry, deformed, extra limbs, bad anatomy, door filling the frame, empty street, tiny distant people, monochrome sketch"}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 432, "height": 768, "batch_size": frames}},
        "5": {"class_type": "ADE_AnimateDiffLoaderGen1", "inputs": {"model": ["1", 0], "model_name": MOTION, "beta_schedule": "autoselect"}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": seed, "steps": steps, "cfg": 7.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "novel-studio/frames"}},
    }
    # A closed loop makes the last frame jump back to the first. Longer clips use a forward window instead.
    if frames > 16:
        graph["9"] = {"class_type": "ADE_StandardUniformContextOptions", "inputs": {"context_length": 16, "context_stride": 1, "context_overlap": 4, "fuse_method": "pyramid"}}
        graph["5"]["inputs"]["context_options"] = ["9", 0]
    return graph, "8", MOTION_FPS


def workflow_wan(prompt, seed, length, steps=20):
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": WAN_UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": WAN_CLIP, "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": WAN_VAE}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": wan_prompt(prompt)}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": WAN_NEGATIVE}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "7": {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": 480, "height": 832, "length": length, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["6", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["7", 0], "seed": seed, "steps": steps, "cfg": 6.0, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "novel-studio/frames"}},
    }
    return graph, "10", WAN_FPS


def check_cancel(folder):
    if (folder / "cancel").exists():
        raise InterruptedError("任务已暂停，可继续生成")


def run_process(args, folder, logname, timeout=1800):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with (folder / logname).open("w", encoding="utf-8") as log:
        p = subprocess.Popen(args, cwd=folder, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        started = time.monotonic()
        try:
            while p.poll() is None:
                check_cancel(folder)
                if time.monotonic() - started > timeout:
                    raise TimeoutError(f"步骤超时，详见 {logname}")
                time.sleep(.5)
        except BaseException:
            p.terminate()
            p.wait(timeout=10)
            raise
    if p.returncode:
        detail = (folder / logname).read_text(encoding="utf-8", errors="replace")[-1600:]
        raise RuntimeError(f"步骤失败：{detail}")


def save_documents(folder, plan):
    (folder / "01-summary.md").write_text("# 剧情摘要\n\n" + plan.get("summary", ""), encoding="utf-8")
    (folder / "02-bible.md").write_text("# 人物与画面设定\n\n" + plan.get("anchor", ""), encoding="utf-8")
    storyboard, prompts = ["# 分镜"], ["# 提示词"]
    for i, s in enumerate(plan["shots"], 1):
        storyboard.append(f"## 镜 {i}\n\n{s['prompt']}\n\n原文：{s['narration']}")
        prompts.append(f"## 镜 {i}\n\n{s['prompt']}")
    (folder / "03-storyboard.md").write_text("\n\n".join(storyboard), encoding="utf-8")
    (folder / "04-prompts.md").write_text("\n\n".join(prompts), encoding="utf-8")


def prepare_plan(job, folder):
    update(job, status="planning", message="本地模型正在阅读正文并编写分镜")
    # The planner exits before ComfyUI generation, releasing its GPU memory.
    api("/free", {"unload_models": True, "free_memory": True})
    run_process([sys.executable, str(ROOT / "app/planner.py"), str(folder)], folder, "planner.log")
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    save_documents(folder, plan)
    update(job, status="review", message="分镜已准备好，可修改后生成视频", plan=plan)


def render(job, folder):
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    plan = job["plan"]
    update(job, video=None)
    save_documents(folder, plan)
    clips = []
    for index, shot in enumerate(plan["shots"]):
        check_cancel(folder)
        shot_dir = folder / f"shot-{index+1:03}"
        shot_dir.mkdir(exist_ok=True)
        slot = float(job["duration"]) / len(plan["shots"])
        use_wan = wan_installed()
        frames = wan_length(slot) if use_wan else shot_frames(slot)
        engine = "wan" if use_wan else active_checkpoint()
        signature = hashlib.sha256(json.dumps(["render-v5", shot, job["seed"], engine, frames], ensure_ascii=False).encode()).hexdigest()
        clip = shot_dir / "clip.mp4"
        stamp = shot_dir / "signature.txt"
        meta = {}
        if stamp.exists():
            try:
                meta = json.loads(stamp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        if clip.exists() and meta.get("signature") == signature:
            clips.append(clip)
            continue
        update(job, status="generating", message=f"正在生成镜头 {index+1}/{len(plan['shots'])}", completed=index)
        # Persist the prompt id BEFORE polling so a restarted app resumes the same task.
        taskfile = shot_dir / "task.json"
        task = json.loads(taskfile.read_text()) if taskfile.exists() else {}
        if task.get("signature") != signature:
            task = {}
        if not task.get("prompt_id"):
            if use_wan:
                graph, save_node, fps = workflow_wan(shot.get("prompt") or shot.get("image_prompt") or "", job["seed"] + index, frames)
            else:
                graph, save_node, fps = workflow(shot.get("image_prompt") or shot["prompt"], "", job["seed"] + index, frames)
            graph[save_node]["inputs"]["filename_prefix"] = f"novel-studio/{job['id']}/shot-{index+1:03}"
            task_meta = {"save_node": save_node, "fps": fps}
            submitted = api("/prompt", {"prompt": graph, "client_id": job["id"]})
            if submitted.get("node_errors") or not submitted.get("prompt_id"):
                raise RuntimeError(str(submitted))
            task = {"signature": signature, "prompt_id": submitted["prompt_id"], **task_meta}
            write_json(taskfile, task)
        deadline = time.monotonic() + 3600
        while True:
            check_cancel(folder)
            history = api("/history/" + task["prompt_id"])
            result = history.get(task["prompt_id"])
            if result:
                if result.get("status", {}).get("status_str") == "error":
                    task["prompt_id"] = None
                    write_json(taskfile, task)
                    raise RuntimeError(json.dumps(result.get("status"), ensure_ascii=False)[-2000:])
                images = result.get("outputs", {}).get(task.get("save_node", "8"), {}).get("images", [])
                if images:
                    break
            if time.monotonic() > deadline:
                raise TimeoutError("该镜头等待超过一小时；再次继续会查询原任务，不重复提交")
            time.sleep(2)
        for j, item in enumerate(images):
            url = COMFY + "/view?" + urllib.parse.urlencode(item)
            with urllib.request.urlopen(url, timeout=60) as response:
                (shot_dir / f"frame-{j:04}.png").write_bytes(response.read())
        # Play the generated frames once. Looping the same short clip is what made the picture twitch.
        width, height = ("720", "1280") if task.get("fps") == WAN_FPS else ("576", "1024")
        args = [ffmpeg, "-y", "-framerate", str(task.get("fps", MOTION_FPS)), "-i", "frame-%04d.png", "-vf", f"scale={width}:{height}:flags=lanczos,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart", "clip.mp4"]
        run_process(args, shot_dir, "encode.log")
        stamp.write_text(json.dumps({"signature": signature, "frames": len(images)}), encoding="utf-8")
        clips.append(clip)
    update(job, status="assembling", message="正在拼接镜头")
    (folder / "concat.txt").write_text("\n".join(f"file 'shot-{i+1:03}/clip.mp4'" for i in range(len(clips))), encoding="utf-8")
    run_process([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy", "-movflags", "+faststart", "final.mp4"], folder, "merge.log")
    note = "视频已生成，无配音。每镜是视频模型直接生成的连续画面。" if wan_installed() else "视频已生成，无配音"
    update(job, status="done", message=note, completed=len(clips), video=f"/media/{job['id']}/final.mp4")


def worker(job_id, mode):
    folder = job_dir(job_id)
    job = read_job(job_id)
    try:
        if mode == "plan":
            prepare_plan(job, folder)
            if job.get("automatic"):
                render(job, folder)
        else:
            render(job, folder)
    except InterruptedError as e:
        update(job, status="paused", message=str(e))
    except Exception as e:
        (folder / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        update(job, status="error", message=str(e)[:2400])
    finally:
        LOCK.release()


def start_job(job_id, mode):
    if not LOCK.acquire(blocking=False):
        raise ValueError("已有任务运行，请等待完成或暂停后再启动")
    try:
        folder = job_dir(job_id)
        (folder / "cancel").unlink(missing_ok=True)
        threading.Thread(target=worker, args=(job_id, mode), daemon=True).start()
    except Exception:
        LOCK.release()
        raise


class Handler(BaseHTTPRequestHandler):
    def json_response(self, data, code=200):
        self.send_data(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def send_data(self, data, mime, code=200):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/":
                html = (ROOT / "app/index.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
                return self.send_data(html.encode(), "text/html; charset=utf-8")
            if path == "/api/health":
                return self.json_response(health())
            if path == "/api/jobs":
                jobs = [json.loads(p.read_text(encoding="utf-8")) for p in JOBS.glob("*/job.json")]
                return self.json_response(sorted(jobs, key=lambda x:x["created"], reverse=True))
            if path.startswith("/media/"):
                parts = path.split("/")
                allowed = {"final.mp4", "subtitles.srt", "01-summary.md", "02-bible.md", "03-storyboard.md", "04-prompts.md", "plan.json"}
                if len(parts) != 4 or parts[3] not in allowed:
                    raise ValueError("文件不可访问")
                file = job_dir(parts[2]) / parts[3]
                mime = "video/mp4" if file.suffix == ".mp4" else "text/plain; charset=utf-8"
                return self.send_data(file.read_bytes(), mime)
            return self.json_response({"error": "未找到页面"}, 404)
        except Exception as e:
            return self.json_response({"error": str(e)}, 400)

    def do_POST(self):
        try:
            if self.headers.get("X-Studio-Token") != TOKEN:
                return self.json_response({"error": "请刷新本地页面后重试"}, 403)
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1000000:
                raise ValueError("输入过大")
            data = json.loads(self.rfile.read(size))
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/jobs":
                text = str(data.get("text", "")).strip()
                if not 10 <= len(text) <= 60000:
                    raise ValueError("正文需要 10 到 60000 字")
                if not health()["ready"]:
                    raise ValueError("环境或模型尚未就绪，请查看页面上方环境状态")
                duration = int(data.get("duration", 30))
                if duration not in (10, 30, 60, 90):
                    raise ValueError("不支持的时长")
                job_id = secrets.token_hex(8)
                folder = job_dir(job_id)
                folder.mkdir(parents=True)
                job = {"id": job_id, "title": str(data.get("title", "未命名章节"))[:80], "created": time.time(), "duration": duration, "automatic": bool(data.get("automatic", False)), "seed": 20260922, "status": "new", "message": "准备中"}
                (folder / "source.txt").write_text(text, encoding="utf-8")
                write_json(folder / "job.json", job)
                start_job(job_id, "plan")
                return self.json_response(job, 201)
            job_id = data["id"]
            job = read_job(job_id)
            if path == "/api/replan":
                start_job(job_id, "plan")
                return self.json_response({"ok": True})
            if path == "/api/pause":
                (job_dir(job_id) / "cancel").touch()
                return self.json_response({"ok": True})
            if path == "/api/render":
                if LOCK.locked():
                    raise ValueError("已有任务运行，请稍后再试")
                plan = data.get("plan", job.get("plan"))
                if not isinstance(plan, dict) or not isinstance(plan.get("shots"), list) or not 1 <= len(plan["shots"]) <= 30:
                    raise ValueError("分镜格式不正确")
                for shot in plan["shots"]:
                    if not isinstance(shot, dict) or any(not isinstance(shot.get(k), str) or not shot[k].strip() for k in ("prompt", "narration")):
                        raise ValueError("每个镜头需要画面提示词与旁白")
                    if len(shot["narration"]) > 180 or len(shot["prompt"]) > 2000:
                        raise ValueError("镜头文字过长，请精简")
                job["plan"] = plan
                write_json(job_dir(job_id) / "job.json", job)
                write_json(job_dir(job_id) / "plan.json", plan)
                start_job(job_id, "render")
                return self.json_response({"ok": True})
            raise ValueError("未知操作")
        except Exception as e:
            return self.json_response({"error": str(e)}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    JOBS.mkdir(parents=True, exist_ok=True)
    for file in JOBS.glob("*/job.json"):
        job = json.loads(file.read_text(encoding="utf-8"))
        if job["status"] in ("planning", "generating", "assembling"):
            update(job, status="paused", message="上次运行中断，已保留分镜与已完成镜头")
    print(f"Novel Studio: http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
