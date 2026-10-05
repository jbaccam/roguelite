-- Temporary Studio server Script only; deliberately excluded from Rojo projects.
-- Destructive to this in-memory test run. Stop Play to discard all fixtures.
assert(game:GetService('RunService'):IsStudio(), 'Studio only')
local H=game:GetService('HttpService')
local ok,result=xpcall(function()
 local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
 local S=require(game.ServerScriptService.ShopService)
 local R=require(game.ServerScriptService.ServerRole)
 local C=game.ReplicatedStorage.RogueliteCombat
 local run=game.ReplicatedStorage.RogueliteRunState
 while not S.states[p] or not p.Character or not p.Character:FindFirstChildOfClass('Humanoid') do task.wait() end
 p:SetAttribute('LobbyPreviewActive',false);p:SetAttribute('StudioArea','Arena')
 local spawn=assert(R.playerSpawn(),'Arena spawn missing')
 p.Character:PivotTo(spawn.CFrame+Vector3.yAxis*4);S.join(p)
 S.jumpToWave(2);C:SetAttribute('ZombiesEnabled',false);run:SetAttribute('AdminTestRun',true)
 local state=S.states[p];state.pendingLevels=2;state.upgradeOffers={};S.publish(p)
 local slot=C.PlayerStates[tostring(p.UserId)].Slot1;local weapon=slot:GetAttribute('WeaponId')
 p.Character.Humanoid.Health=0;task.wait(.3)
 assert(p:GetAttribute('RunDown')==true,'Death did not mark player down')
 assert(S.finishWave(),'Wave did not finish')
 local deadline=os.clock()+12
 repeat task.wait(.1) until os.clock()>deadline or (not p:GetAttribute('RunDown') and not p:GetAttribute('RunReturning') and p.Character and p.Character:FindFirstChildOfClass('Humanoid') and p.Character.Humanoid.Health>0)
 local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
 assert(h and h.Health==h.MaxHealth,'Not revived at full health')
 assert(not p:GetAttribute('RunDown') and not p:GetAttribute('RunReturning'),'Death/return flags stuck')
 assert(slot:GetAttribute('WeaponId')==weapon,'Build lost')
 assert(state.pendingLevels==2 and #state.upgradeOffers==4,'Banked upgrades lost')
 assert(S.phase=='Shop','Next combat skipped the recovering player')
 -- The old all-dead timer must not defeat a newly revived player ten seconds later.
 task.wait(11)
 assert(S.isMember(p) and not p:GetAttribute('RunResult'),'Stale last-stand timer ended the revived run')
 assert(p.Character==h.Parent and h.Health>0,'Revived body lost after the old timeout')
 return {passed=true,checks=9,health=h.Health,pending=state.pendingLevels,offers=#state.upgradeOffers,weapon=weapon,phase=S.phase}
end,debug.traceback)
script:SetAttribute('Result',H:JSONEncode({ok=ok,result=result}))
