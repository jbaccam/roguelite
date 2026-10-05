-- Source-only Studio Edit integration, with backups and optimistic concurrency checks.
-- Existing map/models/properties are untouched. New scripts inherit capabilities explicitly.
return function(base,manifestPath,backupName)
 assert(game.PlaceId==107877054949326,'Wavebreaker only')
 assert(not game:GetService('RunService'):IsRunning(),'Stop Play before syncing')
 local H=game:GetService('HttpService')
 local function get(path) return H:GetAsync(base..path..'?t='..os.clock(),true):gsub('\r\n','\n') end
 local function resolve(path)
  local parts=string.split(path,'.');local v=game:GetService(parts[1])
  for i=2,#parts do v=v and v:FindFirstChild(parts[i]) end
  return v
 end
 local plan={};local made,changed=0,0
 for _,e in H:JSONDecode(get(manifestPath)).scripts do
  local source=get(e.repo);assert(loadstring(source,'='..e.repo))
  local inst=resolve(e.studio);local before=inst and inst.Source
  if inst then assert(inst.ClassName==e.class,'Wrong class '..e.studio) end
  local parentPath,name=e.studio:match('^(.*)%.([^%.]+)$')
  local parent=assert(resolve(parentPath),'Missing parent '..parentPath)
  local inherit=not inst and assert(e.inherit and resolve(e.inherit),'Missing capability reference '..e.studio)
  if not inst or before:gsub('\r\n','\n')~=source then
   H:PostAsync(base..'dump/'..backupName..'-'..e.studio:gsub('%.','_'),H:JSONEncode({studio=e.studio,repo=e.repo,class=e.class,source=before,created=inst==nil}),Enum.HttpContentType.ApplicationJson)
   table.insert(plan,{inst=inst,before=before,source=source,parent=parent,name=name,class=e.class,inherit=inherit})
  end
 end
 for _,e in plan do assert(not e.inst or e.inst.Source==e.before,'Source changed during sync '..e.name) end
 game:GetService('ChangeHistoryService'):SetWaypoint('Before '..backupName)
 for _,e in plan do
  local inst=e.inst
  if not inst then
   inst=Instance.new(e.class);inst.Name=e.name;inst.Sandboxed=e.inherit.Sandboxed;inst.Capabilities=e.inherit.Capabilities
   inst.Source=e.source;inst.Parent=e.parent;made+=1
  else inst.Source=e.source;changed+=1 end
  assert(inst.Source:gsub('\r\n','\n')==e.source,'Sync mismatch '..e.name)
 end
 game:GetService('ChangeHistoryService'):SetWaypoint('After '..backupName)
 return {changed=changed,created=made}
end
