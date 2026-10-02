-- Lifetime Kills, Highest Wave and Time Played, shown on the three lobby leaderboards.
-- Server authority only. Kills come from the enemy-death hook (credited to LastDamageUserId, real runs only);
-- the wave counts once a player is alive in that wave's combat; time counts every second in the server.
-- Saved stats live in their own DataStore so ProfileService is untouched. Studio uses in-memory stats
-- unless Workspace attribute EnableStudioDataStores=true, so Studio play never reaches the real boards;
-- the boards then list the players in the test server.
-- Per map (plan J item 12, user 2026-10-02: "have the leaderboard cycle through all maps, and have one
-- for total too. Same with top kills"): kills and the highest wave are also kept per map, each with its
-- own ranking, and the Kills and Wave boards cycle every 8 s: ALL MAPS, then Pine Valley ... Volcanic
-- Crater. The totals are the same numbers as before. Time Played stays one board.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local DataStores=game:GetService('DataStoreService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local SSS=game:GetService('ServerScriptService')
local combat=RS:WaitForChild('RogueliteCombat')
local Shop=require(SSS:WaitForChild('ShopService')) -- run phase and membership
local Death=require(combat:WaitForChild('ZombieDeath'))
local Rules=require(RS:WaitForChild('RunSetupRules')) -- the maps, in unlock order
local runState=RS:WaitForChild('RogueliteRunState')
-- Test runs (the admin panel was used) record no kills or best waves. Time played still counts:
-- it measures time on the server, not a run result.
local Admin=require(combat:WaitForChild('AdminConfig'))

local STATS={
 {id='Kills',field='kills',mapField='mapKills'},
 {id='Wave',field='bestWave',mapField='mapWaves'},
 {id='Time',field='seconds'},
}
local MAPS={};for _,m in Rules.Maps do table.insert(MAPS,{id=m.id,name=m.name}) end
local TOP=10
local useStore=not RunService:IsStudio() or workspace:GetAttribute('EnableStudioDataStores')==true
local store=useStore and DataStores:GetDataStore('RogueliteLeaderboardStats_v1')
-- Rankings: 'Kills', 'Wave', 'Time' (the totals, as before) and 'Kills/<map>', 'Wave/<map>'.
local ordered={}
if useStore then
 for _,s in STATS do
  ordered[s.id]=DataStores:GetOrderedDataStore('RogueliteTop'..s.id..'_v1')
  if s.mapField then for _,m in MAPS do ordered[s.id..'/'..m.id]=DataStores:GetOrderedDataStore('RogueliteTop'..s.id..'_'..m.id..'_v1') end end
 end
end

-- data: this session's view of the totals (Studio boards read it). pending: kills and seconds
-- earned since the last save. committed: the record as last saved, which the rankings publish.
local data,pending,committed,written={},{},{},{}
local function fresh() return {kills=0,bestWave=0,seconds=0,mapKills={},mapWaves={}} end
local function key(p) return 'u_'..p.UserId end
local function runMap() local id=combat:GetAttribute('RunMap');return Rules.MapIndex[id] and id or 'PineValley' end
-- Best waves already in the player's save (ProfileBestWaves, 'PineValley:12,BeachCove/Hard:5') seed
-- the per-map highs, so the new boards don't start empty for players who already played.
local function seedWaves(p)
 local d=data[p];local text=p:GetAttribute('ProfileBestWaves')
 if not d or type(text)~='string' then return end
 for runKey,wave in string.gmatch(text,'([^,:]+):(%d+)') do
  local map=string.match(runKey,'^([^/]+)');local n=tonumber(wave) or 0
  if Rules.MapIndex[map] and n>(d.mapWaves[map] or 0) then d.mapWaves[map]=n;if n>d.bestWave then d.bestWave=n end end
 end
end

local function load(p)
 local d
 if store then
  for attempt=1,3 do
   local ok,result=pcall(store.GetAsync,store,key(p))
   if ok then d=result;break end
   warn('LeaderboardService: load failed',p.UserId,result);task.wait(attempt)
  end
 end
 -- A failed load still counts this session: saves add on top of whatever is stored.
 d=type(d)=='table' and d or fresh()
 for k,v in fresh() do if type(d[k])~=type(v) then d[k]=v end end
 if p.Parent then
  data[p]=d;pending[p]={kills=0,seconds=0,mapKills={}};written[p]={}
  seedWaves(p);p:GetAttributeChangedSignal('ProfileBestWaves'):Connect(function() seedWaves(p) end)
 end
end
-- Kills and time are added to the stored totals, never overwritten, so two servers holding the
-- same player (a quick rejoin) both count. The best waves keep the larger value.
local saving={}
local function save(p)
 local d,add=data[p],pending[p];if not store or not d then return end
 while saving[p] do task.wait() end
 saving[p]=true
 local kills,seconds=add.kills,math.floor(add.seconds)
 local mapKills=table.clone(add.mapKills);local mapWaves=table.clone(d.mapWaves)
 local ok,result=pcall(store.UpdateAsync,store,key(p),function(old)
  old=type(old)=='table' and old or {}
  local outKills,outWaves={},{}
  for id,v in type(old.mapKills)=='table' and old.mapKills or {} do outKills[id]=tonumber(v) or 0 end
  for id,v in mapKills do outKills[id]=(outKills[id] or 0)+v end
  for id,v in type(old.mapWaves)=='table' and old.mapWaves or {} do outWaves[id]=tonumber(v) or 0 end
  for id,v in mapWaves do outWaves[id]=math.max(outWaves[id] or 0,v) end
  return {kills=(tonumber(old.kills) or 0)+kills,bestWave=math.max(tonumber(old.bestWave) or 0,d.bestWave),seconds=(tonumber(old.seconds) or 0)+seconds,
   mapKills=outKills,mapWaves=outWaves}
 end)
 saving[p]=nil
 if not ok then warn('LeaderboardService: save failed',p.UserId,result);return end
 add.kills-=kills;add.seconds-=seconds
 for id,v in mapKills do add.mapKills[id]=(add.mapKills[id] or 0)-v;if add.mapKills[id]==0 then add.mapKills[id]=nil end end
 committed[p]=result
 -- Show the stored totals plus what is still unsaved.
 d.kills=result.kills+add.kills;d.seconds=result.seconds+add.seconds;d.bestWave=math.max(d.bestWave,result.bestWave)
 for id,v in result.mapKills do d.mapKills[id]=v+(add.mapKills[id] or 0) end
 for id,v in result.mapWaves do d.mapWaves[id]=math.max(d.mapWaves[id] or 0,v) end
end
-- Rankings publish saved totals only, and never lower a ranking another server wrote.
local function publish(p,rankingId,value)
 value=math.floor(value or 0)
 if value<=0 or written[p][rankingId]==value then return end
 local ok,err=pcall(ordered[rankingId].UpdateAsync,ordered[rankingId],key(p),function(old) return math.max(tonumber(old) or 0,value) end)
 if ok then written[p][rankingId]=value else warn('LeaderboardService: ranking write failed',rankingId,err) end
end
local function publishOrdered(p)
 local c=committed[p];if not store or not c or not written[p] then return end
 for _,s in STATS do
  publish(p,s.id,c[s.field])
  if s.mapField and type(c[s.mapField])=='table' then
   for _,m in MAPS do publish(p,s.id..'/'..m.id,c[s.mapField][m.id]) end
  end
 end
end

-- Kills --------------------------------------------------------------------------------
local function credit(npc)
 if Shop.phase~='Combat' or Admin.isTestRun(runState) or npc:GetAttribute('PracticeTarget') or npc:GetAttribute('KillCredited') then return end
 if not Tags:HasTag(npc,'RogueliteZombie') then return end
 local id=npc:GetAttribute('LastDamageUserId')
 local p=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
 if not p or not Shop.states[p] or not data[p] then return end
 npc:SetAttribute('KillCredited',true)
 local map=runMap()
 data[p].kills+=1;pending[p].kills+=1
 data[p].mapKills[map]=(data[p].mapKills[map] or 0)+1;pending[p].mapKills[map]=(pending[p].mapKills[map] or 0)+1
end
-- A listener alongside ShopService's drop handler (ZombieDeath keeps both).
Death.onDeath=function(npc)
 local ok,err=pcall(credit,npc);if not ok then warn('LeaderboardService: kill credit failed',err) end
end

-- Waves and time ------------------------------------------------------------------------
local function inRun(p)
 local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
 return Shop.isMember(p) and h~=nil and h.Health>0 and not p:GetAttribute('RunDown')
end
local last=os.clock()
task.spawn(function()
 while true do
  task.wait(1)
  local now=os.clock();local dt=math.min(now-last,5);last=now
  local wave=runState:GetAttribute('Phase')=='Combat' and (runState:GetAttribute('Wave') or 0) or 0
  local map=runMap()
  for p,d in data do
   d.seconds+=dt;pending[p].seconds+=dt
   if wave>0 and inRun(p) and not Admin.isTestRun(runState) then
    if wave>d.bestWave then d.bestWave=wave end
    if wave>(d.mapWaves[map] or 0) then d.mapWaves[map]=wave end
   end
  end
 end
end)

-- Boards ----------------------------------------------------------------------------------
local CREAM=Color3.fromRGB(246,234,204)
local AMBER=Color3.fromRGB(231,176,82)
local DIM=Color3.fromRGB(150,170,178)
local FONT=Font.new('rbxasset://fonts/families/GothamSSm.json',Enum.FontWeight.Bold)
local names={}
local function nameFor(userId)
 local p=Players:GetPlayerByUserId(userId);if p then names[userId]=p.Name;return p.Name end
 if names[userId] then return names[userId] end
 local ok,name=pcall(Players.GetNameFromUserIdAsync,Players,userId)
 names[userId]=ok and name or ('Player '..userId);return names[userId]
end
local function grouped(n)
 local s=tostring(math.floor(n));local out=s:reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (out:gsub('^,',''))
end
local FORMAT={
 Kills=grouped,
 Wave=function(n) return 'Wave '..math.floor(n) end,
 Time=function(n) local h=math.floor(n/3600);local m=math.floor(n%3600/60);return h>0 and string.format('%dh %02dm',h,m) or (m..'m') end,
}
-- What each board shows, in order: the Total, then every map (Kills and Wave); Time is one page.
local PAGES={Kills={{key='Total',name='ALL MAPS'}},Wave={{key='Total',name='ALL MAPS'}},Time={{key='Total',name=nil}}}
for _,m in MAPS do
 table.insert(PAGES.Kills,{key=m.id,name=string.upper(m.name)})
 table.insert(PAGES.Wave,{key=m.id,name=string.upper(m.name)})
end
local CYCLE=8 -- seconds each page stays up

local function label(parent,name,props)
 local l=Instance.new('TextLabel');l.Name=name;l.BackgroundTransparency=1;l.FontFace=FONT;l.TextColor3=CREAM
 l.TextScaled=true;l.TextXAlignment=Enum.TextXAlignment.Left
 for k,v in props do l[k]=v end
 l.Parent=parent;return l
end
-- One SurfaceGui per board, on the Display part in front of the painted blue panel (7.7 x 5.7 studs).
-- A cycling board keeps a header strip on top: which map it shows, and a dot per page.
local HEADER=58
local function ensureGui(display,cycling)
 local gui=display:FindFirstChild('Ranking')
 -- A board built before it cycled (no header) is rebuilt with one.
 if gui and cycling and not gui:FindFirstChild('Header') then gui:Destroy();gui=nil end
 if gui then return gui end
 gui=Instance.new('SurfaceGui');gui.Name='Ranking';gui.Face=Enum.NormalId.Back
 gui.SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud;gui.PixelsPerStud=100;gui.LightInfluence=0;gui.Brightness=1.1
 gui.MaxDistance=140;gui.ResetOnSpawn=false
 local top=cycling and HEADER or 0
 if cycling then
  local header=Instance.new('Frame');header.Name='Header';header.BackgroundTransparency=1
  header.Size=UDim2.new(1,-24,0,HEADER-6);header.Position=UDim2.fromOffset(12,6);header.Parent=gui
  label(header,'Page',{Size=UDim2.new(.62,0,.82,0),Position=UDim2.new(0,6,.09,0),TextColor3=AMBER})
  label(header,'Dots',{Size=UDim2.new(.36,0,.5,0),Position=UDim2.new(.64,0,.25,0),TextXAlignment=Enum.TextXAlignment.Right,TextColor3=DIM})
 end
 local list=Instance.new('Frame');list.Name='Rows';list.BackgroundTransparency=1
 list.Size=UDim2.new(1,-24,1,-16-top);list.Position=UDim2.fromOffset(12,8+top);list.Parent=gui
 local layout=Instance.new('UIListLayout');layout.SortOrder=Enum.SortOrder.LayoutOrder;layout.Parent=list
 for i=1,TOP do
  local row=Instance.new('Frame');row.Name='Row'..i;row.LayoutOrder=i;row.Size=UDim2.new(1,0,1/TOP,0)
  row.BackgroundColor3=Color3.fromRGB(12,34,47);row.BackgroundTransparency=i%2==0 and .55 or 1;row.BorderSizePixel=0;row.Parent=list
  Instance.new('UICorner',row).CornerRadius=UDim.new(0,8)
  -- Text fills ~80% of each row so names read from the spawn path.
  label(row,'Rank',{Text=tostring(i),Size=UDim2.new(0,58,.84,0),Position=UDim2.new(0,2,.08,0),TextXAlignment=Enum.TextXAlignment.Center,TextColor3=i<=3 and AMBER or DIM})
  local head=Instance.new('ImageLabel');head.Name='Headshot';head.BackgroundColor3=Color3.fromRGB(29,64,83);head.BorderSizePixel=0
  head.Size=UDim2.new(0,42,0,42);head.Position=UDim2.new(0,66,.5,-21);head.Parent=row
  Instance.new('UICorner',head).CornerRadius=UDim.new(1,0)
  label(row,'PlayerName',{Size=UDim2.new(1,-318,.8,0),Position=UDim2.new(0,120,.1,0)})
  label(row,'Value',{Size=UDim2.new(0,196,.8,0),Position=UDim2.new(1,-200,.1,0),TextXAlignment=Enum.TextXAlignment.Right,TextColor3=i<=3 and AMBER or CREAM})
 end
 gui.Parent=display;return gui
end
local function render(board,statId,pageIndex,entries)
 local display=board:FindFirstChild('Display');if not display then return end
 local pages=PAGES[statId];local cycling=#pages>1
 local gui=ensureGui(display,cycling)
 if cycling and gui:FindFirstChild('Header') then
  gui.Header.Page.Text=pages[pageIndex].name
  local dots={};for i=1,#pages do dots[i]=i==pageIndex and '●' or '○' end
  gui.Header.Dots.Text=table.concat(dots,' ')
 end
 local rows=gui.Rows
 for i=1,TOP do
  local row=rows['Row'..i];local e=entries and entries[i]
  row.PlayerName.Text=e and e.name or (i==1 and not entries and 'Loading...' or '—');row.PlayerName.TextColor3=e and CREAM or DIM
  row.Value.Text=e and FORMAT[statId](e.value) or ''
  row.Headshot.Image=e and string.format('rbxthumb://type=AvatarHeadShot&id=%d&w=48&h=48',e.userId) or ''
  row.Headshot.BackgroundTransparency=e and 0 or 1
 end
end

-- The top TOP of one ranking. Store reads are budgeted (OrderedDataStore GetSortedAsync allows about
-- 5 + 2 per player each minute), so the boards read one ranking every 12 s and show cached pages.
local function rankingId(statId,pageKey) return pageKey=='Total' and statId or statId..'/'..pageKey end
local function topFor(stat,pageKey)
 local entries={}
 if useStore then
  local ranking=ordered[rankingId(stat.id,pageKey)];if not ranking then return nil end
  local ok,pages=pcall(ranking.GetSortedAsync,ranking,false,TOP)
  if not ok then warn('LeaderboardService: ranking read failed',stat.id,pageKey,pages);return nil end
  for _,item in pages:GetCurrentPage() do
   local id=tonumber(string.match(item.key,'^u_(%d+)$'))
   if id and item.value>0 then table.insert(entries,{userId=id,value=item.value}) end
  end
 else
  for p,d in data do
   local value=math.floor(pageKey=='Total' and d[stat.field] or (d[stat.mapField] and d[stat.mapField][pageKey]) or 0)
   if value>0 or (stat.id=='Time' and pageKey=='Total') then table.insert(entries,{userId=p.UserId,value=value}) end
  end
  table.sort(entries,function(a,b) return a.value>b.value end)
  while #entries>TOP do table.remove(entries) end
 end
 for _,e in entries do e.name=nameFor(e.userId) end
 return entries
end
local cache={} -- rankingId -> {entries,at}
local function boardsByStat()
 local boards={}
 for _,board in Tags:GetTagged('RogueliteLeaderboard') do
  local id=board:GetAttribute('LeaderboardStat');if PAGES[id] and board:IsDescendantOf(workspace) then boards[id]=boards[id] or {};table.insert(boards[id],board) end
 end
 return boards
end
-- Read the stalest ranking a board here can show (one per call).
local function readOne()
 local boards=boardsByStat()
 local best,bestAt
 for _,stat in STATS do
  if boards[stat.id] then
   for _,page in PAGES[stat.id] do
    local id=rankingId(stat.id,page.key);local c=cache[id];local at=c and c.at or -math.huge
    if not best or at<bestAt then best,bestAt={stat=stat,page=page,id=id},at end
   end
  end
 end
 if not best then return end
 local entries=topFor(best.stat,best.page.key)
 if entries then cache[best.id]={entries=entries,at=os.clock()} end
end
local STAT={};for _,s in STATS do STAT[s.id]=s end
local page=0
local function show()
 page+=1
 for statId,list in boardsByStat() do
  local pages=PAGES[statId];local index=(page-1)%#pages+1
  -- Studio reads this server's players directly; live servers show the cached ranking.
  local entries
  if useStore then local c=cache[rankingId(statId,pages[index].key)];entries=c and c.entries
  else entries=topFor(STAT[statId],pages[index].key) end
  for _,board in list do render(board,statId,index,entries) end
 end
end

Players.PlayerAdded:Connect(load)
for _,p in Players:GetPlayers() do task.spawn(load,p) end
local function release(p)
 if not data[p] then return end
 save(p);publishOrdered(p)
 data[p]=nil;pending[p]=nil;committed[p]=nil;written[p]=nil
end
Players.PlayerRemoving:Connect(release)
game:BindToClose(function()
 local left=0
 for p in data do left+=1;task.spawn(function() release(p);left-=1 end) end
 local started=os.clock()
 while left>0 and os.clock()-started<25 do task.wait(.1) end
end)
task.spawn(function() while true do task.wait(120);for p in data do save(p) end end end)
-- Rankings: publish saved numbers every minute (match servers too); read one ranking every 12 s
-- (3 s in Studio, which reads this server's players); turn the cycling boards every 8 s.
task.spawn(function()
 while true do
  task.wait(useStore and 60 or 10)
  for p in data do local ok,err=pcall(publishOrdered,p);if not ok then warn('LeaderboardService: publish failed',err) end end
 end
end)
task.spawn(function()
 task.wait(2)
 while true do
  local ok,err=pcall(readOne);if not ok then warn('LeaderboardService: refresh failed',err) end
  task.wait(useStore and 12 or 3)
 end
end)
task.spawn(function()
 task.wait(3)
 while true do
  local ok,err=pcall(show);if not ok then warn('LeaderboardService: board update failed',err) end
  task.wait(CYCLE)
 end
end)
