-- Edit-time helper for this place's experimental script sandbox, after source sync.
assert(not game:GetService('RunService'):IsRunning(),'Stop Play first')
local c=game.ReplicatedStorage.RogueliteCombat
for _,name in {'RolledShirtVisual','RolledShirtData','TeeTorsoData','TeeSleeveData','DesignerShirtVisual','ShirtVisuals'} do
 local m=c[name];m.Sandboxed=c.ShardMotion.Sandboxed;m.Capabilities=c.ShardMotion.Capabilities
end
local server=game.ServerScriptService
server.MobCollision.Sandboxed=server.RogueliteCombat.Sandboxed
server.MobCollision.Capabilities=server.RogueliteCombat.Capabilities
-- Optional mesh presentation requires both this capability and the experience's
-- EditableMesh API setting. Default triangle presentation needs neither.
for _,m in {c.RolledShirtVisual,c.DesignerShirtVisual,c.ShirtVisuals,game.StarterPlayer.StarterPlayerScripts.RogueliteCombat} do
 m.Capabilities=m.Capabilities:Add(Enum.SecurityCapability.DynamicGeneration)
end
return 'Designer cloth script capabilities synchronized'
