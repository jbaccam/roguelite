-- Guarded source-only sync; never replaces the map or templates. Run from Studio MCP Edit.
return function(base, manifestPath, dryRun)
 assert(game.PlaceId == 107877054949326, 'Wrong place: Wavebreaker only')
 assert(not game:GetService('RunService'):IsRunning(), 'Stop Play before source sync')
 local H=game:GetService('HttpService')
 local function get(path) return (H:GetAsync(base..path..'?t='..os.clock(),true):gsub('\r\n','\n')) end
 local function resolve(path)
  local parts=string.split(path,'.');local at=game:GetService(parts[1])
  for i=2,#parts do at=at and at:FindFirstChild(parts[i]) end
  return at
 end
 local manifest=H:JSONDecode(get(manifestPath));local plan={}
 for _,e in manifest.scripts do
  local inst=assert(resolve(e.studio),'Missing '..e.studio)
  assert(inst.ClassName==e.class,'Wrong class: '..e.studio)
  local source=get(e.repo);local fn,err=loadstring(source,'='..e.repo)
  assert(fn,err)
  local current=inst.Source:gsub('\r\n','\n')
  assert(current==source or current==get(e.guard),'Studio changed since backup: '..e.studio)
  table.insert(plan,{inst=inst,source=source,changed=current~=source})
 end
 if not dryRun then
  game:GetService('ChangeHistoryService'):SetWaypoint('Before reported bug fixes')
  for _,e in plan do if e.changed then e.inst.Source=e.source end end
  game:GetService('ChangeHistoryService'):SetWaypoint('After reported bug fixes')
 end
 local changed=0;for _,e in plan do if e.changed then changed+=1 end end
 return {validated=#plan,changed=changed,dryRun=dryRun==true,placeId=game.PlaceId}
end
