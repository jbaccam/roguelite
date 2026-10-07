local RunService=game:GetService('RunService')
local Vacuum=require(game.ReplicatedStorage.RogueliteCombat.VacuumVisuals)
local U=require(game.ReplicatedStorage.RogueliteCombat.UtilityMotion)
local V={}
function V.mount(combat,folder,lookup,options)
 options=options or {}
 local closed=false
 local streams={};local vacuumPool={};local vacuumCount=0
 local walls=RaycastParams.new();walls.FilterType=Enum.RaycastFilterType.Exclude
 walls.FilterDescendantsInstances={folder};walls.RespectCanCollide=true
 local function clear(key)
  local s=streams[key];if not s then return end
  if s.vacuum then s.vacuum:hide();table.insert(vacuumPool,s.vacuum) else s.model:Destroy() end
  streams[key]=nil
 end
 local function stop(key)
  local s=streams[key];if not s then return end
  if s.vacuum then clear(key) else s.stopped=true end -- let emitted water finish its own lifetime
 end
 local function onFx(action,key,...)
  if closed then return end
  if action=='StreamEnd' then stop(key);return end
  if action~='Stream' then return end
  local id,owner,slot,origin,finish,width,expires,safe,started=...
  local s=streams[key]
  if s and s.id~=id then clear(key);s=nil end
  if not s then
   if id=='28' then
    local visual=table.remove(vacuumPool)
    if not visual then
     if vacuumCount>=12 then return end
     visual=Vacuum.new(folder);vacuumCount+=1
    end
    s={id=id,vacuum=visual,model=visual.model};streams[key]=s
   else
    local count=0;for _,other in streams do if not other.vacuum then count+=1 end end
    if count>=24 then return end
    local model=Instance.new('Model');model.Name='WaterStream';model.Parent=folder
    s={id=id,model=model,drops={},credit=0,serial=0};streams[key]=s
    -- Reused slots, never retargeted after emission. Fixed lifespan guarantees FIFO expiry.
    for i=1,40 do
     local p=Instance.new('Part');p.Name='WaterDroplet';p.Shape=Enum.PartType.Ball;p.Size=Vector3.one*.19
     p.Color=Color3.fromRGB(151,218,255);p.Transparency=1;p.Material=Enum.Material.SmoothPlastic
     p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false;p.Parent=model
     s.drops[i]={part=p}
    end
   end
  end
  s.owner=owner;s.slot=slot;s.origin=origin;s.finish=finish;s.width=width;s.expires=expires;s.safe=safe
  s.started=started or s.started or workspace:GetServerTimeNow();s.stopped=false
 end
 local function step(dt)
  if closed then return end
  local now=workspace:GetServerTimeNow()
  for key,s in streams do
   if not folder.Parent then clear(key);continue end
   if now>s.expires then stop(key);if s.vacuum then continue end end
   local origin=s.origin;local visual=lookup(s.owner,s.slot)
   if visual and visual.model.Parent then origin=visual.model:GetPivot():PointToWorldSpace(Vector3.new(0,0,-1.1)) end
   s.smoothFinish=s.smoothFinish and s.smoothFinish:Lerp(s.finish,1-math.exp(-18*dt)) or s.finish
   if s.vacuum then s.vacuum:update(origin,s.smoothFinish,s.width,now);continue end
   local pressure=s.stopped and 0 or U.washPressure(now-s.started)
   s.model:SetAttribute('Pressure',pressure)
   local delta=s.smoothFinish-origin
   local direction=delta.Magnitude>.05 and delta.Unit or Vector3.zAxis
   local right=direction:Cross(Vector3.yAxis);right=right.Magnitude>.01 and right.Unit or Vector3.xAxis
   -- Constant emission rate during pressure, tapering to disconnected drips as the trigger releases.
   s.credit=pressure>0 and math.min(8,s.credit+math.min(dt,.1)*65*pressure) or 0
   local wall=pressure>0 and workspace:Raycast(origin,direction*delta.Magnitude,walls)
   local wallDistance=wall and (wall.Position-origin).Magnitude
   local active=0
   for _,drop in s.drops do
    if drop.born then
     local age=now-drop.born
     if age>=drop.life then drop.born=nil;drop.part.Transparency=1
     else
      local nextPosition=drop.origin+drop.velocity*age-Vector3.yAxis*(.5*U.WashGravity*age*age)
      drop.part.CFrame=CFrame.lookAt(nextPosition,nextPosition+drop.velocity-Vector3.yAxis*(U.WashGravity*age));drop.part.Transparency=.25+.75*(age/U.WashLife)^2;active+=1
     end
    end
    if not drop.born and s.credit>=1 then
     s.credit-=1;s.serial+=1
     local lane=math.sin(s.serial*2.399)
     drop.born=now;drop.origin=origin+right*lane*.06
     -- Low-pressure droplets lose reach and sag, while the full jet arcs gently to its target.
     local speed=math.max(18,delta.Magnitude/.4)*(.25+.75*pressure)
     drop.life=wallDistance and math.min(U.WashLife,wallDistance/speed) or U.WashLife
     drop.velocity=direction*speed+Vector3.yAxis*(U.WashGravity*.2*pressure)+right*lane*.65
     drop.part.Position=drop.origin;drop.part.Transparency=.25
     local size=.11+.13*pressure
     drop.part.Size=Vector3.new(size,size,size*(1+3*pressure))
     drop.part.CFrame=CFrame.lookAt(drop.origin,drop.origin+drop.velocity)
     active+=1
    end
   end
   s.model:SetAttribute('ActiveDroplets',active)
   if s.stopped and active==0 then clear(key) end
  end
 end
 local function destroy()
  if closed then return end;closed=true
  for key in streams do clear(key) end
  for _,v in vacuumPool do v:destroy() end
  table.clear(vacuumPool)
 end
 if options.preview then return {handle=onFx,step=step,destroy=destroy} end
 combat.SpecialFX.OnClientEvent:Connect(onFx)
 RunService.RenderStepped:Connect(step)
end
return V
