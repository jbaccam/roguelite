-- Manual Studio Client fixture, deliberately excluded from the shipping overlay.
-- Use in an idle scene. Temporary cosmetic effects only; no remotes/rewards.
return function()
 local Run=game:GetService('RunService')
 assert(Run:IsStudio() and Run:IsClient(),'Studio Client only')
 local player=game.Players.LocalPlayer
 local previous=player:GetAttribute('Setting_VisualQuality')
 local K=require(game.ReplicatedStorage.RogueliteCombat.VfxKit)
 local folder=Instance.new('Folder');folder.Name='ClientPerformanceQA';folder.Parent=workspace
 local results={}
 local ok,err=pcall(function()
  for _,mode in {'Full','Low'} do
   player:SetAttribute('Setting_VisualQuality',mode);task.wait(.1)
   local camera=assert(workspace.CurrentCamera)
   local position=camera.CFrame.Position+camera.CFrame.LookVector*8
   for _=1,100 do
    K.cloud(folder,position,Color3.new(1,1,1),2,.3)
    K.flash(folder,position,Color3.new(1,1,1),10,2,.2)
    K.shards(folder,position,Color3.new(1,1,1),12,2,.3)
   end
   local peak=#folder:GetChildren();task.wait(.5)
   results[mode]={peak=peak,remaining=#folder:GetChildren()}
   assert(results[mode].remaining==0,'Effect cleanup failed')
  end
 end)
 player:SetAttribute('Setting_VisualQuality',previous);folder:Destroy()
 assert(ok,err)
 return results
end
