"""Anchored hunks for scripts several sessions edit at once (memory: shared-script edits as hunks).

A plan's hunk file defines HUNKS (and optionally MODULES) and calls run():
    python <plan>_hunks.py            apply to the repo files (hunks already there are skipped)
    python <plan>_hunks.py --check    report only, change nothing
    python <plan>_hunks.py --stage    also stage HEAD + these hunks (git index) for each shared file,
                                      so a commit never takes other sessions' uncommitted edits
    python <plan>_hunks.py --json     also write the Studio sync manifest for tools/SyncPlan.luau

Hunk: (repo file, Studio dot path or None, anchor, where, text). where is 'after' / 'before' the
anchor line, 'replace' the anchor line, or 'block': anchor is (first line, last line) and the whole
block is replaced. Lines match with a trailing \\r ignored. A hunk is "present" when its text
already appears in the file.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # studio-prototype


def apply(text, anchor, where, ins):
    if ins in text.replace("\r\n", "\n"):
        return text, "present"
    lines = text.split("\n")

    def find(a):
        return [i for i, l in enumerate(lines) if l.rstrip("\r") == a]

    def fresh(i):
        crlf = lines[i].endswith("\r")
        return [l + ("\r" if crlf else "") for l in ins.split("\n")]

    if where == "block":
        a, b = find(anchor[0]), find(anchor[1])
        if len(a) != 1 or len(b) != 1 or b[0] < a[0]:
            return text, f"block anchors found {len(a)}/{len(b)} times"
        lines[a[0]:b[0] + 1] = fresh(a[0])
        return "\n".join(lines), "applied"
    hits = find(anchor)
    if len(hits) != 1:
        return text, f"anchor found {len(hits)} times"
    i = hits[0]
    new = fresh(i)
    if where == "replace":
        lines[i:i + 1] = new
    elif where == "after":
        lines[i + 1:i + 1] = new
    elif where == "before":
        lines[i:i] = new
    else:
        return text, f"unknown where {where}"
    return "\n".join(lines), "applied"


def stage_on_head(hunks):
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    for path in sorted({h[0] for h in hunks}):
        gp = prefix + path
        # The index, not HEAD: a second plan staging the same file then builds on the first one's
        # staged hunks instead of replacing them (2026-10-02: plan K over plan L dropped plan L).
        text = subprocess.run(["git", "show", ":" + gp], cwd=repo, capture_output=True, check=True).stdout.decode("utf-8")
        for p, _, anchor, where, ins in hunks:
            if p == path:
                text, status = apply(text, anchor, where, ins)
                assert status in ("applied", "present"), f"{path}: {status}"
        sha = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo, input=text.encode("utf-8"), capture_output=True, check=True).stdout.decode().strip()
        subprocess.run(["git", "update-index", "--cacheinfo", f"100644,{sha},{gp}"], cwd=repo, check=True)
        print("staged HEAD + hunks:", gp)


def run(hunks, modules=(), manifest=None, base=None):
    check = "--check" in sys.argv
    files, bad = {}, 0
    for path, studio, anchor, where, ins in hunks:
        p = ROOT / path
        text = files.get(path) or p.read_bytes().decode("utf-8")
        new, status = apply(text, anchor, where, ins)
        files[path] = new
        bad += status not in ("applied", "present")
        print(f"{status:30s} {path}: {ins.splitlines()[0][:70]}")
    if bad:
        print(f"{bad} hunk(s) did not apply; nothing written")
        sys.exit(1)
    if not check:
        for path, text in files.items():
            p = ROOT / path
            if text != p.read_bytes().decode("utf-8"):
                p.write_bytes(text.encode("utf-8"))
    if "--stage" in sys.argv:
        stage_on_head(hunks)
    if "--json" in sys.argv and manifest:
        out = {
            "modules": [dict(m, base=base) for m in modules],
            "hunks": [{"repo": p, "studio": s, "anchor": a, "where": w, "text": t} for p, s, a, w, t in hunks if s],
        }
        (ROOT / manifest).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote", manifest)
