-- Server-owned rare heart pickups. A real combat kill may drop one; any living player
-- inside their PickupRadius pulls it in and heals on arrival (a full-health player just
-- uses it up). Unclaimed hearts expire after LIFETIME. No remote, no client-supplied
-- amounts. Hearts clear whenever the run leaves Combat.
-- Variants (spawnAt's second argument) share all of this with their own kind, lifetime, heal
-- and pickup check: Chef pizza slices (ChefPizzaService, attached at the bottom). Their Kind
-- attribute tells the clients apart; the heart cap counts hearts only.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local Motion=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('ShardMotion'))
local H={drops={},
 BASE_CHANCE=.01, -- per eligible kill
 LUCK_CHANCE=.0002, -- per Luck point of the killer (Luck 100 -> +2%)
 MAX_CHANCE=.03,
 HEAL=15, -- before Recovery; base max health is 100
 MAX_ACTIVE=3,
 LIFETIME=10, -- seconds on the ground before it vanishes (HeartVisuals blinks the last 3)
 MIN_PICKUP_RADIUS=4,
}
local characters
local rng=Random.new()
local folder=Instance.new('Folder');folder.Name='RogueliteHeartDrops';folder.Parent=workspace
-- ShopService requires this module before it creates RogueliteRunState, so never
-- wait for it at load time: that would deadlock the whole server.
local function inCombat() local run=RS:FindFirstChild('RogueliteRunState');return run~=nil and run:GetAttribute('Phase')=='Combat' end
local function living(p)
 local c=p and p.Character;local h=c and c:FindFirstChildOfClass('Humanoid');local r=c and c:FindFirstChild('HumanoidRootPart')
 if h and h.Health>0 and r and not p:GetAttribute('LobbyPreviewActive') then return r,h end
end
function H.configure(c) characters=c end
local function remove(i) local d=table.remove(H.drops,i);if d then d.model:Destroy() end end
function H.clear() for i=#H.drops,1,-1 do remove(i) end end
function H.chance(luck)
 -- Studio-only test hook, ignored in live servers. (TestZombieCountOverride is different: the admin panel's Keep N alive sets it, so developers can use it live.)
 local test=RunService:IsStudio() and RS.RogueliteCombat:GetAttribute('TestHeartChance')
 if type(test)=='number' then return math.clamp(test,0,1) end
 return math.clamp(H.BASE_CHANCE+math.max(0,tonumber(luck) or 0)*H.LUCK_CHANCE,0,H.MAX_CHANCE)
end
-- variant (optional): {kind, owner, lifetime, heal=function(humanoid) base HP, allow=function(d,now,distance,radius) bool,
-- arrive=function(player) after the heal (Chef pizza's Full Belly stack)}.
function H.spawnAt(position,variant)
 if not inCombat() then return nil end
 if not variant then local hearts=0;for _,d in H.drops do if not d.kind then hearts+=1 end end;if hearts>=H.MAX_ACTIVE then return nil end end
 local exclude={folder}
 local mobs=workspace:FindFirstChild('RogueliteEnemies');if mobs then table.insert(exclude,mobs) end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=exclude
 local ground=workspace:Raycast(position+Vector3.new(0,2,0),Vector3.new(0,-100,0),params)
 local at=ground and ground.Position+Vector3.new(0,1.6,0) or position
 local model=Instance.new('Model');model.Name=variant and variant.kind..'Pickup' or 'HeartPickup'
 local root=Instance.new('Part');root.Name='HeartMarker';root.Size=Vector3.one*.1;root.Transparency=1
 root.Anchored=true;root.CanCollide=false;root.CanTouch=false;root.CanQuery=false;root.CastShadow=false
 root.CFrame=CFrame.new(at);root.Parent=model;model.PrimaryPart=root
 local born=workspace:GetServerTimeNow()
 local lifetime=variant and variant.lifetime or H.LIFETIME
 model:SetAttribute('Origin',at);model:SetAttribute('BornAt',born)
 if variant then model:SetAttribute('Kind',variant.kind);model:SetAttribute('OwnerUserId',variant.owner and variant.owner.UserId) else model:SetAttribute('HealAmount',H.HEAL) end
 model:SetAttribute('ExpiresAt',born+lifetime)
 model.Parent=folder
 local d={model=model,origin=at,position=at,born=born,lifetime=lifetime}
 if variant then d.kind=variant.kind;d.owner=variant.owner;d.heal=variant.heal;d.allow=variant.allow;d.arrive=variant.arrive end
 table.insert(H.drops,d);return d
end
function H.removeDrop(d) local i=table.find(H.drops,d);if i then remove(i) end end
-- Called once per real death (never practice bosses/targets, never split children).
function H.roll(npc,position)
 if not inCombat() or not characters or npc:GetAttribute('PracticeTarget') or npc:GetAttribute('IsBoss') or npc:GetAttribute('SplitChild') then return nil end
 if not Tags:HasTag(npc,'RogueliteZombie') or npc:GetAttribute('HeartRolled') then return nil end
 npc:SetAttribute('HeartRolled',true)
 local id=npc:GetAttribute('LastDamageUserId');local killer=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
 local state=killer and characters.states[killer]
 if rng:NextNumber()>=H.chance(state and state.stats.Luck or 0) then return nil end
 return H.spawnAt(position)
end
local function cancel(d) d.target=nil;d.started=nil;d.model:SetAttribute('MagnetUserId',nil);d.model:SetAttribute('MagnetStart',nil) end
function H.collect(p,d)
 if not inCombat() or d.target or not d.model.Parent then return false end
 local now=workspace:GetServerTimeNow()
 if now-d.born<Motion.REST_SECONDS then return false end
 local r,h=living(p);local s=characters and characters.states[p]
 -- Full-health players still grab it (it's wasted), so hearts can't be banked for later.
 if not r or not s then return false end
 local radius=math.max(H.MIN_PICKUP_RADIUS,math.clamp(s.stats.PickupRadius or 0,0,100))
 local distance=(r.Position-d.origin).Magnitude
 if distance>radius then return false end
 if d.allow and not d.allow(d,now,distance,radius) then return false end -- a variant's own rules (ChefPizza.canCollect)
 d.target=p;d.started=now;d.startPosition=Motion.idle(d.origin,d.born,now)
 d.model:SetAttribute('MagnetOrigin',d.startPosition);d.model:SetAttribute('MagnetStart',now);d.model:SetAttribute('MagnetUserId',p.UserId)
 return true
end
function H.step(now)
 if not inCombat() then if #H.drops>0 then H.clear() end;return end
 for i=#H.drops,1,-1 do
  local d=H.drops[i]
  if not d.model.Parent then remove(i)
  elseif not d.target and now>=d.born+d.lifetime then remove(i)
  elseif d.target then
   local r=living(d.target)
   if not r or (r.Position-d.origin).Magnitude>100 then cancel(d)
   elseif now-d.started>=Motion.PULL_SECONDS then
    local _,h=living(d.target);local before=h.Health
    characters.heal(d.target,d.heal and d.heal(h) or H.HEAL) -- Recovery applies inside heal
    d.model:SetAttribute('Healed',h.Health-before)
    if d.arrive then local ok,err=pcall(d.arrive,d.target);if not ok then warn('HeartDropService: pickup hook failed:',err) end end
    remove(i)
   end
  else
   for _,p in Players:GetPlayers() do if H.collect(p,d) then break end end
  end
 end
end
Players.PlayerRemoving:Connect(function(p) for _,d in H.drops do if d.target==p then cancel(d) end end end)
local pausedAt -- plan L: server time when the run paused
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<1/30 then return end;elapsed=0
 local now=workspace:GetServerTimeNow()
 -- Pause (plan L): hearts wait out a paused run; their age and ExpiresAt move later by it.
 if RS.RogueliteCombat:GetAttribute('RunPaused')==true then pausedAt=pausedAt or now;return end
 if pausedAt then
  local by=now-pausedAt;pausedAt=nil
  for _,d in H.drops do
   d.born+=by
   if d.model.Parent then d.model:SetAttribute('BornAt',d.born);d.model:SetAttribute('ExpiresAt',d.born+d.lifetime) end
  end
 end
 H.step(now)
end)
-- Chef pizza slices. Looked up, not waited on: a place without the module still has hearts.
local pizza=script.Parent:FindFirstChild('ChefPizzaService')
if pizza then
 local ok,err=pcall(function() require(pizza).attach(H) end)
 if not ok then warn('HeartDropService: ChefPizzaService failed to load:',err) end
end
return H
