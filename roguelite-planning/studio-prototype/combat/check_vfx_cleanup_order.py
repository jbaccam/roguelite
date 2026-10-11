"""Static check: effect cleanups destroy their own parts before starting follow-up effects.

Usage: python check_vfx_cleanup_order.py [files...]   (default: every client VFX module here)

VfxKit runs each cleanup in a pcall (2026-10-10). If a cleanup starts a follow-up effect (a burst,
shards, a landing blast) and THEN destroys its own parts, a follow-up that throws skips the
destroys and those parts stay on screen for the rest of the run. This finds the cleanup argument
of every K.animate / kit.animate / C.follow call and fails when a call that is not a destroy or a
harmless read comes before the last destroy in that cleanup. Exit code 1 lists the offenders.
"""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent
DEFAULT = [
    "LegendaryVisuals.luau", "GodlyVisuals.luau", "PandoraVisuals.luau", "ProjectileStyleVisuals.luau",
    "SwingVisuals.luau", "ThrownVisuals.luau", "ArcVisuals.luau", "VfxKit.luau", "HitFeedbackVisuals.luau",
    "RogueliteCombat.client.luau", "RogueliteChickens.client.luau", "HandymanTurret.client.luau",
    "events/Round10World.luau", "bosses/BossVfx/*.luau",
]
DESTROY = re.compile(r":[Dd]estroy\(|\bdropRocket\(|\bC\.retire\(|\brelease\(|\bgive\(|:done\(")
# Calls that only read, test or tidy: allowed before a destroy.
HARMLESS = re.compile(
    r"^(math\.\w+|table\.clear|table\.insert|pairs|ipairs|next|tostring|type|typeof|Vector3\.new|CFrame\.new|CFrame\.lookAt|"
    r"K\.near|C\.near|C\.ground|npcRoot|\w+:GetPivot|\w+:FindFirstChild\w*|\w+:IsA|\w+:GetDescendants|C\.stopSound)$"
)


def strip(src):
    """Blank out comments and string contents, keeping offsets."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        if src.startswith("--[[", i) or src.startswith("--[=[", i):
            close = "]]" if src.startswith("--[[", i) else "]=]"
            j = src.find(close, i)
            j = n if j < 0 else j + len(close)
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif src.startswith("--", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif src[i] in "\"'":
            q = src[i]
            j = i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


WORD = re.compile(r"[A-Za-z_]\w*")


def call_args(code, open_paren):
    """Argument spans of the call whose '(' is at open_paren, honouring function/do/if ... end blocks."""
    spans, start, depth, blocks = [], open_paren + 1, 0, 0
    i = open_paren
    while i < len(code):
        c = code[i]
        if c.isalpha() or c == "_":
            m = WORD.match(code, i)
            w = m.group(0)
            if w in ("function", "do", "if"):
                blocks += 1
            elif w == "end":
                blocks -= 1
            i = m.end()
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                spans.append((start, i))
                return spans
        elif c == "," and depth == 1 and blocks == 0:
            spans.append((start, i))
            start = i + 1
        i += 1
    return spans


def own_level(body):
    """Per character: True where it belongs to the cleanup function itself, not a nested function
    (a nested K.animate's cleanup has its own order and is checked on its own)."""
    flags, stack, i = [False] * len(body), [], 0
    while i < len(body):
        c = body[i]
        if c.isalpha() or c == "_":
            m = WORD.match(body, i)
            w = m.group(0)
            if w == "function":
                stack.append("f")
            elif w in ("do", "if"):
                stack.append("b")
            elif w == "end" and stack:
                stack.pop()
            own = stack.count("f") == 1
            for k in range(i, m.end()):
                flags[k] = own
            i = m.end()
            continue
        flags[i] = stack.count("f") == 1
        i += 1
    return flags


def check(path):
    src = path.read_text(encoding="utf-8-sig")
    code = strip(src)
    problems = []
    for m in re.finditer(r"\b(K\.animate|kit\.animate|C\.follow)\(", code):
        args = call_args(code, m.end() - 1)
        index = 3 if m.group(1) == "C.follow" else 2
        if len(args) <= index:
            continue
        a, b = args[index]
        body = code[a:b]
        if not body.strip().startswith("function"):
            continue
        own = own_level(body)
        destroys = [d.start() for d in DESTROY.finditer(body) if own[d.start()]]
        if not destroys:
            continue
        last = destroys[-1]
        for call in re.finditer(r"([A-Za-z_][\w\.:]*)\s*\(", body[:last]):
            name = call.group(1)
            if name == "function" or not own[call.start()]:
                continue
            if name.endswith((":Destroy", ":destroy", ":done")) or name in ("dropRocket", "C.retire", "release", "give"):
                continue
            if HARMLESS.match(name):
                continue
            line = src.count("\n", 0, a + call.start()) + 1
            problems.append(f"{path.relative_to(root)}:{line}: cleanup calls {name}() before its own destroys")
            break
    return problems


def main():
    names = sys.argv[1:] or DEFAULT
    files = []
    for name in names:
        files += sorted(root.glob(name)) if "*" in name else [root / name]
    problems, cleanups = [], 0
    for f in files:
        problems += check(f)
        cleanups += len(re.findall(r"\b(?:K\.animate|kit\.animate|C\.follow)\(", strip(f.read_text(encoding="utf-8-sig"))))
    for p in problems:
        print(p)
    print(f"check_vfx_cleanup_order: {len(files)} files, {cleanups} effect calls, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
