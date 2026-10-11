"""Run the pure hit-number and combat-wire tests without Studio (2026-10-10, hit colours).

Usage (from the repo root):
  python roguelite-planning/studio-prototype/combat/run_hit_feedback_tests.py build/luau-validation/luau.exe

Inlines the real HitFeedbackVisuals, ShotBatch and WeaponCatalog, then runs HitFeedbackTests (pool,
merge and crit/element colour rules, flash colours, weapon themes, plus ShotBatch.style's round trip) and CombatWireTests (Shot rows, hit
batches with their crit/element bits, packed attacks). Only engine types are stubbed: Color3,
Enum, a small Vector3 / yaw-only CFrame, Random, typeof, game and workspace. HitFeedbackVisuals'
V.mount, which builds Instances, is never called.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent

STUBS = r"""
local nativeTypeof=typeof
local Vec={}
Vec.__index=function(v,k)
 if k=='Magnitude' then return math.sqrt(v.X*v.X+v.Y*v.Y+v.Z*v.Z)
 elseif k=='Unit' then local m=math.sqrt(v.X*v.X+v.Y*v.Y+v.Z*v.Z);return Vector3.new(v.X/m,v.Y/m,v.Z/m)
 elseif k=='Dot' then return function(a,b) return a.X*b.X+a.Y*b.Y+a.Z*b.Z end end
end
Vec.__add=function(a,b) return Vector3.new(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
Vec.__sub=function(a,b) return Vector3.new(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
Vec.__mul=function(a,b) if type(a)=='number' then a,b=b,a end;if type(b)=='number' then return Vector3.new(a.X*b,a.Y*b,a.Z*b) end;return Vector3.new(a.X*b.X,a.Y*b.Y,a.Z*b.Z) end
Vec.__div=function(a,b) return Vector3.new(a.X/b,a.Y/b,a.Z/b) end
Vec.__unm=function(a) return Vector3.new(-a.X,-a.Y,-a.Z) end
Vector3={new=function(x,y,z) return setmetatable({X=x or 0,Y=y or 0,Z=z or 0},Vec) end}
Vector3.zero=Vector3.new(0,0,0);Vector3.one=Vector3.new(1,1,1);Vector3.xAxis=Vector3.new(1,0,0);Vector3.yAxis=Vector3.new(0,1,0);Vector3.zAxis=Vector3.new(0,0,1)
-- Yaw-only CFrame: enough for the packed attack (flat looks, upright).
local CF={}
local function rotY(yaw,v) local c,s=math.cos(yaw),math.sin(yaw);return Vector3.new(v.X*c+v.Z*s,v.Y,-v.X*s+v.Z*c) end
CF.__index=function(f,k)
 if k=='LookVector' then return Vector3.new(-math.sin(f.yaw),0,-math.cos(f.yaw))
 elseif k=='UpVector' then return Vector3.yAxis
 elseif k=='X' or k=='Y' or k=='Z' then return f.Position[k] end
end
CF.__mul=function(a,b) return setmetatable({Position=a.Position+rotY(a.yaw,b.Position),yaw=a.yaw+b.yaw},CF) end
CFrame={new=function(x,y,z) return setmetatable({Position=Vector3.new(x,y,z),yaw=0},CF) end,
 Angles=function(_,yaw,_) return setmetatable({Position=Vector3.zero,yaw=yaw},CF) end,
 lookAt=function(p,t) local d=t-p;return setmetatable({Position=p,yaw=math.atan2(-d.X,-d.Z)},CF) end}
CFrame.identity=CFrame.new(0,0,0)
Random={new=function(seed) math.randomseed(seed);return {NextNumber=function(_,a,b) return a+(b-a)*math.random() end} end}
Color3={fromRGB=function(r,g,b) return {R=r/255,G=g/255,B=b/255} end,new=function(r,g,b) return {R=r,G=g,B=b} end}
Enum={EasingStyle={Quad=1,Back=2},EasingDirection={Out=1}}
local function instance(name) return {__instance=true,Name=name} end
workspace=instance('Workspace')
local services={Players={GetPlayers=function() return {} end},Lighting=instance('Lighting')}
game={GetService=function(_,name) return services[name] or {} end}
typeof=function(v)
 if type(v)=='table' then
  if v.__instance then return 'Instance' end
  if getmetatable(v)==Vec then return 'Vector3' end
  if getmetatable(v)==CF then return 'CFrame' end
 end
 return nativeTypeof(v)
end
"""


def module(name, filename):
    source = (root / filename).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return f"MODULES.{name}=(function()\n{source}\nend)()\n"


source = STUBS + "local MODULES={}\n"
for name, filename in [
    ("HitFeedbackVisuals", "HitFeedbackVisuals.luau"),
    ("ShotBatch", "ShotBatch.luau"),
    ("WeaponCatalog", "WeaponCatalog.luau"),
    ("HitFeedbackTests", "HitFeedbackTests.luau"),
    ("CombatWireTests", "CombatWireTests.luau"),
]:
    source += module(name, filename)
source += """local M=MODULES
print('HitFeedbackTests: '..M.HitFeedbackTests(M.HitFeedbackVisuals,M.ShotBatch,M.WeaponCatalog).checks..' checks passed')
local wire=M.CombatWireTests(M.ShotBatch)
print('CombatWireTests: '..wire.checks..' checks passed ('..wire.notes.hitMessages..' hit messages, worst budget '..wire.notes.worstHitBudget..' bytes)')
"""
with tempfile.TemporaryDirectory(prefix="roguelite-hitfx-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
