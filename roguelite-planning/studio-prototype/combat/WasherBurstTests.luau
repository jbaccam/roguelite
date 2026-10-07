-- Client fixture: require(ReplicatedStorage.WasherBurstTests).run(); never grants equipment/rewards.
local T={}
function T.run()
 local RS=game:GetService('ReplicatedStorage')
 local U=require(RS.RogueliteCombat.UtilityMotion)
 local Visual=require(RS.RogueliteCombat.UtilityVisuals)
 local n=0
 local function check(ok,msg) assert(ok,msg);n+=1 end
 check(U.washPressure(.1)==1,'full pressure')
 check(math.abs(U.washPressure(.9)-.5)<.001,'trickle')
 check(U.washPressure(1.2)==0,'refill must fully stop')
 local integral=0
 for i=0,13999 do integral+=U.washPressure((i+.5)*.0001)*.0001 end
 check(math.abs(integral*U.WashDamageScale/U.WashPeriod-1)<.0001,'sustained damage preserved')
 local folder=Instance.new('Folder');folder.Name='WasherBurstQA';folder.Parent=workspace
 local visual=Visual.mount(nil,folder,function() return nil end,{preview=true})
 local start=workspace:GetServerTimeNow();local origin=Vector3.new(0,500,0)
 visual.handle('Stream','QA','29',0,1,origin,origin+Vector3.new(20,0,0),.6,start+10,7,start)
 local full,trickle,empty=false,false,false
 while workspace:GetServerTimeNow()-start<1.38 do
  visual.step(.03)
  local model=folder:FindFirstChild('WaterStream')
  local pressure=model:GetAttribute('Pressure')
  full=full or pressure>.99;trickle=trickle or pressure>0 and pressure<.9;empty=empty or pressure==0
  task.wait(.03)
 end
 check(full and trickle and empty,'live cycle includes full, taper and empty phases')
 -- Start fresh pressure, retain emitted droplets through an explicit shutoff.
 local restart=workspace:GetServerTimeNow()
 visual.handle('Stream','QA','29',0,1,origin,origin+Vector3.new(20,0,0),.6,restart+10,7,restart)
 visual.step(.06)
 local model=folder:FindFirstChild('WaterStream')
 local tracked
 for _,p in model:GetChildren() do if p.Transparency<1 then tracked=p;break end end
 check(tracked~=nil,'actual water emitted')
 local p0=tracked.Position
 visual.handle('StreamEnd','QA');task.wait(.05);visual.step(.05)
 check(model.Parent~=nil and tracked.Transparency<1,'shutoff retains airborne water')
 check(tracked.Position.X>p0.X,'airborne water continues forward after shutoff')
 local before=tracked.Position
 task.wait(.2);visual.step(.2)
 check(tracked.Position.Y-before.Y<1,'gravity bends aging water down')
 task.wait(.35);visual.step(.03)
 check(folder:FindFirstChild('WaterStream')==nil,'all water retires after its own lifetime')
 visual.destroy();folder:Destroy()
 return {passed=n}
end
return T
