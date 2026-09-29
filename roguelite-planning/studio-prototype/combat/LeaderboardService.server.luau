-- Lifetime Kills, Highest Wave and Time Played, shown on the three lobby leaderboards.
-- Server authority only. Kills come from the enemy-death hook (credited to LastDamageUserId, real runs only);
-- the wave counts once a player is alive in that wave's combat; time counts every second in the server.
-- Saved stats live in their own DataStore so ProfileService is untouched. Studio uses in-memory stats
-- unless Workspace attribute EnableStudioDataStores=true, so Studio play never reaches the real boards;
-- the boards then list the players in the test server.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local DataStores=game:GetService('DataStoreService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local SSS=game:GetService('ServerScriptService')
local combat=RS:WaitForChild('RogueliteCombat')
local Shop=require(SSS:WaitForChild('ShopService')) -- sets ZombieDeath.onDeath, which is wrapped below
local Death=require(combat:WaitForChild('ZombieDeath'))
local runState=RS:WaitForChild('RogueliteRunState')
-- Test runs (the admin panel was used) record no kills or best waves. Time played still counts:
-- it measures time on the server, not a run result.
local Admin=require(combat:WaitForChild('AdminConfig'))

local STATS={
 {id='Kills',field='kills'},
 {id='Wave',field='bestWave'},
 {id='Time',field='seconds'},
}
local TOP=10
local useStore=not RunService:IsStudio() or workspace:GetAttribute('EnableStudioDataStores')==true
local REFRESH=useStore and 60 or 3
local store=useStore and DataStores:GetDataStore('RogueliteLeaderboardStats_v1')
local ordered={}
if useStore then for _,s in STATS do ordered[s.id]=DataStores:GetOrderedDataStore('RogueliteTop'..s.id..'_v1') end end

local data,loaded,written={},{},{}
local function fresh() return {kills=0,bestWave=0,seconds=0} end
local function key(p) return 'u_'..p.UserId end

local function load(p)
 local d
 if store then
  for attempt=1,3 do
   local ok,result=pcall(store.GetAsync,store,key(p))
   if ok then d=result or fresh();loaded[p]=true;break end
   warn('LeaderboardService: load failed',p.UserId,result);task.wait(attempt)
  end
 else loaded[p]=true end
 d=d or fresh() -- a failed load still counts this session but is never saved over the unknown record
 for k,v in fresh() do if type(d[k])~='number' then d[k]=v end end
 if p.Parent then data[p]=d;written[p]={} end
end
-- Values only grow, so a stale server can never lower a saved record.
local function save(p)
 local d=data[p];if not store or not d or not loaded[p] then return end
 local ok,err=pcall(store.UpdateAsync,store,key(p),function(old)
  old=type(old)=='table' and old or {}
  return {kills=math.max(old.kills or 0,d.kills),bestWave=math.max(old.bestWave or 0,d.bestWave),seconds=math.max(old.seconds or 0,math.floor(d.seconds))}
 end)
 if not ok then warn('LeaderboardService: save failed',p.UserId,err) end
end
local function publishOrdered(p)
 local d=data[p];if not store or not d or not loaded[p] then return end
 for _,s in STATS do
  local value=math.floor(d[s.field])
  if value>0 and written[p][s.id]~=value then
   local ok,err=pcall(ordered[s.id].SetAsync,ordered[s.id],key(p),value)
   if ok then written[p][s.id]=value else warn('LeaderboardService: ranking write failed',s.id,err) end
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
 data[p].kills+=1
end
local previousDeath=Death.onDeath
Death.onDeath=function(npc,position)
 local ok,err=pcall(credit,npc);if not ok then warn('LeaderboardService: kill credit failed',err) end
 if previousDeath then previousDeath(npc,position) end
end

-- Waves and time ------------------------------------------------------------------------
local function inRun(p)
 local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
 return Shop.states[p]~=nil and h~=nil and h.Health>0 and not p:GetAttribute('RunDown') and not p:GetAttribute('LobbyPreviewActive')
end
local last=os.clock()
task.spawn(function()
 while true do
  task.wait(1)
  local now=os.clock();local dt=math.min(now-last,5);last=now
  local wave=runState:GetAttribute('Phase')=='Combat' and (runState:GetAttribute('Wave') or 0) or 0
  for p,d in data do
   d.seconds+=dt
   if wave>d.bestWave and inRun(p) and not Admin.isTestRun(runState) then d.bestWave=wave end
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

local function label(parent,name,props)
 local l=Instance.new('TextLabel');l.Name=name;l.BackgroundTransparency=1;l.FontFace=FONT;l.TextColor3=CREAM
 l.TextScaled=true;l.TextXAlignment=Enum.TextXAlignment.Left
 for k,v in props do l[k]=v end
 l.Parent=parent;return l
end
-- One SurfaceGui per board, on the Display part in front of the painted blue panel (7.7 x 5.7 studs).
local function ensureGui(display)
 local gui=display:FindFirstChild('Ranking');if gui then return gui end
 gui=Instance.new('SurfaceGui');gui.Name='Ranking';gui.Face=Enum.NormalId.Back
 gui.SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud;gui.PixelsPerStud=100;gui.LightInfluence=0;gui.Brightness=1.1
 gui.MaxDistance=140;gui.ResetOnSpawn=false
 local list=Instance.new('Frame');list.Name='Rows';list.BackgroundTransparency=1
 list.Size=UDim2.new(1,-36,1,-30);list.Position=UDim2.fromOffset(18,15);list.Parent=gui
 local layout=Instance.new('UIListLayout');layout.SortOrder=Enum.SortOrder.LayoutOrder;layout.Parent=list
 for i=1,TOP do
  local row=Instance.new('Frame');row.Name='Row'..i;row.LayoutOrder=i;row.Size=UDim2.new(1,0,1/TOP,0)
  row.BackgroundColor3=Color3.fromRGB(12,34,47);row.BackgroundTransparency=i%2==0 and .55 or 1;row.BorderSizePixel=0;row.Parent=list
  Instance.new('UICorner',row).CornerRadius=UDim.new(0,8)
  label(row,'Rank',{Text=tostring(i),Size=UDim2.new(0,62,.62,0),Position=UDim2.new(0,4,.19,0),TextXAlignment=Enum.TextXAlignment.Center,TextColor3=i<=3 and AMBER or DIM})
  local head=Instance.new('ImageLabel');head.Name='Headshot';head.BackgroundColor3=Color3.fromRGB(29,64,83);head.BorderSizePixel=0
  head.Size=UDim2.new(0,40,0,40);head.Position=UDim2.new(0,72,.5,-20);head.Parent=row
  Instance.new('UICorner',head).CornerRadius=UDim.new(1,0)
  label(row,'PlayerName',{Size=UDim2.new(1,-330,.56,0),Position=UDim2.new(0,124,.22,0)})
  label(row,'Value',{Size=UDim2.new(0,190,.56,0),Position=UDim2.new(1,-196,.22,0),TextXAlignment=Enum.TextXAlignment.Right,TextColor3=i<=3 and AMBER or CREAM})
 end
 gui.Parent=display;return gui
end
local function render(board,statId,entries)
 local display=board:FindFirstChild('Display');if not display then return end
 local rows=ensureGui(display).Rows
 for i=1,TOP do
  local row=rows['Row'..i];local e=entries[i]
  row.PlayerName.Text=e and e.name or '—';row.PlayerName.TextColor3=e and CREAM or DIM
  row.Value.Text=e and FORMAT[statId](e.value) or ''
  row.Headshot.Image=e and string.format('rbxthumb://type=AvatarHeadShot&id=%d&w=48&h=48',e.userId) or ''
  row.Headshot.BackgroundTransparency=e and 0 or 1
 end
end

local function topFor(stat)
 local entries={}
 if useStore then
  local ok,pages=pcall(ordered[stat.id].GetSortedAsync,ordered[stat.id],false,TOP)
  if not ok then warn('LeaderboardService: ranking read failed',stat.id,pages);return nil end
  for _,item in pages:GetCurrentPage() do
   local id=tonumber(string.match(item.key,'^u_(%d+)$'))
   if id and item.value>0 then table.insert(entries,{userId=id,value=item.value}) end
  end
 else
  for p,d in data do
   local value=math.floor(d[stat.field])
   if value>0 or stat.id=='Time' then table.insert(entries,{userId=p.UserId,value=value}) end
  end
  table.sort(entries,function(a,b) return a.value>b.value end)
  while #entries>TOP do table.remove(entries) end
 end
 for _,e in entries do e.name=nameFor(e.userId) end
 return entries
end
local function refresh()
 for p in data do publishOrdered(p) end
 local boards={}
 for _,board in Tags:GetTagged('RogueliteLeaderboard') do
  local id=board:GetAttribute('LeaderboardStat');if id and board:IsDescendantOf(workspace) then boards[id]=boards[id] or {};table.insert(boards[id],board) end
 end
 for _,stat in STATS do
  if boards[stat.id] then
   local entries=topFor(stat)
   if entries then for _,board in boards[stat.id] do render(board,stat.id,entries) end end
  end
 end
end

Players.PlayerAdded:Connect(load)
for _,p in Players:GetPlayers() do task.spawn(load,p) end
Players.PlayerRemoving:Connect(function(p) publishOrdered(p);save(p);data[p]=nil;loaded[p]=nil;written[p]=nil end)
game:BindToClose(function() for p in data do publishOrdered(p);save(p) end end)
task.spawn(function() while true do task.wait(120);for p in data do save(p) end end end)
task.spawn(function()
 task.wait(2)
 while true do
  local ok,err=pcall(refresh);if not ok then warn('LeaderboardService: refresh failed',err) end
  task.wait(REFRESH)
 end
end)
