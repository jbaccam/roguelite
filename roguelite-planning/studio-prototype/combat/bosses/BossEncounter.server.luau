local RS=game:GetService('ReplicatedStorage')
local Role=require(script.Parent:WaitForChild('ServerRole'))
-- Lobby servers run no waves (ServerRole).
if Role.get()=='Lobby' then return end
local B=require(script.Parent:WaitForChild('BossService'))
local run=RS:WaitForChild('RogueliteRunState')
local combat=RS:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('BossMotion'))
local Maps=require(combat:WaitForChild('MapConfig'))
-- A map-boss module, or nil when this place lacks it or it fails to load. It never waits, so a
-- part-synced place still gets its wave-20 boss: the old Hammer needs none of them.
local function module(parent,name)
 local m=parent:FindFirstChild(name);if not m then return nil end
 local ok,v=pcall(require,m);if not ok then warn('BossEncounter: '..name..' failed to load: '..tostring(v)) end
 return ok and v or nil
end
-- 'Hammer' is the old BossService Hammer until this place can run the rebuilt Hammer Brute
-- (MapBossDefs.legacy: his def, timing, clips, template and runtime all here). A missing, failing or
-- older MapBossDefs keeps the old one.
local function oldHammer(Defs) local ok,old=pcall(function() return Defs.legacy('Hammer') end);return not (ok and old==false) end
-- Encounter selection is server-owned; no client spawn or damage remote.
local current,lastWave
local function update()
 local wave=run:GetAttribute('Wave');local active=combat:GetAttribute('ZombiesEnabled')==true
 if not active then current=nil;lastWave=nil;run:SetAttribute('BossAlive',false);return end
 if wave~=(combat:GetAttribute('HammerBossWave') or 20) or lastWave==wave then return end
 -- The map's boss (MapConfig): a MapBossDefs id; a map without one is won by clearing wave 20.
 local map=Maps.get(Role.activeMap());if not map or not map.boss then return end
 local marker=Role.marker();if not marker then return end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances={workspace:FindFirstChild('RogueliteEnemies'),marker}
 local p=marker.Position+Vector3.new(0,0,-15);local ground=workspace:Raycast(p+Vector3.yAxis*35,-Vector3.yAxis*100,params)
 if not ground then return end
 local Defs=module(combat,'MapBossDefs');current=nil
 if not (map.boss=='Hammer' and oldHammer(Defs)) then
  -- Wave bosses make their entrance (def.intro, where the def has one).
  local MB=module(script.Parent,'MapBossService');local okT,T=pcall(function() return Defs.timing(map.boss) end)
  if MB and okT and T then
   local ok,npc=pcall(MB.spawn,map.boss,CFrame.new(ground.Position+Vector3.yAxis*(T.rootHeight+.1)),false,{intro=true})
   if not ok then warn('BossEncounter: '..map.boss..' failed to spawn: '..tostring(npc)) end
   current=ok and npc or nil
  end
 end
 -- The old Hammer: while the rebuilt one isn't ready here, or when he failed to spawn.
 if not current and map.boss=='Hammer' then current=B.spawn(CFrame.new(ground.Position+Vector3.yAxis*(Motion.RootHeight+.1)),false) end
 if current then
  lastWave=wave;run:SetAttribute('BossAlive',true)
  current.Destroying:Connect(function() run:SetAttribute('BossAlive',false) end)
 end
end
combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(function() task.defer(update) end)
run:GetAttributeChangedSignal('Wave'):Connect(function() task.defer(update) end)
task.defer(update)
