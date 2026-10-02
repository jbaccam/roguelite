-- "YOU DIED" splash, then one of two views while the server sets RunDown:
-- * Teammates still fighting: SPECTATE. The camera follows one of them (‹ › on screen, Q/E,
--   LB/RB), with REVIVE and LEAVE RUN; downed players respawn when the wave ends. A teammate can
--   also revive them for free by holding their spot for 5 s (TeammateRevive): "BEN IS REVIVING YOU"
--   then shows at the top with the hold's progress, and the screen closes when they stand up.
-- * Nobody left standing (or solo): the run summary (stats, weapons, items, progress) under
--   "REVIVE OR THE RUN ENDS · n", the server's last-stand clock (RogueliteRunState.LastStandEndsAt).
--   The same clock shows under the YOU DIED splash, so it is on screen from the first moment.
-- REVIVE is Robux, server-validated, and its price doubles with each revive in a run (DeathInfo);
-- LEAVE RUN ends this player's run (results screen).
local TweenService=game:GetService('TweenService')
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local UserInputService=game:GetService('UserInputService')
local GuiService=game:GetService('GuiService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local LevelUps=require(combat:WaitForChild('LevelUpCatalog'))
local Catalog=require(combat:WaitForChild('ShopCatalog'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local ShopUI=require(RS:WaitForChild('ShopUI'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local M={}

function M.mount(player)
 local state=combat:WaitForChild('PlayerStates'):WaitForChild(tostring(player.UserId))
 -- Full screen minus phone notches and rounded corners; the shade and vignette reach under them.
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='DeathScreen',ResetOnSpawn=false,DisplayOrder=80,ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false,Enabled=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local shade=T.make('Frame',screen,{Name='Shade',Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),BackgroundColor3=Color3.new(0,0,0),BackgroundTransparency=1,BorderSizePixel=0,Active=true})
 local vignette=T.make('Frame',screen,{Name='Vignette',Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),BackgroundColor3=Color3.fromRGB(150,10,20),BackgroundTransparency=1,BorderSizePixel=0})
 T.make('UIGradient',vignette,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.5,1),NumberSequenceKeypoint.new(1,0)})})
 -- Root of the layout: the safe area. The summary is placed from its AbsoluteSize.
 local root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local splash=T.label(root,'YouDied','YOU DIED',0,0,0,0,120,Color3.fromRGB(236,38,48))
 splash.AnchorPoint=Vector2.new(.5,.5);splash.Position=UDim2.fromScale(.5,.45);splash.Size=UDim2.fromOffset(900,150);splash.TextWrapped=false
 T.make('UIStroke',splash,{Color=Color3.fromRGB(20,4,6),Thickness=7,ApplyStrokeMode=Enum.ApplyStrokeMode.Contextual})
 local splashScale=T.make('UIScale',splash,{Scale=1})
 local sub=T.label(root,'Wave','',0,0,0,0,30,C.white);sub.AnchorPoint=Vector2.new(.5,0);sub.Position=UDim2.new(.5,0,.45,82);sub.Size=UDim2.fromOffset(700,40)
 -- The last stand's clock under the splash, so the countdown shows from the first moment of death;
 -- the summary title takes over once the splash fades. It pops on each new second.
 local clock=T.label(root,'Clock','',0,0,0,0,40,C.negative);clock.AnchorPoint=Vector2.new(.5,0);clock.Position=UDim2.new(.5,0,.45,132);clock.Size=UDim2.fromOffset(700,52);clock.Visible=false
 T.make('UIStroke',clock,{Color=Color3.fromRGB(20,4,6),Thickness=4,ApplyStrokeMode=Enum.ApplyStrokeMode.Contextual})
 local clockScale=T.make('UIScale',clock,{Scale=1})
 local clockShown -- the number on the clock, to pop it only when it changes
 -- A teammate holding this player's revive spot (TeammateRevive): "BEN IS REVIVING YOU" and the hold,
 -- read from the spot's HoldStartedAt (server time), so it fills in step with the ring they see.
 -- Near the top, clear of the splash and the spectate bar; phones draw it smaller (.56 at 390 tall).
 local reviving=T.panel(root,'Reviving',0,0,560,96,'panel');reviving.AnchorPoint=Vector2.new(.5,0);reviving.Position=UDim2.new(.5,0,0,60);reviving.Visible=false
 local revivingScale=T.make('UIScale',reviving,{Scale=1})
 local revivingText=T.label(reviving,'Text','',20,8,520,40,30,C.lime)
 local revivingFill=T.bar(reviving,'Progress',40,58,480,18,C.lime)
 local spots -- Workspace.RogueliteReviveSpots, once it exists
 local function revivingTick()
  local spot
  if screen.Enabled then
   spots=spots or workspace:FindFirstChild('RogueliteReviveSpots')
   for _,s in spots and spots:GetChildren() or {} do if s:GetAttribute('DownUserId')==player.UserId then spot=s;break end end
  end
  local began=spot and spot:GetAttribute('HoldStartedAt')
  if type(began)~='number' then reviving.Visible=false;return end
  local v=root.AbsoluteSize
  revivingScale.Scale=math.clamp(math.min((v.X-24)/560,v.Y/700),.4,1)
  revivingText.Text=string.upper(spot:GetAttribute('ReviverName') or 'A teammate')..' IS REVIVING YOU'
  T.setBar(revivingFill,(workspace:GetServerTimeNow()-began)/(spot:GetAttribute('HoldSeconds') or 5))
  reviving.Visible=true
 end
 RunService.RenderStepped:Connect(revivingTick)
 local summary -- built per death
 local info={};local tab='Primary';local token=0
 local uiScale=1 -- the summary's scale, set by build()
 local runState=RS:WaitForChild('RogueliteRunState')
 local mode -- 'spectate' or 'summary', chosen by build()
 local watching -- the teammate the camera follows while spectating
 local countdown -- the summary title, rewritten as the last stand counts down
 -- Teammates still in this run and standing (ShopService's RunMember, server-set).
 local function teammates()
  local list={}
  for _,p in game:GetService('Players'):GetPlayers() do
   local h=p~=player and p:GetAttribute('RunMember') and not p:GetAttribute('RunDown') and p.Character and p.Character:FindFirstChildOfClass('Humanoid')
   if h and h.Health>0 then table.insert(list,p) end
  end
  table.sort(list,function(a,b) return a.UserId<b.UserId end)
  return list
 end
 local function follow(p)
  watching=p
  local h=p and p.Character and p.Character:FindFirstChildOfClass('Humanoid')
  if h then workspace.CurrentCamera.CameraSubject=h end
 end
 local function cycle(step)
  local list=teammates();if #list==0 then return end
  local at=table.find(list,watching) or 0
  follow(list[(at-1+step)%#list+1]);M.redraw()
 end
 -- This revive's price: the server's DeathInfo says which revive of the run it is (each one doubles),
 -- and Money.price gives what Roblox charges this player for it (regional prices, price tests).
 local function revivePrice() return Money.price(Money.reviveKey(info.revive or 1)) end
 -- Seconds left in the last stand (everyone in the run is down), nil when there is none.
 local function lastStandLeft()
  local ends=runState:GetAttribute('LastStandEndsAt')
  return ends and math.max(0,math.ceil(ends-workspace:GetServerTimeNow())) or nil
 end
 -- Fitted body text may shrink, but not below 9 px on screen (at scale .55 that is 17 layout px).
 local function readable(l)
  local c=l:FindFirstChildOfClass('UITextSizeConstraint')
  if c then c.MinTextSize=math.min(c.MaxTextSize,math.max(9,math.ceil(9/uiScale))) end
  return l
 end

 local function statsPanel(parent,x,y,w,h)
  local box=T.panel(parent,'Stats',x,y,w,h,'panel')
  T.label(box,'Title','Stats',0,12,w,36,30)
  local tabH=math.max(38,math.ceil(40/uiScale)) -- 40 px taps on phones
  T.tabs(box,16,56,w-32,tabH,{'Primary','Secondary'},tab,function(id) tab=id;M.redraw() end)
  local values=Stats.read(state)
  local rows=T.scroll(box,'Rows',14,66+tabH,w-28,h-78-tabH)
  local list={{id='Level',label='Current level',value=tostring(info.level or 1),color=C.white}}
  for _,d in Stats.List do
   if (LevelUps.ById[d.id]~=nil)==(tab=='Primary') then
    table.insert(list,{id=d.id,label=d.label,value=Stats.format(d,values[d.id]),color=ShopUI.statColor(d.id,values[d.id],d.base),icon=LevelUps.icon(d.id)})
   end
  end
  local rowH=28
  for i,r in list do
   local yy=(i-1)*rowH+(i>1 and 8 or 0)
   if r.icon and r.icon~='' then T.icon(rows,r.id..'Icon',0,yy+3,22,r.icon) end
   local n=readable(T.text(rows,r.id,r.label,28,yy,(w-28)*.62-28,rowH,18,r.color))
   local v=readable(T.text(rows,r.id..'Value',r.value,(w-28)*.62,yy,(w-28)*.38-14,rowH,18,r.color));v.TextXAlignment=Enum.TextXAlignment.Right
   n.TextYAlignment=Enum.TextYAlignment.Center
  end
  rows.CanvasSize=UDim2.fromOffset(0,#list*rowH+12)
 end
 local function section(parent,name,text,x,y,w)
  local l=T.label(parent,name,text,x,y,300,40,32);l.TextXAlignment=Enum.TextXAlignment.Left
  local tw=game:GetService('TextService'):GetTextSize(text,32,T.Font,Vector2.new(1000,100)).X
  T.make('Frame',parent,{Name=name..'Line',Position=UDim2.fromOffset(x+tw+16,y+21),Size=UDim2.fromOffset(math.max(0,w-tw-16),2),BackgroundColor3=Color3.fromRGB(60,66,70),BorderSizePixel=0})
 end
 local function build()
  local path=T.selectionPath(root) -- a controller's selection survives a redraw (stat tabs)
  -- 1180 wide at one scale that fits the width; the height follows the screen between 476 (+ the
  -- taller phone buttons) and 640, and the stats and items lists scroll. Example: a 750x369 phone
  -- gets scale .615 and a 1180x574 summary (text 18 -> 11 px) instead of .54 on 1180x640.
  local v=root.AbsoluteSize
  if v.X<100 or v.Y<100 then return end
  if summary then summary:Destroy() end
  countdown=nil
  local mates=teammates()
  mode=#mates>0 and 'spectate' or 'summary'
  if mode=='spectate' then
   -- A light shade so the arena reads; a bar at the bottom: who you watch, REVIVE, LEAVE RUN.
   shade.BackgroundTransparency=.82;vignette.BackgroundTransparency=.55
   if not table.find(mates,watching) then follow(mates[1]) end
   local W,H=880,224
   local s=math.min(1,(v.X-24)/W);local bh=math.max(56,math.ceil(40/s))
   uiScale=s
   summary=T.frame(root,'Spectate',0,0,W,H+bh-56);summary.AnchorPoint=Vector2.new(.5,1)
   T.make('UIScale',summary,{Scale=s})
   summary.Position=UDim2.new(.5,0,1,-12)
   local bar=T.panel(summary,'Bar',0,0,W,H+bh-56,'panel')
   local aw=math.max(64,math.ceil(40/s))
   T.button(bar,'Prev','‹',20,16,aw,64,function() cycle(-1) end,true).Caption.TextSize=44
   T.button(bar,'Next','›',W-20-aw,16,aw,64,function() cycle(1) end,true).Caption.TextSize=44
   local name=watching and (watching.DisplayName or watching.Name) or ''
   T.label(bar,'Watching','SPECTATING  '..string.upper(name),40+aw,18,W-80-2*aw,40,32)
   readable(T.text(bar,'Hint','A teammate can revive you  ·  respawn at wave end  ·  Q / E to switch',40+aw,58,W-80-2*aw,22,17,C.muted)).TextXAlignment=Enum.TextXAlignment.Center
   local bw=320;local by=96
   local revive=T.button(bar,'Revive','REVIVE  ·  R$ '..revivePrice(),W/2-bw-16,by,bw,bh,function() combat.PurchaseRequest:FireServer('Revive') end)
   revive.Caption.TextSize=26
   local leave=T.button(bar,'LeaveRun','LEAVE RUN',W/2+16,by,bw,bh,function() combat.RunAction:FireServer('LeaveRun') end,true)
   leave.Caption.TextSize=26;leave.Caption.TextColor3=C.negative
   readable(T.text(bar,'LeaveNote','Keep '..(info.emeralds or 0)..' emeralds',W/2+16,by+bh+6,bw,20,16,C.muted)).TextXAlignment=Enum.TextXAlignment.Center
   if UserInputService:GetLastInputType().Name:find('^Gamepad') then GuiService.SelectedObject=revive end
   return
  end
  shade.BackgroundTransparency=.2;vignette.BackgroundTransparency=.35
  -- Nobody to watch: back to your own body (it lies where you fell).
  if watching then watching=nil;local own=player.Character and player.Character:FindFirstChildOfClass('Humanoid');if own then workspace.CurrentCamera.CameraSubject=own end end
  local W=1180
  local s=math.min(1,(v.X-24)/W)
  local bh=math.max(64,math.ceil(40/s)) -- REVIVE / GIVE UP stay 40 px to tap
  local H=math.min(640,math.max(476+bh-64,(v.Y-16)/s))
  if H*s>v.Y-16 then s=(v.Y-16)/H end
  uiScale=s
  summary=T.frame(root,'Summary',0,0,W,H);summary.AnchorPoint=Vector2.new(.5,.5)
  local scale=T.make('UIScale',summary,{Scale=s})
  -- Centre near 52% of the height, but always 8 px inside the safe area.
  local cy=math.clamp(v.Y*.52,8+H*s/2,math.max(8+H*s/2,v.Y-8-H*s/2))
  local title=T.panel(summary,'Title',(W-620)/2,0,620,62,'panel');T.caps(title,46)
  countdown=T.label(title,'Text','DOWN  ·  '..string.upper(info.map or 'Pine Valley')..'  ·  WAVE '..(info.wave or 1),0,0,620,62,26)
  local by=H-6-bh -- buttons; their notes sit just above, the body ends above the notes
  local BH=by-28-76
  local body=T.panel(summary,'Body',0,76,W,BH,'panel')
  statsPanel(body,14,14,330,BH-28)
  local RX=364;local RW=W-RX-24
  -- Weapons (live slots) and progress. Progress starts after room for all six weapon cells
  -- (6 x 84 - 8 = 496), so a full loadout never runs into it: x 884, 272 wide.
  local PX=RX+6*84-8+24;local PW=W-24-PX
  section(body,'WeaponsTitle','Weapons',RX,16,PX-24-RX)
  local wx=RX
  local badgeSize=math.max(15,math.ceil(10/s)) -- tier numeral at least 10 px on screen
  for i=1,6 do
   local slot=state:FindFirstChild('Slot'..i);local id=slot and slot:GetAttribute('WeaponId') or ''
   if id~='' then
    local tier=slot:GetAttribute('Tier') or 1
    local cell=T.panel(body,'Weapon'..i,wx,64,76,76,'inset');T.setTier(cell,tier)
    T.icon(cell,'Icon',10,10,56,WeaponIcons[id])
    local badge=T.tierBadge(cell,tier,74,74,Vector2.new(1,1))
    if badgeSize>15 then
     badge.Size=UDim2.fromOffset(math.round(badge.Size.X.Offset*badgeSize/15),math.round(badge.Size.Y.Offset*badgeSize/15))
     local t=badge:FindFirstChild('Tier');if t then t.TextSize=badgeSize end
    end
    wx+=84
   end
  end
  section(body,'ProgressTitle','Progress',PX,16,PW)
  local rows={{'Waves survived',tostring(math.max(0,(info.wave or 1)-1))},{'Level reached',tostring(info.level or 1)},{'Emeralds earned',tostring(info.emeralds or 0)}}
  for i,r in rows do
   local yy=62+(i-1)*28
   readable(T.text(body,'Progress'..i,r[1],PX,yy,PW-96,26,18,C.muted))
   local val=readable(T.text(body,'ProgressValue'..i,r[2],PX+PW-92,yy,92,26,18,i==3 and C.gold or C.white));val.TextXAlignment=Enum.TextXAlignment.Right
  end
  -- Items from the run snapshot.
  section(body,'ItemsTitle','Items',RX,160,RW)
  local raw=state:GetAttribute('ShopSnapshot');local ok,data=pcall(Http.JSONDecode,Http,raw or '')
  local items=ok and data and data.items or {}
  local grid=T.scroll(body,'Items',RX,208,RW,BH-222)
  local cols=math.max(1,math.floor((RW-12)/80))
  if #items==0 then readable(T.text(grid,'None','No items this run.',4,4,RW-20,26,18,C.muted)) end
  for i,it in items do
   local entry=Catalog.ById[it.id]
   if entry then
    local cell=T.panel(grid,'Item'..i,((i-1)%cols)*80,math.floor((i-1)/cols)*80,72,72,'inset');T.setTier(cell,entry.tier)
    T.icon(cell,'Icon',10,8,52,T.Asset[entry.icon] or entry.icon)
    if it.count>1 then local n=T.label(cell,'Count','×'..it.count,0,44,66,24,20);n.TextXAlignment=Enum.TextXAlignment.Right end
   end
  end
  grid.CanvasSize=UDim2.fromOffset(0,math.ceil(#items/cols)*80)
  -- Actions.
  -- Buttons 40 apart; each note is 340 wide over its button, so the two never meet.
  local bw=300
  local revive=T.button(summary,'Revive','REVIVE  ·  R$ '..revivePrice(),W/2-bw-20,by,bw,bh,function()
   combat.PurchaseRequest:FireServer('Revive')
  end)
  revive.Caption.TextSize=26
  -- Say up front that the next one costs more (prices double, up to R$ 1040).
  local nextPrice=Money.price(Money.reviveKey((info.revive or 1)+1))
  local noteText=(nextPrice and nextPrice>revivePrice()) and ('Back with 50% health  ·  next one R$ '..nextPrice) or 'Back in the same wave with 50% health'
  local note=readable(T.text(summary,'ReviveNote',noteText,W/2-bw/2-20-170,by-24,340,20,17,C.muted));note.TextXAlignment=Enum.TextXAlignment.Center
  local give=T.button(summary,'LeaveRun','LEAVE RUN',W/2+20,by,bw,bh,function() combat.RunAction:FireServer('LeaveRun') end,true)
  give.Caption.TextSize=26;give.Caption.TextColor3=C.negative
  local keys=readable(T.text(summary,'LeaveNote','Keep '..(info.emeralds or 0)..' emerald'..((info.emeralds or 0)==1 and '' or 's')..' and see your results',W/2+bw/2+20-170,by-24,340,20,17,C.muted));keys.TextXAlignment=Enum.TextXAlignment.Center
  summary.Position=UDim2.fromOffset(v.X/2,cy+v.Y*.06);TweenService:Create(summary,TweenInfo.new(.35,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Position=UDim2.fromOffset(v.X/2,cy)}):Play()
  -- Controller: keep the selection across a redraw, else start on REVIVE.
  if path then T.restoreSelection(root,path)
  elseif UserInputService:GetLastInputType().Name:find('^Gamepad') then GuiService.SelectedObject=revive end
 end
 function M.redraw() if summary and screen.Enabled then build() end end
 local function show()
  local raw=player:GetAttribute('DeathInfo');local ok,d=pcall(Http.JSONDecode,Http,raw or '')
  info=ok and d or {}
  token+=1;local mine=token
  screen.Enabled=true;tab='Primary'
  T.hideTouchControls('DeathScreen',true) -- the jump button would sit over GIVE UP on phones
  if summary then summary:Destroy();summary=nil end
  -- The splash never wider than the screen (its text shrinks to fit).
  -- Just enabled: the root may not have a size yet on the first death; use the camera's.
  local vx=root.AbsoluteSize.X;if vx<100 then vx=workspace.CurrentCamera.ViewportSize.X end
  splash.Size=UDim2.fromOffset(math.min(900,vx-24),150);sub.Size=UDim2.fromOffset(math.min(700,vx-24),40);clock.Size=UDim2.fromOffset(math.min(700,vx-24),52)
  shade.BackgroundTransparency=1;vignette.BackgroundTransparency=1
  splash.Visible=true;sub.Visible=true;splash.TextTransparency=1;sub.TextTransparency=1
  -- The clock is up from the first frame (no fade-in), so a solo player sees every second.
  clock.Visible=true;clock.TextTransparency=0;clock.Text='';clockShown=nil
  sub.Text='Wave '..(info.wave or 1)..'  ·  Level '..(info.level or 1)
  splashScale.Scale=1.6
  TweenService:Create(shade,TweenInfo.new(.6),{BackgroundTransparency=.45}):Play()
  TweenService:Create(vignette,TweenInfo.new(.6),{BackgroundTransparency=.35}):Play()
  TweenService:Create(splash,TweenInfo.new(.35),{TextTransparency=0}):Play()
  TweenService:Create(splashScale,TweenInfo.new(.5,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
  task.delay(.5,function() if token==mine then TweenService:Create(sub,TweenInfo.new(.3),{TextTransparency=0}):Play() end end)
  task.delay(2.3,function()
   if token~=mine or not screen.Enabled then return end
   TweenService:Create(splash,TweenInfo.new(.25),{TextTransparency=1}):Play()
   TweenService:Create(sub,TweenInfo.new(.25),{TextTransparency=1}):Play()
   TweenService:Create(clock,TweenInfo.new(.25),{TextTransparency=1}):Play()
   TweenService:Create(shade,TweenInfo.new(.3),{BackgroundTransparency=.2}):Play()
   task.delay(.25,function() if token==mine and screen.Enabled then splash.Visible=false;sub.Visible=false;clock.Visible=false;build() end end)
  end)
  -- The splash clock: "REVIVE OR THE RUN ENDS · n" while everyone in the run is down.
  local function tickClock()
   if not clock.Visible then return end
   local left=lastStandLeft()
   clock.Text=left and ('REVIVE OR THE RUN ENDS  ·  '..left) or ''
   if left and left~=clockShown then
    clockShown=left;clockScale.Scale=1.25
    TweenService:Create(clockScale,TweenInfo.new(.3,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
   end
  end
  tickClock()
  -- Keep the view right while down: switch views when the last teammate falls (or one is revived),
  -- follow someone else when the watched teammate falls, and count the last stand down.
  task.spawn(function()
   while token==mine and screen.Enabled do
    task.wait(.1)
    if token~=mine then continue end
    tickClock()
    if not summary then continue end
    local mates=teammates()
    if (#mates>0 and 'spectate' or 'summary')~=mode then M.redraw()
    elseif mode=='spectate' and not table.find(mates,watching) then follow(mates[1]);M.redraw() end
    local left=lastStandLeft()
    if countdown and countdown.Parent then
     countdown.TextColor3=left and C.negative or C.white
     countdown.Text=left and ('REVIVE OR THE RUN ENDS  ·  '..left)
      or 'DOWN  ·  '..string.upper(info.map or 'Pine Valley')..'  ·  WAVE '..(info.wave or 1)
    end
   end
  end)
 end
 local function hide()
  token+=1;screen.Enabled=false;clock.Visible=false;T.hideTouchControls('DeathScreen',false);if summary then summary:Destroy();summary=nil end
  -- Spectating ends: the camera goes back to this player's own body when there is one.
  if watching then watching=nil;local own=player.Character and player.Character:FindFirstChildOfClass('Humanoid');if own then workspace.CurrentCamera.CameraSubject=own end end
 end
 -- Q / E and the bumpers switch the teammate you watch.
 UserInputService.InputBegan:Connect(function(input,processed)
  if not screen.Enabled or mode~='spectate' or UserInputService:GetFocusedTextBox() then return end
  if input.KeyCode==Enum.KeyCode.Q or input.KeyCode==Enum.KeyCode.ButtonL1 then cycle(-1)
  elseif input.KeyCode==Enum.KeyCode.E or input.KeyCode==Enum.KeyCode.ButtonR1 then cycle(1) end
 end)
 local function changed() if player:GetAttribute('RunDown') then show() else hide() end end
 player:GetAttributeChangedSignal('RunDown'):Connect(changed)
 root:GetPropertyChangedSignal('AbsoluteSize'):Connect(function() if summary then M.redraw() end end)
 combat:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(key,ok,message)
  if screen.Enabled and Money.isRevive(key) and type(message)=='string' then T.toast(screen,message,ok and C.lime or C.negative) end
 end)
 changed()
 return M
end
return M
