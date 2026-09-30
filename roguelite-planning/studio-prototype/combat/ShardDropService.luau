-- Server owns one lightweight marker per death and credits only after magnetic arrival.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local E=require(combat.EconomyConfig)
local Motion=require(combat.ShardMotion)
local D={drops={}}
local characters,isCombat,award
local folder=Instance.new('Folder');folder.Name='RogueliteShardDrops';folder.Parent=workspace
local function living(p)
 local c=p and p.Character;local h=c and c:FindFirstChildOfClass('Humanoid');local r=c and c:FindFirstChild('HumanoidRootPart')
 return h and h.Health>0 and r
end
function D.configure(c,phase,credit) characters=c;isCombat=phase;award=credit end
local function remove(i) local d=table.remove(D.drops,i);if d then d.model:Destroy() end end
local function visible(p,from,to)
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 local exclude={p.Character,folder}
 local mobs=workspace:FindFirstChild('RogueliteEnemies');if mobs then table.insert(exclude,mobs) end
 params.FilterDescendantsInstances=exclude
 return not workspace:Raycast(from,to-from,params)
end
function D.collect(p,d)
 if not isCombat or not isCombat() or not d or d.collected or d.target or not d.model.Parent then return false end
 local now=workspace:GetServerTimeNow()
 if now-d.born<Motion.REST_SECONDS then return false end
 local r=living(p);local s=characters.states[p]
 if not r or not s or (d.owner and d.owner~=p) then return false end
 local radius=math.clamp(s.stats.PickupRadius or 0,0,100)
 if (r.Position-d.origin).Magnitude>radius or not visible(p,d.origin,r.Position) then return false end
 d.target=p;d.started=now
 d.startPosition=Motion.idle(d.origin,d.born,now)
 d.model:SetAttribute('MagnetOrigin',d.startPosition)
 d.model:SetAttribute('MagnetStart',now)
 d.model:SetAttribute('MagnetUserId',p.UserId)
 return true
end
local function cancel(d)
 d.target=nil;d.started=nil;d.position=d.origin
 d.model:SetAttribute('MagnetUserId',nil);d.model:SetAttribute('MagnetStart',nil)
end
function D.step(now)
 for i=#D.drops,1,-1 do
  local d=D.drops[i]
  if not d.model.Parent then remove(i)
  elseif isCombat and isCombat() then
   if d.target then
    local r=living(d.target)
    if not r or not characters.states[d.target] or (r.Position-d.origin).Magnitude>100 or not visible(d.target,d.position,r.Position) then cancel(d)
    else
     d.position=Motion.pull(d.startPosition,r.Position,now-d.started)
     if now-d.started>=Motion.PULL_SECONDS then
      d.collected=true
      if award(d.target,d.value,true) then remove(i) else d.collected=false;cancel(d) end
     end
    end
   elseif d.owner then D.collect(d.owner,d)
   else for _,p in Players:GetPlayers() do if D.collect(p,d) then break end end end
  end
 end
end
-- A defeated wave boss showers public crystals (anyone may collect) over a wide disc.
D.BOSS_DROPS=50;D.BOSS_DROP_VALUE=4
local function dropAt(at,owner,value,bonus)
 local model=Instance.new('Model');model.Name='CrystalShard'
 local root=Instance.new('Part');root.Name='ShardMarker';root.Size=Vector3.one*.1;root.Transparency=1
 root.Anchored=true;root.CanCollide=false;root.CanTouch=false;root.CanQuery=false;root.CastShadow=false
 root.CFrame=CFrame.new(at);root.Parent=model;model.PrimaryPart=root
 local born=workspace:GetServerTimeNow()
 model:SetAttribute('DesignerBonus',bonus)
 model:SetAttribute('Origin',at);model:SetAttribute('BornAt',born)
 model:SetAttribute('OwnerUserId',owner and owner.UserId or 0);model:SetAttribute('ShardValue',value);model.Parent=folder
 local d={model=model,position=at,origin=at,born=born,owner=owner,value=value,collected=false}
 table.insert(D.drops,d);return d
end
function D.spawn(npc,position)
 if npc:GetAttribute('PracticeTarget') then return end
 if not isCombat or not isCombat() or not Tags:HasTag(npc,'RogueliteZombie') or npc:GetAttribute('ShardDropped') then return end
 local h=npc:FindFirstChildOfClass('Humanoid');if not h or h.Health>0 then return end
 npc:SetAttribute('ShardDropped',true)
 local id=npc:GetAttribute('LastDamageUserId');local owner=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
 local exclude={folder,npc}
 local mobs=workspace:FindFirstChild('RogueliteEnemies');if mobs then table.insert(exclude,mobs) end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=exclude
 if npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('IsMapBoss') then
  local first
  for n=1,D.BOSS_DROPS do
   -- Golden-angle spiral: evenly filled disc, 3 to 14 studs from the body.
   local angle=n*2.39996;local radius=3+math.sqrt(n/D.BOSS_DROPS)*11
   local spot=position+Vector3.new(math.cos(angle)*radius,0,math.sin(angle)*radius)
   local ground=workspace:Raycast(spot+Vector3.new(0,6,0),Vector3.new(0,-100,0),params)
   local d=dropAt(ground and ground.Position+Vector3.new(0,1.15,0) or spot,nil,D.BOSS_DROP_VALUE,0)
   first=first or d
  end
  return first
 end
 local ground=workspace:Raycast(position+Vector3.new(0,2,0),Vector3.new(0,-100,0),params)
 local at=ground and ground.Position+Vector3.new(0,1.15,0) or position
 local value=E.KILL_SHARDS+(npc:GetAttribute('DesignerShirt')==true and E.DESIGNER_BONUS_SHARDS or 0)
 return dropAt(at,owner,value,value-E.KILL_SHARDS)
end
function D.clear(bank)
 for i=#D.drops,1,-1 do
  local d=D.drops[i]
  if bank and not d.collected then
   local owner=d.owner
   if not owner then
    local nearest=math.huge
    for _,p in Players:GetPlayers() do local root=living(p)
     if root and characters.states[p] then local distance=(root.Position-d.origin).Magnitude;if distance<nearest then nearest=distance;owner=p end end
    end
   end
   if owner then d.collected=true;award(owner,d.value,false) end
  end
  remove(i)
 end
end
Players.PlayerRemoving:Connect(function(p)
 for i=#D.drops,1,-1 do if D.drops[i].owner==p then remove(i) elseif D.drops[i].target==p then cancel(D.drops[i]) end end
end)
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<1/30 then return end;elapsed=0;D.step(workspace:GetServerTimeNow())
end)
return D
