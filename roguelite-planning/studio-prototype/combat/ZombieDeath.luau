-- Server-only, idempotent death lifecycle. Effects never keep a corpse alive.
local combat=script.Parent
local Death={}
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
 if Death.onDeath and not npc:GetAttribute('BossPractice') then Death.onDeath(npc,position) end
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
 npc:Destroy()
end
return Death
