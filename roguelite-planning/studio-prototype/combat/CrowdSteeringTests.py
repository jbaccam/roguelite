"""Execute actual crowd steering and legacy grid tests with deterministic vector stubs.
Usage: python CrowdSteeringTests.py /path/to/luau.exe
This kinematic simulation does not replace Studio Humanoid/play testing.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
PRELUDE = r'''

local Vector3={}
local mt={}
function Vector3.new(x,y,z) return setmetatable({X=x or 0,Y=y or 0,Z=z or 0},mt) end
mt.__add=function(a,b) return Vector3.new(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return Vector3.new(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__unm=function(a) return Vector3.new(-a.X,-a.Y,-a.Z) end
mt.__mul=function(a,b) if type(a)=='number' then a,b=b,a end return Vector3.new(a.X*b,a.Y*b,a.Z*b) end
mt.__div=function(a,b) return a*(1/b) end
mt.__index=function(a,k)
 if k=='Magnitude' then return math.sqrt(a.X*a.X+a.Y*a.Y+a.Z*a.Z) end
 if k=='Unit' then return a/a.Magnitude end
 if k=='Dot' then return function(a,b) return a.X*b.X+a.Y*b.Y+a.Z*b.Z end end
end
Vector3.zero=Vector3.new()
local Random={new=function(seed)
 math.randomseed(seed)
 return {NextNumber=function(_,a,b) return a+(b-a)*math.random() end}
end}
'''
CHECKS = r'''

local children={}
local folder={GetChildren=function() return children end}
local function mob(position,boss,size)
 local root={Position=position,Size=size or Vector3.new(3,4,3),IsA=function() return true end}
 local npc={Parent=folder,root=root}
 npc.GetAttribute=function(_,name) if name=='IsBoss' then return boss end;if name=='CrowdRadius' and not boss then return 1.5 end end
 npc.FindFirstChild=function(_,name) if name=='HumanoidRootPart' or name=='Torso' then return root end end
 table.insert(children,npc);return npc
end
local boss=mob(Vector3.zero,true,Vector3.new(8,10,6))
local one=mob(Vector3.new(-12,0,0))
local grid=Grid.new(folder,4.5)
local d=grid:steer(one,one.root.Position,Vector3.new(20,0,0),3)
assert(math.abs(d.Z)>.5,'boss must be sidestepped before body contact')
assert(grid.bosses[1].body>=4,'legacy boss geometry did not establish body clearance')
one.root.Position=Vector3.new(-2,0,0);grid:invalidate()
d=grid:steer(one,one.root.Position,Vector3.new(20,0,0),3)
assert(d.X<-.5,'inside boss must escape outward')
children={}
local a=mob(Vector3.zero);local b=mob(Vector3.zero)
grid=Grid.new(folder,4.5)
local da=grid:steer(a,a.root.Position,Vector3.zero,3)
local db=grid:steer(b,b.root.Position,Vector3.zero,3)
assert(da.Magnitude>.9 and db.Magnitude>.9 and da:Dot(db)<-.99,'equal centers did not separate in opposite directions')
-- A cosmetic defeated body must disappear from steering even before the next rebuild.
local oldAttr=b.GetAttribute
b.GetAttribute=function(self,name) if name=='DeathPopped' then return true end;return oldAttr(self,name) end
assert(grid:steer(a,a.root.Position,Vector3.zero,3).Magnitude<.001,'dead cached neighbor still pushes')
grid:invalidate();grid:rebuild()
assert(not grid.entries[b],'defeated model remained in grid')
-- Legacy unannotated large bodies use the same cached footprint as their neighbors.
children={}
local large=mob(Vector3.zero,false,Vector3.new(7,8,7))
large.GetAttribute=function() return nil end
local other=mob(Vector3.new(5,0,0))
grid=Grid.new(folder,4.5)
local largeMove=grid:steer(large,large.root.Position,Vector3.zero,3)
assert(grid.entries[large].body==3.5 and largeMove.X<0,'large own footprint ignored')
-- Alternating neighboring pressure must not snap the movement vector left/right every think.
children={}
local moving=mob(Vector3.zero)
local noisy=mob(Vector3.new(0,0,2))
local time=0
grid=Grid.new(folder,4.5,function() return time end)
local previous=grid:steer(moving,Vector3.zero,Vector3.new(100,0,0),3)
local maxChange=0
for i=1,30 do
 time=i*.1
 noisy.root.Position=Vector3.new(0,0,i%2==0 and 2 or -2)
 grid:invalidate()
 local command=grid:steer(moving,Vector3.zero,Vector3.new(100,0,0),3)
 maxChange=math.max(maxChange,(command-previous).Magnitude)
 assert((command-previous).Magnitude<=.35001,'crowd correction snapped left/right')
 previous=command
end
-- Moderate hitch caps integration; a long pause clears stale movement history.
time+=.5;noisy.root.Position=Vector3.new(0,0,2);grid:invalidate()
local afterHitch=grid:steer(moving,Vector3.zero,Vector3.new(100,0,0),3)
assert((afterHitch-previous).Magnitude<=.52501,'hitch exceeded acceleration bound')
time+=1
local afterPause=grid:steer(moving,Vector3.zero,Vector3.new(-100,0,0),3)
assert(afterPause.X<0 and afterPause.Magnitude<=1.00001,'pause resumed stale forward command')
-- Passing side survives small target movements around a head-on boss approach.
children={}
local blockingBoss=mob(Vector3.zero,true,Vector3.new(8,10,6))
local walker=mob(Vector3.new(-10,0,0))
time=0;grid=Grid.new(folder,4.5,function() return time end)
local sign=nil
for i=1,20 do
 time=i*.1
 local command=grid:steer(walker,walker.root.Position,Vector3.new(20,0,i%2==0 and 2 or -2),3)
 local side=grid.steering[walker].sides[blockingBoss]
 sign=sign or side
 assert(side==sign and command.Z*sign<0,'boss passing side oscillated')
end
print('PASS smooth correction/hitch/pause/stable boss side; max command change:',maxChange)
-- Kinematic crowd comparison: 60 regulars converge through a stationary Hammer-sized body.
-- Both versions use the actual module; this isolates steering from Humanoid physics.
local function simulate(modern, module)
 children={}
 local boss=mob(Vector3.new(0,0,0),true,Vector3.new(8,10,6))
 local crowd={}
 for i=1,60 do
  local angle=math.pi*.65+(i%12)/11*math.pi*.7
  local radius=18+math.floor((i-1)/12)*4
  crowd[i]=mob(Vector3.new(math.cos(angle)*radius,0,math.sin(angle)*radius))
 end
 local time=0
 local grid=(module or Grid).new(folder,4.5,function() return time end)
 local goal=Vector3.new(10,0,0)
 local lastMoves,reversals={},0
 for tick=1,180 do
  time=tick*.05
  grid:invalidate();grid:rebuild()
  local moves={}
  for i,npc in crowd do
   local p=npc.root.Position
   local delta=goal-p
   if modern then moves[i]=grid:steer(npc,p,goal,3)
   else
    local direction=(delta.Magnitude>=3 and delta.Unit or Vector3.zero)+grid:separation(npc,p)*1.8
    moves[i]=direction.Magnitude>.05 and direction.Unit or Vector3.zero
   end
   if lastMoves[i] and moves[i].Magnitude>.1 and lastMoves[i].Magnitude>.1 and moves[i].Unit:Dot(lastMoves[i].Unit)<0 then reversals+=1 end
   lastMoves[i]=moves[i]
   assert(moves[i].Magnitude<=1.00001 and moves[i].Y==0,'unbounded/nonflat crowd movement')
  end
  for i,npc in crowd do npc.root.Position+=moves[i]*16*.05 end
 end
 local inside,pairs=0,0
 for i,npc in crowd do
  if npc.root.Position.Magnitude<6.9 then inside+=1 end
  for j=i+1,#crowd do if (npc.root.Position-crowd[j].root.Position).Magnitude<2 then pairs+=1 end end
 end
 return inside,pairs,reversals
end
local oldInside,oldPairs=simulate(false)
local newInside,newPairs,newReversals=simulate(true)
assert(newInside<oldInside,'new crowd did not clear boss body')
assert(newPairs<oldPairs,'new crowd did not reduce overlaps')
print('Crowd simulation old/new inside boss:',oldInside,newInside,'pairs under2:',oldPairs,newPairs)
if BeforeGrid then
 local _,beforePairs,beforeReversals=simulate(true,BeforeGrid)
 assert(newReversals<beforeReversals,'damping did not reduce crowd direction reversals')
 print('Before/current damping: pairs',beforePairs,newPairs,'direction reversals',beforeReversals,newReversals)
end
local legacy=legacyTests(Grid)
assert(legacy.passed)
print('PASS crowd steering; legacy grid checks:',legacy.checks)
'''

base = Path(__file__).resolve().parent
source = (base / "EnemySpatialGrid.luau").read_text()
legacy = (base / "EnemySpatialGridTests.luau").read_text()
before = Path(sys.argv[2]).read_text() if len(sys.argv)>2 else "return nil"
with tempfile.TemporaryDirectory(prefix="roguelite-crowd-tests-") as directory:
    harness = Path(directory) / "CrowdSteeringTests.luau"
    harness.write_text(PRELUDE + "\nlocal BeforeGrid=(function()\n" + before + "\nend)()\nlocal Grid=(function()\n" + source + "\nend)()\nlocal legacyTests=(function()\n" + legacy + "\nend)()\n" + CHECKS)
    subprocess.run([sys.argv[1], str(harness)], check=True)
