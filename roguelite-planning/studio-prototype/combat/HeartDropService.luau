-- Server-owned rare heart pickups. A real combat kill may drop one; a hurt living
-- player inside their PickupRadius pulls it in and heals on arrival. No remote,
-- no client-supplied amounts. Hearts clear whenever the run leaves Combat.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local Motion=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('ShardMotion'))
local H={drops={},
 BASE_CHANCE=.025, -- per eligible kill
 LUCK_CHANCE=.0005, -- per Luck point of the killer (Luck 100 -> +5%)
 MAX_CHANCE=.08,
 HEAL=15, -- before Recovery; base max health is 100
 MAX_ACTIVE=6,
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
function H.spawnAt(position)
 if not inCombat() or #H.drops>=H.MAX_ACTIVE then return nil end
 local exclude={folder}
 local mobs=workspace:FindFirstChild('RogueliteEnemies');if mobs then table.insert(exclude,mobs) end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=exclude
 local ground=workspace:Raycast(position+Vector3.new(0,2,0),Vector3.new(0,-100,0),params)
 local at=ground and ground.Position+Vector3.new(0,1.6,0) or position
 local model=Instance.new('Model');model.Name='HeartPickup'
 local root=Instance.new('Part');root.Name='HeartMarker';root.Size=Vector3.one*.1;root.Transparency=1
 root.Anchored=true;root.CanCollide=false;root.CanTouch=false;root.CanQuery=false;root.CastShadow=false
 root.CFrame=CFrame.new(at);root.Parent=model;model.PrimaryPart=root
 local born=workspace:GetServerTimeNow()
 model:SetAttribute('Origin',at);model:SetAttribute('BornAt',born);model:SetAttribute('HealAmount',H.HEAL)
 model.Parent=folder
 local d={model=model,origin=at,position=at,born=born}
 table.insert(H.drops,d);return d
end
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
 -- Only hurt players pull hearts, so a full-health teammate never wastes one.
 if not r or not s or h.Health>=h.MaxHealth then return false end
 local radius=math.max(H.MIN_PICKUP_RADIUS,math.clamp(s.stats.PickupRadius or 0,0,100))
 if (r.Position-d.origin).Magnitude>radius then return false end
 d.target=p;d.started=now;d.startPosition=Motion.idle(d.origin,d.born,now)
 d.model:SetAttribute('MagnetOrigin',d.startPosition);d.model:SetAttribute('MagnetStart',now);d.model:SetAttribute('MagnetUserId',p.UserId)
 return true
end
function H.step(now)
 if not inCombat() then if #H.drops>0 then H.clear() end;return end
 for i=#H.drops,1,-1 do
  local d=H.drops[i]
  if not d.model.Parent then remove(i)
  elseif d.target then
   local r=living(d.target)
   if not r or (r.Position-d.origin).Magnitude>100 then cancel(d)
   elseif now-d.started>=Motion.PULL_SECONDS then
    local _,h=living(d.target);local before=h.Health
    characters.heal(d.target,H.HEAL)
    d.model:SetAttribute('Healed',h.Health-before)
    remove(i)
   end
  else
   for _,p in Players:GetPlayers() do if H.collect(p,d) then break end end
  end
 end
end
Players.PlayerRemoving:Connect(function(p) for _,d in H.drops do if d.target==p then cancel(d) end end end)
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<1/30 then return end;elapsed=0;H.step(workspace:GetServerTimeNow())
end)
return H
