"""Write ArmorCatalog.Icons from studio-asset-ids.json (run after uploading new icons)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ids = json.load(open(ROOT / "studio-asset-ids.json"))["icons"]
cat = ROOT.parent / "studio-prototype" / "combat" / "ArmorCatalog.luau"
s = open(cat, encoding="utf-8", newline="").read()
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
body = "\n".join(f'\t["{k}"] = "{ids[k]}",' for k in sorted(ids))
s, n = re.subn(r"A\.Icons = \{[^}]*\}", "A.Icons = {\n" + body + "\n}", s)
assert n == 1
if crlf:
    s = s.replace("\n", "\r\n")
open(cat, "w", encoding="utf-8", newline="").write(s)
print("icons", len(ids))
