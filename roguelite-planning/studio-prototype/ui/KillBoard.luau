-- In-run kill board (play-tester request 2026-10-10: "Kill leaderboard for when playing with friends
-- in-game would be cool"). Presentation only: every number is the server's.
--   Data: each run member's Player attribute RunKills, which RogueliteMeta already publishes (the
--   pause screen's Kills). The server credits a kill to the enemy's LastDamageUserId (the killing
--   blow's owner, set by CombatEffectsService), so pets and the Handyman's turret count for their
--   owner and a Bloater chain for whoever hit the Bloater. Combat only, and none in a run where the
--   admin panel was used (TEST RUN); it resets each stint (a new join starts at 0). No new remotes.
--   Shown in every run, solo too (one row: you; user, 2026-10-10: "show for single players too").
--   Hidden in the lobby, once this player's run has ended, in the tutorial run (Eggbert's guide
--   box takes a free edge spot there, and the guide and the HUD must never cover each other), and
--   while Settings > Kill board is OFF (Setting_KillBoard=false; default ON, saved with the
--   profile like the other settings; the board hides and returns at once when it is toggled).
--   Rows: rank, headshot, display name, kills; you are the lime row. Ties share a rank (5, 5, 3 kills
--   -> 1, 1, 3). At most MAX rows: with more members, the last row is yours if you are lower.
--   Updates twice a second, and only redraws when a row changed.
--   Placement (place below): in the HUD frame, sized by the HUD's own scale. Desktops and tablets:
--   the left edge under the health block (under the chat window when that is in the way, else the
--   bottom-left corner). Phones (the thumbstick owns their lower left): a compact board without names
--   on the right under the weapon strip, left of PAUSE/SETTINGS and above DASH. It never touches the
--   health block, timer, build strip, menu, boss bar, round 10 panel, chat window, DASH or the touch
--   controls; the toasts and round 10 panel keep the top centre. Mockup:
--   previews/kill-leaderboard-mockup/index.html.
-- Pure functions first (KillBoardTests runs them with luau.exe); mount() is the Roblox part.
local K={}
-- Design pixels at HUD scale 1.
K.W=260;K.PAD=8;K.HEAD=28;K.ROW=30;K.GAP=4;K.MAX=4
function K.height(n) n=math.max(1,n);return K.PAD+K.HEAD+n*K.ROW+(n-1)*K.GAP+K.PAD end

-- entries: {userId, name, kills}. Returns copies sorted by kills (then name, then id), each with
-- rank (ties share one: 5, 5, 3 -> 1, 1, 3) and mine (the local player).
function K.rank(entries,localId)
 local list={}
 for _,e in entries do table.insert(list,{userId=e.userId,name=tostring(e.name or ''),kills=math.max(0,math.floor(tonumber(e.kills) or 0))}) end
 table.sort(list,function(a,b)
  if a.kills~=b.kills then return a.kills>b.kills end
  if a.name~=b.name then return a.name<b.name end
  return (a.userId or 0)<(b.userId or 0)
 end)
 for i,e in list do
  e.rank=(i>1 and list[i-1].kills==e.kills) and list[i-1].rank or i
  e.mine=e.userId==localId
 end
 return list
end
-- The rows to draw: the top `max`; if you are below them, your row replaces the last one.
function K.rows(ranked,max)
 max=max or K.MAX
 local out={}
 for i=1,math.min(max,#ranked) do out[i]=ranked[i] end
 if #ranked>max then
  local shown=false;for _,e in out do if e.mine then shown=true end end
  if not shown then for _,e in ranked do if e.mine then out[max]=e;break end end end
 end
 return out
end
-- 999 -> "999", 1234 -> "1,234", 12345 -> "12.3K", 10000 -> "10K", 1290000 -> "1.2M" (rounded
-- down, so it never shows more kills than there are).
function K.format(n)
 n=math.max(0,math.floor(tonumber(n) or 0))
 local function short(v,suffix) local s=string.format('%.1f',math.floor(v*10)/10);s=s:gsub('%.0$','');return s..suffix end
 if n>=1e6 then return short(n/1e6,'M') end
 if n>=1e4 then return short(n/1e3,'K') end
 local s=tostring(n):reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (s:gsub('^,',''))
end
-- enabled: Setting_KillBoard (nil = the default, ON); tutorial: RogueliteCombat.TutorialRun.
function K.visible(members,isMember,ended,enabled,tutorial)
 return isMember==true and ended~=true and members>=1 and enabled~=false and tutorial~=true
end
-- What a row's look depends on, so an unchanged board is not redrawn.
function K.signature(rows)
 local parts={}
 for i,e in rows do parts[i]=tostring(e.userId)..':'..e.kills..':'..e.rank..':'..(e.mine and 1 or 0)..':'..e.name end
 return table.concat(parts,'|')
end

-- Rects are {x0,y0,x1,y1} in HUD-frame pixels.
local function overlaps(a,b,gap) return math.min(a[3],b[3])-math.max(a[1],b[1])>-gap and math.min(a[4],b[4])-math.max(a[2],b[2])>-gap end
K.overlaps=overlaps
-- Where the board goes on a w x h HUD at HUD scale s with n rows (user, 2026-10-10: "On PC it should
-- definitely be on the left"). hud: health, build (down to the three item rows it reserves), menu
-- and chat (optional) and blocks: every rect it must not touch (health, timer, build strip, menu,
-- boss bar, round 10 panel, chat window, DASH button, touch thumbstick and jump button).
-- compact (small screens): no names, 128 wide. Tries the first spot clear of every block, each
-- side at the HUD scale, then .85 and .7 of it (never below .5), the left side first:
--   1. left edge, under the health block (desktops, tablets);
--   2. left edge, under the chat window (keyboard screens put it centre left in a run);
--   3. bottom-left corner;
--   4. right side under the build strip, sliding left past the PAUSE/SETTINGS row and DASH but
--      never into the middle of the screen; then the same under the menu row. Phones end up here:
--      their left side below the health block is the thumbstick.
-- Returns x0, y0, scale, clear (false: nowhere clear, e.g. a 667 px phone while the boss bar sits
-- bottom centre; the board hides).
-- Examples: 1920 x 1022 desktop -> x 12..272 under the health block (solo y 256..330, 2 players
-- y 256..364) or under
-- the chat window when the health spot would touch it; 750 x 311 phone, compact at .55 -> x 537..607,
-- y 137.5..197 (2 players), left of PAUSE/SETTINGS and above DASH.
K.WC=128
function K.width(compact) return compact and K.WC or K.W end
function K.place(w,h,s,hud,n,compact)
 local function clear(r)
  if r[1]<0 or r[2]<0 or r[3]>w or r[4]>h-8 then return false end
  for _,b in hud.blocks do if overlaps(r,b,2) then return false end end
  return true
 end
 -- Scales to try: the HUD's, then .85 and .7 of it, never below half size (phones stay at .55).
 local scales={s};for _,k in {.85,.7} do if s*k>=.5 then table.insert(scales,s*k) end end
 for _,sc in scales do
  local bw,bh=K.width(compact)*sc,K.height(n)*sc
  local lefts={}
  if hud.health then table.insert(lefts,hud.health[4]+10) end
  if hud.chat then table.insert(lefts,hud.chat[4]+10) end
  table.insert(lefts,h-12-bh)
  for _,y0 in lefts do if clear({12,y0,12+bw,y0+bh}) then return 12,y0,sc,true end end
 end
 for _,sc in scales do
  local bw,bh=K.width(compact)*sc,K.height(n)*sc
  local tops={hud.build[4]+10}
  if hud.menu then table.insert(tops,hud.menu[4]+8) end
  for _,y0 in tops do
   local x1=w-12
   for _=1,8 do
    local r={x1-bw,y0,x1,y0+bh}
    if r[4]>h-8 or r[1]<w*.5+60*sc then break end
    local hit;for _,b in hud.blocks do if overlaps(r,b,2) then hit=b;break end end
    if not hit then return r[1],r[2],sc,true end
    x1=hit[1]-8
   end
  end
 end
 return 12,0,s,false
end

-- Roblox ---------------------------------------------------------------------------------------
function K.mount(player)
 local Players=game:GetService('Players')
 local RS=game:GetService('ReplicatedStorage')
 local Input=game:GetService('UserInputService')
 local RunService=game:GetService('RunService')
 local T=require(RS:WaitForChild('UITheme'))
 local C=T.Color
 local playerGui=player:WaitForChild('PlayerGui')
 local studio=RunService:IsStudio()
 local view -- the built board, inside the HUD frame
 local lastSignature,lastScale

 local function readable(base,scale) return math.max(base,math.ceil(10/scale)) end
 local function build(hud)
  local root=T.make('Frame',hud,{Name='KillBoard',BackgroundTransparency=1,BorderSizePixel=0,Active=false,Visible=false,Size=UDim2.fromOffset(K.W,K.height(2))})
  local scale=T.make('UIScale',root,{Scale=1})
  local plate=T.panel(root,'Plate',0,0,0,0,'panel');plate.Size=UDim2.fromScale(1,1)
  local title=T.label(root,'Title','KILLS',K.PAD+6,K.PAD-1,K.W-2*K.PAD-12,K.HEAD-2,18,C.cream);title.TextXAlignment=Enum.TextXAlignment.Left
  local rw=K.W-2*K.PAD
  local rows={}
  for i=1,K.MAX do
   local row=T.make('Frame',root,{Name='Row'..i,Position=UDim2.fromOffset(K.PAD,K.PAD+K.HEAD+(i-1)*(K.ROW+K.GAP)),Size=UDim2.fromOffset(rw,K.ROW),BackgroundColor3=C.well,BackgroundTransparency=.1,BorderSizePixel=0,Visible=false})
   T.make('UICorner',row,{CornerRadius=UDim.new(0,6)})
   local stroke=T.make('UIStroke',row,{Color=C.lime,Thickness=2,Enabled=false})
   local rank=T.label(row,'Rank','',2,0,22,K.ROW,17,C.muted)
   local head=T.make('ImageLabel',row,{Name='Headshot',BackgroundColor3=C.track,BorderSizePixel=0,Position=UDim2.fromOffset(28,3),Size=UDim2.fromOffset(24,24),Image=''})
   T.make('UICorner',head,{CornerRadius=UDim.new(1,0)})
   local name=T.make('TextLabel',row,{Name='PlayerName',BackgroundTransparency=1,Position=UDim2.fromOffset(58,0),Size=UDim2.fromOffset(rw-58-56,K.ROW),Text='',Font=T.Font,TextSize=17,
    TextColor3=C.white,TextXAlignment=Enum.TextXAlignment.Left,TextTruncate=Enum.TextTruncate.AtEnd,TextWrapped=false,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=.12})
   local kills=T.label(row,'Kills','',rw-54,0,50,K.ROW,19,C.white);kills.TextXAlignment=Enum.TextXAlignment.Right
   rows[i]={row=row,stroke=stroke,rank=rank,head=head,name=name,kills=kills}
  end
  return {root=root,scale=scale,title=title,rows=rows,count=2}
 end
 -- Compact (small screens): 128 wide, no names; rank, headshot, kills.
 local function setCompact(compact)
  view.compact=compact
  local width=K.width(compact);local rw=width-2*K.PAD
  view.root.Size=UDim2.fromOffset(width,K.height(view.count))
  view.title.Size=UDim2.fromOffset(width-2*K.PAD-12,K.HEAD-2)
  for _,r in view.rows do
   r.row.Size=UDim2.fromOffset(rw,K.ROW);r.name.Visible=not compact
   r.name.Size=UDim2.fromOffset(rw-58-56,K.ROW);r.kills.Position=UDim2.fromOffset(rw-54,0)
  end
 end
 local function render(list)
  for i,r in view.rows do
   local e=list[i];r.row.Visible=e~=nil
   if e then
    r.rank.Text=tostring(e.rank);r.rank.TextColor3=e.rank==1 and C.gold or C.muted
    r.head.Image=(e.userId or 0)>0 and string.format('rbxthumb://type=AvatarHeadShot&id=%d&w=48&h=48',e.userId) or ''
    r.name.Text=e.name;r.name.TextColor3=e.mine and C.limeSoft or C.white
    r.kills.Text=K.format(e.kills);r.kills.TextColor3=e.mine and C.lime or C.white
    r.row.BackgroundColor3=e.mine and C.limeDark or C.well;r.row.BackgroundTransparency=e.mine and 0 or .1;r.stroke.Enabled=e.mine
   end
  end
  view.count=#list;view.root.Size=UDim2.fromOffset(K.width(view.compact),K.height(#list))
 end
 -- Touch play, as the HUD decides it (RogueliteUI touchPlay).
 local function touchPlay()
  local ok,touch=pcall(function() return Input.PreferredInput==Enum.PreferredInput.Touch end)
  if ok then return touch end
  local last=Input:GetLastInputType()
  if last==Enum.UserInputType.Touch then return true end
  return Input.TouchEnabled and not Input.KeyboardEnabled
 end
 -- The HUD's own rects (RogueliteUI layout), in HUD-frame pixels.
 local function hudRects(hud)
  local origin=hud.AbsolutePosition;local w,h=hud.AbsoluteSize.X,hud.AbsoluteSize.Y
  local function rect(obj,height)
   local p=obj.AbsolutePosition-origin;local sz=obj.AbsoluteSize
   return {p.X,p.Y,p.X+sz.X,p.Y+(height or sz.Y)}
  end
  local timer=hud:FindFirstChild('Timer');local ts=timer and timer:FindFirstChildOfClass('UIScale');local s=ts and ts.Scale or 1
  local out={blocks={}}
  local health=hud:FindFirstChild('Health');if health then out.health=rect(health);table.insert(out.blocks,out.health) end
  if timer then table.insert(out.blocks,rect(timer,112*s)) end -- down to the TEST RUN tag
  local buildFrame=hud:FindFirstChild('Build')
  local bs=buildFrame and buildFrame:FindFirstChildOfClass('UIScale');bs=bs and bs.Scale or s
  out.build=buildFrame and rect(buildFrame,210*bs) or {w-12-330*s,12,w-12,12+210*s} -- three item rows reserved
  table.insert(out.blocks,out.build)
  local menu=hud:FindFirstChild('Menu');if menu and menu.Visible then out.menu=rect(menu);table.insert(out.blocks,out.menu) end
  for _,name in {'BossHealth','Round10Objective'} do
   local o=hud:FindFirstChild(name);if o and o:IsA('GuiObject') and o.Visible then table.insert(out.blocks,rect(o)) end
  end
  -- The DASH button (RogueliteCombat.client): bottom right on keyboards, left of jump on touch.
  local dashGui=playerGui:FindFirstChild('RogueliteDash');local area=dashGui and dashGui.Enabled and dashGui:FindFirstChild('SafeArea')
  local dash=area and area:FindFirstChild('DashButton')
  if dash and dash:IsA('GuiObject') and dash.Visible and dash.AbsoluteSize.X>0 then table.insert(out.blocks,rect(dash)) end
  -- The chat window: centre left in a run with a keyboard (RogueliteHUD moves it there).
  pcall(function()
   local window=game:GetService('TextChatService'):FindFirstChild('ChatWindowConfiguration')
   if window and window.Enabled and window.AbsoluteSize.X>0 then
    local p=window.AbsolutePosition-origin;out.chat={p.X,p.Y,p.X+window.AbsoluteSize.X,p.Y+window.AbsoluteSize.Y};table.insert(out.blocks,out.chat)
   end
  end)
  if touchPlay() then
   local small=math.min(w,h)<=500
   local jump=small and {w-95,h-90,w-25,h-20} or {w-170,h-210,w-50,h-90}
   local touchGui=playerGui:FindFirstChild('TouchGui');local frame=touchGui and touchGui:FindFirstChild('TouchControlFrame')
   local button=frame and frame:FindFirstChild('JumpButton')
   if button and button:IsA('GuiObject') and button.Visible and button.AbsoluteSize.X>0 then jump=rect(button) end
   table.insert(out.blocks,jump)
   table.insert(out.blocks,small and {0,h-150,170,h} or {0,h-260,260,h})
  end
  return w,h,s,out
 end
 local function hudFrame()
  local gui=playerGui:FindFirstChild('RogueliteHUD');local safe=gui and gui:FindFirstChild('SafeArea')
  return safe and safe:FindFirstChild('HUD')
 end
 -- Studio only: PlayerGui attribute KillBoardPreview=true adds three made-up teammates, so the
 -- board can be seen in a solo test (client-only; the server and the real counts are untouched).
 local function members()
  local list={}
  for _,p in Players:GetPlayers() do
   if p:GetAttribute('RunMember')==true then table.insert(list,{userId=p.UserId,name=p.DisplayName,kills=p:GetAttribute('RunKills') or 0}) end
  end
  if studio and playerGui:GetAttribute('KillBoardPreview')==true then
   local own=player:GetAttribute('RunKills') or 0
   for i,n in {'Builderman','Teammate2','Teammate3'} do table.insert(list,{userId=-i,name=n,kills=({math.floor(own*1.3)+12,math.floor(own/2)+3,7})[i]}) end
   local found=false;for _,e in list do if e.userId==player.UserId then found=true end end
   if not found then table.insert(list,{userId=player.UserId,name=player.DisplayName,kills=own}) end
  end
  return list
 end
 local function update()
  local hud=hudFrame()
  if not hud then return end
  if not view or view.root.Parent~=hud then
   if view then view.root:Destroy() end
   view=build(hud);lastSignature,lastScale=nil,nil
  end
  local list=members()
  local preview=studio and playerGui:GetAttribute('KillBoardPreview')==true
  local combat=RS:FindFirstChild('RogueliteCombat')
  local show=K.visible(#list,preview or player:GetAttribute('RunMember')==true,player:GetAttribute('RunResult')~=nil or player:GetAttribute('LobbyPreviewActive')==true,
   player:GetAttribute('Setting_KillBoard'),combat~=nil and combat:GetAttribute('TutorialRun')==true)
  view.root.Visible=show
  if not show then return end
  local rows=K.rows(K.rank(list,player.UserId),K.MAX)
  local signature=K.signature(rows)
  if signature~=lastSignature then lastSignature=signature;render(rows) end
  local w,h,s,rects=hudRects(hud)
  if w<2 or h<2 then return end
  local compact=math.min(w,h)<=500
  if compact~=view.compact then setCompact(compact) end
  local x,y,sc,clear=K.place(w,h,s,rects,#rows,compact)
  -- Nowhere clear (e.g. a 667 px phone while the boss bar sits bottom centre): hidden until the
  -- boss falls, rather than over the boss bar or the touch controls.
  view.root.Visible=clear
  view.root.Position=UDim2.fromOffset(math.floor(x+.5),math.floor(y+.5))
  if sc~=lastScale then
   lastScale=sc;view.scale.Scale=sc
   view.title.TextSize=readable(18,sc)
   for _,r in view.rows do r.rank.TextSize=readable(17,sc);r.name.TextSize=readable(17,sc);r.kills.TextSize=readable(19,sc) end
  end
 end
 -- Settings > Kill board: hide or show at once, not on the next half-second tick.
 player:GetAttributeChangedSignal('Setting_KillBoard'):Connect(function()
  local ok,err=pcall(update);if not ok then warn('KillBoard: update failed',err) end
 end)
 task.spawn(function()
  while true do
   local ok,err=pcall(update);if not ok then warn('KillBoard: update failed',err) end
   task.wait(.5)
  end
 end)
end
return K
