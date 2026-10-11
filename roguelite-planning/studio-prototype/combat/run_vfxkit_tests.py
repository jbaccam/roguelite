"""Run VfxKitLifetimeTests against the real VfxKit source without Studio.

Usage: python run_vfxkit_tests.py path/to/luau.exe [VfxKit.luau]
RunService, ClientQuality, os.clock and warn are replaced by a fake clock and RenderStepped,
so nested/failing effect callbacks can be stepped frame by frame. The optional second
argument runs the tests against another copy (e.g. the pre-2026-10-10 version, which fails).
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent
kit_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / "VfxKit.luau"
kit = kit_path.read_text(encoding="utf-8-sig")
for before, after in [
    ("local RunService=game:GetService('RunService')", "local RunService=Env.RunService"),
    ("local Q=require(script.Parent:WaitForChild('ClientQuality'))", "local Q=Env.Quality"),
]:
    assert before in kit, f"Missing test adapter: {before}"
    kit = kit.replace(before, after)

source = r'''
Color3 = { fromRGB = function(r, g, b) return { R = r / 255, G = g / 255, B = b / 255 } end }
local function newKit()
	local Env = { now = 0, warnings = {} }
	Env.os = { clock = function() return Env.now end }
	Env.warn = function(message) table.insert(Env.warnings, message) end
	Env.Quality = { get = function() return { effects = 1 } end }
	local current
	Env.RunService = { RenderStepped = { Connect = function(_, fn)
		local c = { fn = fn, Connected = true }
		function c:Disconnect() self.Connected = false end
		current = c
		return c
	end } }
	local K = (function(Env)
		local os, warn = Env.os, Env.warn
''' + kit + r'''
	end)(Env)
	function Env.frame(dt)
		Env.now += dt
		if current and current.Connected then current.fn(dt) end
	end
	function Env.connected() return current ~= nil and current.Connected end
	return K, Env
end
'''
tests = (root / "VfxKitLifetimeTests.luau").read_text(encoding="utf-8-sig")
source += f"local Tests=(function()\n{tests}\nend)()\n"
source += "local result=Tests(newKit)\nprint(('VfxKitLifetimeTests: %d checks passed'):format(result.checks))\n"
with tempfile.TemporaryDirectory(prefix="roguelite-vfxkit-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
