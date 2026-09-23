"""Offline checks for tracked publication files and local documentation links.

No network, platform login, generation, package installation or file mutation.
This is a repository guardrail, not a comprehensive secret/content scanner.
"""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote, urlsplit


def check(root: Path) -> int:
    root = root.resolve()
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        print("ERROR: Git must be available and --root must be a Git working tree.")
        return 1
    tracked = set(result.stdout.decode("utf-8").strip("\0").split("\0")) - {""}
    errors: list[str] = []
    docs = 0
    links = 0
    forbidden_dirs = {".local", ".tools", "media-tasks", ".venv", "venv", "node_modules", "__pycache__"}
    forbidden_suffixes = {".safetensors", ".ckpt", ".gguf", ".onnx", ".pyc", ".log", ".mp4", ".webm", ".wav", ".mp3"}
    private_prefixes = ("source/private/", "output/private/")
    doc_prefixes = ("docs/", "scripts/")

    for name in sorted(tracked):
        path = root / name
        rel = PurePosixPath(name)
        if (forbidden_dirs.intersection(rel.parts)
                or name.startswith(private_prefixes)
                or rel.name == ".env" or rel.name.startswith(".env.")
                or rel.suffix.lower() in forbidden_suffixes):
            errors.append(f"Local/private artifact is tracked: {name}")
        if not path.is_file():
            errors.append(f"Tracked file is missing: {name}")
            continue
        if path.stat().st_size > 10 * 1024 * 1024:
            errors.append(f"Tracked file exceeds 10 MiB; review publication scope: {name}")
        if rel.suffix.lower() != ".md" or not (
            len(rel.parts) == 1 or name.startswith(doc_prefixes)
            or name in {"source/README.md", "output/README.md"}
        ):
            continue
        docs += 1
        content = path.read_text(encoding="utf-8-sig")
        # Ignore commands/examples inside fenced blocks, not actual document links.
        content = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", content)
        targets = re.findall(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", content)
        targets += re.findall(r"(?:src|href)=[\"']([^\"']+)[\"']", content)
        for target in targets:
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            links += 1
            linked = (path.parent / unquote(parsed.path)).resolve()
            try:
                linked_name = linked.relative_to(root).as_posix()
            except ValueError:
                errors.append(f"Link escapes repository: {name} -> {target}")
                continue
            if not linked.exists():
                errors.append(f"Broken local link: {name} -> {target}")
            elif linked.is_dir():
                prefix = "" if linked_name == "." else linked_name.rstrip("/") + "/"
                if not any(item.startswith(prefix) for item in tracked):
                    errors.append(f"Linked directory has no tracked files: {name} -> {target}")
            elif linked_name not in tracked:
                errors.append(f"Link target is not staged/tracked: {name} -> {target}")

    if errors:
        for error in errors:
            print("ERROR: " + error)
        print(f"FAIL: {len(errors)} repository issue(s).")
        return 1
    print(f"PASS: {len(tracked)} tracked files; {docs} documents; {links} local links/images.")
    print("No network or generation calls. Manually review secrets, rights and screenshot contents.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    raise SystemExit(check(args.root))
