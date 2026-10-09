-- Server only (unsandboxed, ServerScriptService; RogueliteZombieChase requires it): the Bloater's
-- burst (round 10, Pine Valley's POP GOES THE ZOMBIE). EnemyAttacks arms a Bloater beside a player
-- (FuseUntil, FuseCenter); ZombieDeath gives one killed before it armed a short fuse instead of
-- removing it. When the fuse runs out this bursts it, once:
--   players inside the disc (FuseCenter, Blast.radius, judged where their screen has them,
--     CharacterService.seen) take its damage through CharacterService.contact (armor, dodge, i-frames);
--   other enemies inside it take Blast.enemyDamage x that (friendly fire: lure crowds in). Kill credit
--     goes to the player who last hit the Bloater (its LastDamageUserId), so a chain pays the player
--     who started it; each enemy's own death still pays once (ZombieDeath). Bosses, leaders and event
--     objectives (coffins) are never hurt by it.
--   A Bloater caught in a burst is killed like any enemy, so it gets its own lethal fuse: a chain
--     ripples out with a readable gap instead of resolving in one frame. Blast.chainCap bursts a
--     frame at most; the others wait for the next frame.
-- Clients draw the swell, the ring and the burst from the attributes (Round10Events.client) and the
-- Round10FX 'Blast' event. Pausing the run (RunPaused) stops every fuse until it resumes.
local Players=game:GetService('Players')
local Run=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Types=require(combat:WaitForChild('ZombieTypes'))
local Characters=require(script.Parent:WaitForChild('CharacterService'))
local E={}
local Blast=Types.Blast
local fx=combat:FindFirstChild('Round10FX') or Instance.new('RemoteEvent')
fx.Name='Round10FX';fx.Parent=combat
local folder=workspace:WaitForChild('RogueliteEnemies')
local function flat(v) return Vector3.new(v.X,0,v.Z) end
-- Pure: true when `point` is inside the burst disc at `center` (radius, and Blast.height up or down).
function E.inside(center,radius,point)
 return math.abs(point.Y-center.Y)<=Blast.height and flat(point-center).Magnitude<=radius
end
local function burst(npc,now)
 if npc:GetAttribute('Detonated') then return end
 npc:SetAttribute('Detonated',now)
 local center=npc:GetAttribute('FuseCenter')
 if typeof(center)~='Vector3' then local r=npc:FindFirstChild('HumanoidRootPart');center=r and r.Position or npc:GetPivot().Position end
 local radius=Blast.radius*(npc:GetScale()/(npc:GetAttribute('EnemyBaselineModelScale') or 1))
 local damage=npc:GetAttribute('AttackDamage') or 20
 fx:FireAllClients('Blast',center,radius,npc)
 -- Players: their screen's position, the same rule as every enemy hit (enemy-hits-use-player-view).
 for _,player in Players:GetPlayers() do
  local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
  if root and Characters.states[player] then
   local at=Characters.seen(player,root) or root.Position
   if E.inside(center,radius,at) then Characters.contact(player,damage,nil,npc) end
  end
 end
 -- Enemies: ordinary arrivals and other Bloaters only.
 local owner=npc:GetAttribute('LastDamageUserId')
 for _,other in folder:GetChildren() do
  if other~=npc and not other:GetAttribute('IsBoss') and not other:GetAttribute('EventObjective') and not other:GetAttribute('DeathPopped') then
   local h=other:FindFirstChildOfClass('Humanoid');local r=other:FindFirstChild('HumanoidRootPart')
   if h and r and h.Health>0 and Tags:HasTag(other,'RogueliteZombie') and E.inside(center,radius,r.Position) then
    if type(owner)=='number' then other:SetAttribute('LastDamageUserId',owner);other:SetAttribute('LastWeaponId','Bloater') end
    h:TakeDamage(damage*Blast.enemyDamage)
   end
  end
 end
 -- Removal on the next frame: clients get Detonated (the burst) before the body goes.
 task.defer(function() if npc.Parent then npc:Destroy() end end)
end
local pausedAt
Run.Heartbeat:Connect(function()
 local now=workspace:GetServerTimeNow()
 -- A paused run holds every fuse: they resume with the time they had left.
 if combat:GetAttribute('RunPaused')==true then pausedAt=pausedAt or now;return end
 if pausedAt then
  local held=now-pausedAt;pausedAt=nil
  for _,npc in folder:GetChildren() do
   local fuse=npc:GetAttribute('FuseUntil')
   if npc:GetAttribute('Exploder') and type(fuse)=='number' and not npc:GetAttribute('Detonated') then npc:SetAttribute('FuseUntil',fuse+held) end
  end
  return
 end
 local done=0
 for _,npc in folder:GetChildren() do
  if done>=Blast.chainCap then break end
  local fuse=npc:GetAttribute('FuseUntil')
  if npc:GetAttribute('Exploder') and type(fuse)=='number' and now>=fuse and not npc:GetAttribute('Detonated') then
   done+=1
   local ok,err=pcall(burst,npc,now)
   if not ok then warn('ExploderService: burst failed: '..tostring(err));npc:SetAttribute('Detonated',now);npc:Destroy() end
  end
 end
end)
return E
