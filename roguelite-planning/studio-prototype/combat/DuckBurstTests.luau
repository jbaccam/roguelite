-- Run in Play Client: require(ReplicatedStorage.DuckBurstTests)().
-- Uses isolated preview folder, never grants items/rewards or mutates a live loadout.
-- Pure Area Size checks (2026-10-09): require(<this module>).area(UtilityWeapons) from a server or
-- Edit context, or combat/run_shop_tests.py (luau.exe). Returns the number of checks.
local T={}
function T.area(W)
 local checks=0
 local function check(ok,message) assert(ok,message);checks+=1 end
 local function near(a,b,message) check(math.abs(a-b)<1e-6,message..': '..a..' / '..b) end
 local half=math.acos(.84)
 near(W.duckConeDot(0),.84,'no Area: the old .84 cone')
 near(W.duckConeDot(nil),.84,'no stat: the old cone')
 near(math.acos(W.duckConeDot(50)),half*1.5,'+50% Area: half-angle x1.5')
 near(W.duckConeDot(50),math.cos(half*1.5),'+50% Area: dot .652')
 check(math.abs(W.duckConeDot(50)-.6522)<.001 and math.abs(math.deg(math.acos(W.duckConeDot(50)))-49.29)<.01,'+50% Area: 49.3 deg')
 near(math.acos(W.duckConeDot(15)),half*1.15,'one Hot Sauce: x1.15')
 near(W.duckConeDot(150),W.duckConeDot(50),'capped at x1.5')
 near(W.duckConeDot(-80),math.cos(half*.5),'floored at x0.5')
 near(W.duckConeDot(0/0),.84,'NaN Area is treated as none')
 local last=1
 for a=-60,160,10 do local dot=W.duckConeDot(a);check(dot<=last+1e-12 and dot>0,'wider never narrows, never past 90 deg: '..a);last=dot end
 -- A zombie 40 deg off the aim: missed with no Area, hit with +50%.
 local off=math.cos(math.rad(40))
 check(not (off>W.duckConeDot(0)) and off>W.duckConeDot(50),'40 deg off: hit only with +50% Area')
 return checks
end
local function run()
 local C=game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
 local Motion=require(C.SpecialMotion)
 local checks=0
 local function check(ok,message) assert(ok,message);checks+=1 end
 for _,cd in {.03,.05,.08,.1,.15,.22,.32,.5,1,2} do
  local t=Motion.duckTiming(cd)
  check(t.pulses==3,'three fuel pulses')
  check(t.cycle-(t.pulses-1)*t.spacing-t.emission>=.42,'visible rest survives attack speed')
  check(math.abs(t.pulses*t.damageScale/t.cycle-1/cd)<1e-6,'nominal sustained DPS preserved')
  check(t.cycle-(t.pulses-1)*t.spacing-t.emission-.24>=.18,'old flame expires before next burst')
 end
 if not game:GetService('RunService'):IsClient() then return {checks=checks,visual='requires Play Client'} end
 local folder=Instance.new('Folder');folder.Name='DuckBurstQA';folder.Parent=workspace
 local fx=require(C.SpecialWeaponVisuals).mount(C,folder,function() return nil end,{preview=true})
 local ok,err=pcall(function()
  local origin=Vector3.new(0,15,0)
  fx.handle('Spray','qa',origin,Vector3.zAxis,12,-1001,1,.11)
  fx.step(.01)
  local nozzle=folder:FindFirstChild('DuckFlameNozzle')
  check(nozzle~=nil,'emission creates one nozzle')
  local flame=nozzle:FindFirstChild('BurstFlame')
  check(flame and flame.Enabled,'burst emits')
  check(flame.Lifetime.Min==flame.Lifetime.Max,'fixed age expiry gives oldest first')
  check(not flame.LockedToPart and flame.VelocityInheritance==0,'released fire does not follow nozzle')
  check(flame.Acceleration.Y<0,'fire fuel drops under gravity')
  task.wait(.16);fx.step(.16)
  check(not flame.Enabled and nozzle.Parent==folder,'fuel stops while old particles drain')
  task.wait(.27);fx.step(.27)
  check(nozzle.Parent==nil,'drained nozzle cleaned up')
  -- Separate slots must not extend each other's emission/cooldown visuals.
  fx.handle('Spray','qa1',origin,Vector3.zAxis,12,-1001,1,.11)
  fx.handle('Spray','qa2',origin,Vector3.xAxis,12,-1001,2,.11)
  check(#folder:GetChildren()==2,'independent per-slot nozzles')
 end)
 fx.destroy();folder:Destroy()
 assert(ok,err)
 return {checks=checks,visual='emission, gravity, independent lifetime and cleanup passed'}
end
-- Still callable as before: require(ReplicatedStorage.DuckBurstTests)().
return setmetatable(T,{__call=function(_,...) return run(...) end})
