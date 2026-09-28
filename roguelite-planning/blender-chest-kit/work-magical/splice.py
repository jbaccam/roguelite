"""Tiny helper: replace the block of tiers/magical.py that starts at a line beginning with START
and ends before a line beginning with END with the contents of a snippet file.
    python splice.py snippet.txt "    # ---- the skull" "    # ---- the chain"
"""
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
snippet, start, end = sys.argv[1:4]
p = KIT / "tiers" / "magical.py"
L = p.read_text().split("\n")
i0 = next(i for i, l in enumerate(L) if l.startswith(start))
i1 = next(i for i, l in enumerate(L) if i > i0 and l.startswith(end))
new = (Path(__file__).resolve().parent / snippet).read_text().rstrip("\n").split("\n") + [""]
p.write_text("\n".join(L[:i0] + new + L[i1:]))
print("spliced", i0, i1, len(new))
