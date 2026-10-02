-- Legendary extra moves at Tier IV (RARITY_GODLY_ARMOR.md §8, plan J item 8), server-owned:
--   03 Katana: every 3rd swing throws a flying slash through a line of enemies
--   11 Rocket Launcher: every 4th rocket flies a short way, then splits into 3 homing mini rockets
--   18 Deck of Cards: every 5th throw is a Royal Flush, 5 gold cards that pierce everything
--   22 Bowling Ball: a roll that hits 5+ enemies is a STRIKE! with a pin explosion where it stops
--   25 Wrecking Ball: each swing that connects sends a ground shockwave ring out from the hit
--   32 Excalibur: every swing also shoots a golden beam slash
--   31 Mjolnir: every 4th throw calls down a lightning strike where it lands
-- Numbers live in WeaponCatalog.Legendary. Every move hit is a secondary hit (no crits, chains,
-- knockback or other specials, and it can never start another move), and everything is capped.
-- Clients draw from LegendaryFX (LegendaryVisuals); each attack's count shows on the slot as the
-- LegendaryCharge attribute, so the weapon's gold aura builds toward the move.
-- ModuleScript in ServerScriptService, Sandboxed (required by the sandboxed combat script).
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Players=game:GetService('Players')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Motion=require(combat:WaitForChild('WeaponMotion'))
local Batch=require(combat:WaitForChild('ShotBatch'))
local L={}
L.MaxMovers=48 -- slashes and cards in flight, per server
L.MaxScheduled=256

-- Pure helpers (LegendaryMovesTests) -------------------------------------------------------------
-- Is attack number `count` (1, 2, 3 ...) the move? Every 3rd: counts 3, 6, 9 ...
function L.due(count,every) return every<=1 or count%every==0 end
-- Flat (XZ) distance from p to the segment a->b, and how far along it (0..1).
function L.segmentDistance(p,a,b)
 local ab=Vector3.new(b.X-a.X,0,b.Z-a.Z);local ap=Vector3.new(p.X-a.X,0,p.Z-a.Z)
 local len2=ab:Dot(ab);if len2<1e-6 then return ap.Magnitude,0 end
 local t=math.clamp(ap:Dot(ab)/len2,0,1)
 return (ap-ab*t).Magnitude,t
end
-- n flat directions fanned evenly over `fan` degrees around `direction` (a held hand of cards).
function L.fan(direction,n,fan)
 local out={}
 for i=1,n do
  local angle=n>1 and math.rad(-fan/2+fan*(i-1)/(n-1)) or 0
  out[i]=CFrame.Angles(0,angle,0):VectorToWorldSpace(direction)
 end
 return out
end
-- Mini-rocket targets: the main target first, then the nearest others, each once; with fewer
-- enemies than minis the main target takes the rest.
function L.splitTargets(main,others,n)
 local out={main}
 for _,npc in others do
  if #out>=n then break end
  if npc~=main and not table.find(out,npc) then out[#out+1]=npc end
 end
 while #out<n do out[#out+1]=main end
 return out
end
-- How much of a blast lands at `distance` from its centre: all of it at the centre, 35% at the edge
-- (the rocket's falloff).
function L.falloff(distance,radius) return 1-.65*math.clamp(distance/math.max(radius,.01),0,1) end
-- When an expanding ring (radius over duration) reaches something `distance` away.
function L.ringDelay(distance,radius,duration) return math.clamp(distance/math.max(radius,.01),0,1)*duration end

function L.new(damage,canTarget,rayParams)
 local fx=combat:WaitForChild('LegendaryFX')
 local counts={} -- 'userId:slot:weaponId' -> attacks so far (Tier IV only)
 local movers={};local moverCount=0;local scheduled={};local serial=0
 local function nextKey() serial+=1;return serial end
 local function alive(npc)
  local h=npc and npc.Parent and npc:FindFirstChildOfClass('Humanoid');local r=npc and npc:FindFirstChild('HumanoidRootPart')
  if h and r and h.Health>0 and npc:IsDescendantOf(workspace) and Tags:HasTag(npc,'RogueliteZombie') then return h,r end
 end
 local function ownerAlive(d)
  local h=d.character and d.character:FindFirstChildOfClass('Humanoid')
  return d.owner and d.owner.Parent==Players and d.owner.Character==d.character and h and h.Health>0
 end
 -- A practice swing only hits practice targets; everything else follows the owner's targeting.
 local function allowed(d,npc)
  return (not d.practiceTarget or npc:GetAttribute('PracticeTarget')==true) and canTarget(d.owner,npc)
 end
 -- Living enemies this owner may hit within range of position, nearest first.
 local function around(d,position,range,skip)
  local out={}
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local h,r=alive(npc)
   if h and not (skip and skip[npc]) and allowed(d,npc) then
    local distance=(r.Position-position).Magnitude
    if distance<=range then out[#out+1]={npc=npc,distance=distance} end
   end
  end
  table.sort(out,function(a,b) return a.distance<b.distance end)
  local list={};for i,e in out do list[i]=e.npc end
  return list
 end
 local function later(at,fn)
  if #scheduled>=L.MaxScheduled then return end
  scheduled[#scheduled+1]={at=at,fn=fn}
 end
 local function send(position,owner,...) Batch.fire(fx,position,owner,...) end
 local function area(d) return Stats.mult(d.stats.AreaSize) end
 local function slotFolder(d)
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId))
  return state and state:FindFirstChild('Slot'..tostring(d.slotIndex))
 end
 -- Counts this attack and says whether it is the move; the slot's LegendaryCharge (0..every-1)
 -- lets the client aura build toward it.
 local function count(d,spec)
  local key=d.owner.UserId..':'..tostring(d.slotIndex)..':'..d.id
  local n=(counts[key] or 0)+1;counts[key]=n
  local slot=slotFolder(d)
  if slot then slot:SetAttribute('LegendaryCharge',n%spec.every) end
  return L.due(n,spec.every)
 end
 -- The ground under a point (enemies and players don't count), else the point.
 local function groundAt(d,point)
  local hit=workspace:Raycast(point+Vector3.yAxis*3,-Vector3.yAxis*20,rayParams(d.character,true))
  return hit and hit.Position or point
 end
 -- Knock an enemy outward from a centre (bosses barely move), like the Trident's wave.
 local function push(npc,center,strength)
  local _,root=alive(npc);if not root then return end
  local away=Vector3.new(root.Position.X-center.X,0,root.Position.Z-center.Z)
  away=away.Magnitude>.05 and away.Unit or Vector3.xAxis
  local scale=(npc:GetAttribute('IsBoss') or npc:GetAttribute('IsMapBoss')) and .15 or 1
  root:ApplyImpulse((away*strength+Vector3.yAxis*strength*.3)*root.AssemblyMass*scale)
 end
 -- A straight mover (flying slash, beam slash, gold card): it flies `range` studs at `speed`, stops
 -- at a wall, and hits every enemy it passes once. Returns its key and how far it really goes.
 local function mover(d,origin,direction,range,speed,width,factor)
  if moverCount>=L.MaxMovers then return nil end
  local wall=workspace:Raycast(origin,direction*range,rayParams(d.character,true))
  if wall then range=math.max(1,(wall.Position-origin).Magnitude) end
  local key=nextKey()
  movers[key]={d=d,origin=origin,direction=direction,range=range,speed=speed,width=width,factor=factor,
   started=workspace:GetServerTimeNow(),traveled=0,hit={}}
  moverCount+=1
  return key,range
 end

 local api={}
 -- A melee attack began (RogueliteCombat): Katana's every 3rd swing and every Excalibur swing
 -- throw a slash. It leaves on the cut, not the wind-up.
 function api:swing(d,origin,target,direction)
  local spec=Catalog.legendaryMove(d.id,d.tier)
  if not spec or (spec.move~='Slash' and spec.move~='Beam') or not ownerAlive(d) or not count(d,spec) then return end
  local delay=Motion.SwingHitStart/math.max(d.motionRate or 1.8,.1)
  later(workspace:GetServerTimeNow()+delay,function()
   if not ownerAlive(d) then return end
   local root=d.character:FindFirstChild('HumanoidRootPart');if not root then return end
   local flat=Vector3.new(direction.X,0,direction.Z)
   flat=flat.Magnitude>.01 and flat.Unit or Vector3.new(root.CFrame.LookVector.X,0,root.CFrame.LookVector.Z).Unit
   local start=root.Position+flat*2.2-Vector3.yAxis*.4
   local range=spec.range*Stats.mult(d.stats.AttackRange)
   local width=math.clamp(spec.width*area(d),2,9)
   local key,reach=mover(d,start,flat,range,spec.speed,width,spec.factor)
   if key then send(start,d.owner,spec.move,key,d.owner.UserId,d.slotIndex,start,flat,reach,spec.speed,width,workspace:GetServerTimeNow()) end
  end)
 end
 -- The first enemy a melee swing touched (RogueliteCombat): the Wrecking Ball's shockwave ring
 -- spreads from under it and reaches each enemy as it passes.
 function api:contact(d,npc,point)
  local spec=Catalog.legendaryMove(d.id,d.tier);if not spec or spec.move~='Shock' or not ownerAlive(d) then return end
  local ground=groundAt(d,point)
  local radius=math.clamp(spec.radius*area(d),4,22)
  local now=workspace:GetServerTimeNow()
  send(ground,d.owner,'Shock',d.owner.UserId,ground,radius,spec.time,now)
  for _,other in around(d,ground,radius,{[npc]=true}) do
   local _,r=alive(other)
   later(now+L.ringDelay((r.Position-ground).Magnitude,radius,spec.time),function()
    if not alive(other) or not ownerAlive(d) then return end
    damage(other,d.damage*spec.factor,d,true)
    push(other,ground,spec.push)
   end)
  end
 end
 -- The Royal Flush: five gold cards (10, J, Q, K, A) fanned toward the target, each one piercing
 -- everything in its line.
 local function flush(d,spec,origin,aim)
  local flat=Vector3.new(aim.X-origin.X,0,aim.Z-origin.Z);flat=flat.Magnitude>.01 and flat.Unit or -Vector3.zAxis
  local range=d.range*spec.rangeScale
  local list={}
  for _,direction in L.fan(flat,spec.cards,spec.fan) do
   local key,reach=mover(d,origin,direction,range,d.projectileSpeed,spec.width,spec.factor)
   if key then list[#list+1]={key,direction,reach} end
  end
  send(origin,d.owner,'Flush',d.owner.UserId,d.slotIndex,origin,list,d.projectileSpeed,workspace:GetServerTimeNow())
 end
 -- The splitting rocket: it leaves the barrel like any rocket, splits after a short flight, and the
 -- mini rockets home onto three enemies (the target first) and burst when they arrive.
 local function split(d,spec,origin,aim,character)
  local main=d.arcTarget and d.arcTarget.Parent;if not main or not alive(main) then return false end
  local _,mainRoot=alive(main)
  local direction=aim-origin;if direction.Magnitude<.01 then return false end;direction=direction.Unit
  local start=origin+direction*1.8+Vector3.yAxis*.25 -- the barrel mouth (RocketProjectile)
  local carry=math.min(d.projectileSpeed*spec.splitAfter,(mainRoot.Position-start).Magnitude*.55)
  local splitAt=start+direction*carry
  local block=workspace:Raycast(start,splitAt-start,rayParams(character,true))
  if block then splitAt=block.Position-direction*.5 end
  local now=workspace:GetServerTimeNow()
  local splitTime=now+(splitAt-start).Magnitude/d.projectileSpeed
  local radius=math.clamp(spec.radius*area(d),2.5,12)
  local minis={}
  for i,npc in L.splitTargets(main,around(d,mainRoot.Position,16,{[main]=true}),spec.minis) do
   local _,r=alive(npc);local at=r and r.Position or mainRoot.Position
   local arrive=splitTime+(at-splitAt).Magnitude/spec.speed+.1+(i-1)*.07
   minis[i]={arrive,at,npc} -- the enemy last, so a client that can't see it gets no hole
   later(arrive,function()
    if not ownerAlive(d) then return end
    local _,root=alive(npc);local center=root and root.Position or at
    for _,other in around(d,center,radius) do
     local _,rr=alive(other)
     damage(other,d.damage*spec.factor*L.falloff((rr.Position-center).Magnitude,radius),d,true)
    end
   end)
  end
  send(start,d.owner,'Split',d.owner.UserId,d.slotIndex,start,splitAt,now,splitTime,minis,radius,spec.spread)
  return true
 end
 -- A ranged attack is about to fire (RogueliteCombat.shoot). True when the move replaced it (the
 -- rocket split, the Royal Flush); a Mjolnir throw is only marked for its lightning.
 function api:shoot(d,origin,aim,character)
  local spec=Catalog.legendaryMove(d.id,d.tier);if not spec or not ownerAlive(d) then return false end
  if spec.move=='Thunder' then
   if count(d,spec) then d.legendaryThunder=true end
   return false
  elseif spec.move=='Flush' then
   if not count(d,spec) then return false end
   flush(d,spec,origin,aim);return true
  elseif spec.move=='Split' then
   if not count(d,spec) then return false end
   return split(d,spec,origin,aim,character)
  end
  return false
 end
 -- A thrown weapon stopped (SpecialWeapons hooks.impact): Mjolnir's marked throw calls the
 -- lightning; a bowling roll that hit 5+ enemies is a STRIKE.
 function api:impact(d,position,hit)
  local spec=Catalog.legendaryMove(d.id,d.tier);if not spec or not ownerAlive(d) then return end
  local now=workspace:GetServerTimeNow()
  if spec.move=='Thunder' and d.legendaryThunder then
   d.legendaryThunder=nil -- once per throw
   local ground=groundAt(d,position)
   local radius=math.clamp(spec.radius*area(d),4,18)
   send(ground,d.owner,'Thunder',d.owner.UserId,ground,radius,now+spec.delay)
   later(now+spec.delay,function()
    if not ownerAlive(d) then return end
    for _,npc in around(d,ground,radius) do damage(npc,d.damage*spec.factor,d,true) end
   end)
  elseif spec.move=='Strike' then
   local n=0;for _ in hit or {} do n+=1 end
   if n<spec.hits then return end
   local ground=groundAt(d,position)
   local radius=math.clamp(spec.radius*area(d),4,20)
   send(ground,d.owner,'Strike',d.owner.UserId,ground,radius,n,now)
   later(now+.1,function() -- the pins burst a beat after the ball stops
    if not ownerAlive(d) then return end
    for _,npc in around(d,ground,radius) do damage(npc,d.damage*spec.factor,d,true);push(npc,ground,spec.push) end
   end)
  end
 end

 Players.PlayerRemoving:Connect(function(p)
  local prefix=p.UserId..':'
  for key in counts do if string.sub(key,1,#prefix)==prefix then counts[key]=nil end end
 end)
 -- Scheduled hits every frame; movers sweep the stretch they covered since the last frame.
 RunService.Heartbeat:Connect(function()
  local now=workspace:GetServerTimeNow()
  if #scheduled>0 then
   local due={}
   for i=#scheduled,1,-1 do if scheduled[i].at<=now then due[#due+1]=scheduled[i].fn;table.remove(scheduled,i) end end
   for i=#due,1,-1 do local ok,err=pcall(due[i]);if not ok then warn('LegendaryMoves scheduled hit failed:',err) end end
  end
  if moverCount==0 then return end
  local enemies=Tags:GetTagged('RogueliteZombie')
  for key,m in movers do
   if not ownerAlive(m.d) then movers[key]=nil;moverCount-=1;continue end
   local distance=math.min(m.range,math.max(0,now-m.started)*m.speed)
   if distance>m.traveled then
    local a=m.origin+m.direction*m.traveled;local b=m.origin+m.direction*distance
    local mid=(a+b)/2;local reach=(distance-m.traveled)/2+m.width+4
    for _,npc in enemies do
     if not m.hit[npc] then
      local h,r=alive(npc)
      if h and (r.Position-mid).Magnitude<=reach and math.abs(r.Position.Y-a.Y)<7 and allowed(m.d,npc) then
       -- A boss is far wider than its root: give it the room its body takes.
       local slack=(npc:GetAttribute('IsMapBoss') or npc:GetAttribute('IsHammerBoss')) and 4 or 1
       if L.segmentDistance(r.Position,a,b)<=m.width*.5+slack then
        m.hit[npc]=true;damage(npc,m.d.damage*m.factor,m.d,true)
       end
      end
     end
    end
    m.traveled=distance
   end
   if m.traveled>=m.range then movers[key]=nil;moverCount-=1 end
  end
 end)
 return api
end
return L
