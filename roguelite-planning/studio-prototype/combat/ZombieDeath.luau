-- Server-only, idempotent death lifecycle. Ordinary deaths never wait for hit flashes.
local combat=script.Parent
local Death={}
-- onDeath(npc, position) listeners: `Death.onDeath=fn` adds one (ShopService's drops, the
-- leaderboard's kill credit), so neither can replace the other whatever order they load in.
local deathListeners={}
setmetatable(Death,{__newindex=function(t,k,v) if k=='onDeath' then table.insert(deathListeners,v) else rawset(t,k,v) end end})
-- Practice targets soak hits: no death, rewards, lifesteal or status. Studio test
-- targets, plus the server-built lobby dummies (LobbyPracticeDummies) everywhere.
function Death.isPractice(npc)
 return npc:GetAttribute('PracticeTarget')==true and (game:GetService('RunService'):IsStudio() or npc:GetAttribute('LobbyDummy')==true)
end
function Death.finish(npc)
 if Death.isPractice(npc) then return end
 if not npc.Parent or npc:GetAttribute('DeathPopped') then return end
 local humanoid=npc:FindFirstChildOfClass('Humanoid')
 if not humanoid or humanoid.Health>0 then return end
 npc:SetAttribute('DeathPopped',true)
 local root=npc:FindFirstChild('HumanoidRootPart')
 local position=root and root.Position or npc:GetPivot().Position
 combat.ZombiePopped:FireAllClients(position)
 if not npc:GetAttribute('BossPractice') then
  for _,fn in deathListeners do local ok,err=pcall(fn,npc,position);if not ok then warn('ZombieDeath.onDeath listener failed:',err) end end
 end
 game:GetService('CollectionService'):RemoveTag(npc,'RogueliteZombie')
 if npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('IsMapBoss') then
  npc:SetAttribute('Attacking',false)
  npc:SetAttribute('BossDeathStart',workspace:GetServerTimeNow())
  if root then root.Anchored=true end
  humanoid.AutoRotate=false
  for _,p in npc:GetDescendants() do if p:IsA('BasePart') then p.CanCollide=false;p.CanTouch=false;p.CanQuery=false end end
  task.delay(npc:GetAttribute('BossDeathSeconds') or 2.9,function() if npc.Parent then npc:Destroy() end end)
  return
 end
 -- The position-only death burst and damage number outlive the model on the client.
 -- Do not freeze a corpse to keep a Highlight alive: lethal feedback must never delay removal.
 npc:Destroy()
end
return Death
