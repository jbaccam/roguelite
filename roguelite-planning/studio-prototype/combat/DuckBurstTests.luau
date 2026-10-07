-- Run in Play Client: require(ReplicatedStorage.DuckBurstTests)().
-- Uses isolated preview folder, never grants items/rewards or mutates a live loadout.
return function()
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
