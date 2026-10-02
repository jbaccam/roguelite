"""Local server for the Studio tools (plan K). Binds 127.0.0.1 only.
    python roguelite-planning/studio-prototype/tools/dev_server.py [port]      (default 8934)
GET  /<path>                  files under roguelite-planning/ (e.g. /studio-prototype/combat/QuestConfig.luau)
GET  /git/<rev>/<path>        a roguelite-planning/ file as committed at <rev> (SyncPlan's guard)
GET  /assetmap.json           rbxassetid number -> local PNG path, for gui_view.html
POST /dump/<name>             save a GuiDump.luau JSON; GET /dump/<name>.json reads it back
"""
import json
import re
import subprocess
import sys
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROTO = TOOLS.parent
PLANNING = PROTO.parent
DUMPS = Path(tempfile.gettempdir()) / "roguelite-gui-dumps"

# UITheme / StoreFX / ChestConfig / EggConfig art without an asset-ids.json entry.
THEME = {
    "116439058081230": "studio-prototype/ui/assets/panel.png",
    "82653359149627": "studio-prototype/ui/assets/inset.png",
    "72732018694626": "studio-prototype/ui/assets/button.png",
    "107387940957948": "studio-prototype/ui/assets/stone.png",
    "122511819290059": "studio-prototype/ui/assets/corners.png",
    "105310886449973": "studio-prototype/ui/assets/panelplain.png",
    "101432943753406": "studio-prototype/ui/assets/heart.png",
    "113971691535704": "studio-prototype/ui/assets/teeth.png",
    "102213113777434": "studio-prototype/ui/assets/gem.png",
    "89513131203273": "studio-prototype/ui/assets/lock.png",
    "101092695897243": "studio-prototype/ui/assets/glow.png",
    "75268019571051": "studio-prototype/ui/assets/sunburst.png",
    "107205947937384": "studio-prototype/ui/assets/hud/emerald.png",
    "129322350142524": "studio-prototype/ui/assets/hud/shard-bag.png",
    "107136053285951": "blender-chest-kit/previews/icon-wooden.png",
    "103320236733137": "blender-chest-kit/previews/icon-silver.png",
    "88627612681717": "blender-chest-kit/previews/icon-gold.png",
    "92681366357642": "blender-chest-kit/previews/icon-magical.png",
    "81753880209961": "blender-chest-kit/previews/icon-legendary.png",
    "117887028525234": "blender-egg-merchant-kit/previews/icon-egg.png",
}


def asset_map():
    m = dict(THEME)
    for f in (PROTO / "ui" / "assets").rglob("*asset-ids.json"):
        def add(value, key, folder=f.parent):
            hit = re.search(r"rbxassetid://(\d+)", value)
            png = folder / f"{key}.png"
            if hit and png.exists():
                m.setdefault(hit.group(1), png.relative_to(PLANNING).as_posix())

        def walk(node, key=None):
            if isinstance(node, dict):
                if key and isinstance(node.get("asset"), str):
                    add(node["asset"], key)
                for k, v in node.items():
                    walk(v, k)
            elif isinstance(node, str) and key:
                add(node, key)

        walk(json.loads(f.read_text(encoding="utf-8")))
    return m


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/assetmap.json":
            return self.send_bytes(json.dumps(asset_map()).encode(), "application/json")
        if path.startswith("/git/"):
            _, _, rev, rest = path.split("/", 3)
            r = subprocess.run(["git", "show", f"{rev}:roguelite-planning/{rest}"], cwd=PLANNING, capture_output=True)
            if r.returncode:
                return self.send_error(404, r.stderr.decode(errors="replace")[:200])
            return self.send_bytes(r.stdout.replace(b"\r\n", b"\n"), "text/plain; charset=utf-8")
        if path.startswith("/dump/"):
            f = DUMPS / Path(path).name
            if not f.exists():
                return self.send_error(404)
            return self.send_bytes(f.read_bytes(), "application/json")
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        if not path.startswith("/dump/"):
            return self.send_error(404)
        name = re.sub(r"[^\w-]", "", Path(path).name) or "preview"
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        DUMPS.mkdir(exist_ok=True)
        (DUMPS / f"{name}.json").write_bytes(body)
        self.send_bytes(b"ok", "text/plain")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8934
    print(f"serving {PLANNING} on http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(PLANNING))).serve_forever()
