-- Server-only, idempotent death lifecycle. Effects never keep a corpse alive.
local combat=script.Parent
local Death={}
function Death.finish(npc)
 if not npc.Parent or npc:GetAttribute('DeathPopped') then return end
 npc:SetAttribute('DeathPopped',true)
 local root=npc:FindFirstChild('HumanoidRootPart')
 local position=root and root.Position or npc:GetPivot().Position
 combat.ZombiePopped:FireAllClients(position)
 game:GetService('CollectionService'):RemoveTag(npc,'RogueliteZombie')
 npc:Destroy()
end
return Death
