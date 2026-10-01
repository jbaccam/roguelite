-- "YOU DIED" splash, then the run summary: stats, equipped weapons, items and progress,
-- with REVIVE (Robux, server-validated) and GIVE UP. Shown while the server sets RunDown.
local TweenService=game:GetService('TweenService')
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
 local summary -- built per death
 local info={};local tab='Primary';local token=0
 local uiScale=1 -- the summary's scale, set by build()
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
  T.label(title,'Text','RUN OVER  ·  '..string.upper(info.map or 'Pine Valley')..'  ·  WAVE '..(info.wave or 1),0,0,620,62,26)
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
  local restrictedRevive=(info.revivesLeft or 0)<=0
  -- Buttons 40 apart; each note is 340 wide over its button, so the two never meet.
  local bw=300
  local revive=T.button(summary,'Revive','REVIVE  ·  R$ '..Money.Products.Revive.robux,W/2-bw-20,by,bw,bh,function()
   combat.PurchaseRequest:FireServer('Revive')
  end)
  revive.Caption.TextSize=26;revive.Interactable=not restrictedRevive
  if restrictedRevive then revive.Caption.Text='NO REVIVES LEFT' end
  local note=readable(T.text(summary,'ReviveNote','Back in the same wave with 50% health',W/2-bw/2-20-170,by-24,340,20,17,C.muted));note.TextXAlignment=Enum.TextXAlignment.Center
  local give=T.button(summary,'GiveUp','GIVE UP',W/2+20,by,bw,bh,function() combat.RunAction:FireServer('GiveUp') end,true)
  give.Caption.TextSize=26;give.Caption.TextColor3=C.negative
  local keys=readable(T.text(summary,'GiveUpNote','Keep '..(info.emeralds or 0)..' emerald'..((info.emeralds or 0)==1 and '' or 's')..' and return to wave 1',W/2+bw/2+20-170,by-24,340,20,17,C.muted));keys.TextXAlignment=Enum.TextXAlignment.Center
  summary.Position=UDim2.fromOffset(v.X/2,cy+v.Y*.06);TweenService:Create(summary,TweenInfo.new(.35,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Position=UDim2.fromOffset(v.X/2,cy)}):Play()
  -- Controller: keep the selection across a redraw, else start on REVIVE (GIVE UP when no revive).
  if path then T.restoreSelection(root,path)
  elseif UserInputService:GetLastInputType().Name:find('^Gamepad') then GuiService.SelectedObject=revive.Interactable and revive or give end
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
  splash.Size=UDim2.fromOffset(math.min(900,vx-24),150);sub.Size=UDim2.fromOffset(math.min(700,vx-24),40)
  shade.BackgroundTransparency=1;vignette.BackgroundTransparency=1
  splash.Visible=true;sub.Visible=true;splash.TextTransparency=1;sub.TextTransparency=1
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
   TweenService:Create(shade,TweenInfo.new(.3),{BackgroundTransparency=.2}):Play()
   task.delay(.25,function() if token==mine and screen.Enabled then splash.Visible=false;sub.Visible=false;build() end end)
  end)
 end
 local function hide() token+=1;screen.Enabled=false;T.hideTouchControls('DeathScreen',false);if summary then summary:Destroy();summary=nil end end
 local function changed() if player:GetAttribute('RunDown') then show() else hide() end end
 player:GetAttributeChangedSignal('RunDown'):Connect(changed)
 root:GetPropertyChangedSignal('AbsoluteSize'):Connect(function() if summary then M.redraw() end end)
 combat:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(key,ok,message)
  if screen.Enabled and key=='Revive' and type(message)=='string' then T.toast(screen,message,ok and C.lime or C.negative) end
 end)
 changed()
 return M
end
return M
