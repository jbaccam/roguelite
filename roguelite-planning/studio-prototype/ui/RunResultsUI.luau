-- Run results (LOBBY_AND_MATCH_SERVERS.md §5): VICTORY! / DEFEAT / EXTRACTED, the map and
-- difficulty, the emeralds the run paid (with FIRST WIN and NEW BEST), waves cleared, level, best
-- wave and the build it ended with. Shown while the server sets the player's RunResult attribute
-- (RogueliteMeta); BACK TO LOBBY asks the server to send them back, which it also does on its own
-- at returnAt (20 s). Presentation only: every number comes from the server.
-- One canvas (T.canvas): a 1200 x 780 board at most, laid out down to the 1280 x 640 phone canvas.
local Http=game:GetService('HttpService')
local TweenService=game:GetService('TweenService')
local GuiService=game:GetService('GuiService')
local UserInputService=game:GetService('UserInputService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('ShopCatalog'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local M={}
local TITLES={Victory={'VICTORY!',C.gold},Defeat={'DEFEAT',C.negative},Left={'EXTRACTED',C.lime}}

function M.mount(player)
 -- Full screen minus phone notches; the shade reaches under them.
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='RunResults',ResetOnSpawn=false,DisplayOrder=85,Enabled=false,
  ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false})
 local shade=T.make('Frame',screen,{Name='Shade',Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),BackgroundColor3=C.shade,BackgroundTransparency=.12,BorderSizePixel=0,Active=true})
 shade:SetAttribute('AuditIgnore',true)
 local tint=T.make('Frame',screen,{Name='Tint',Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),BackgroundTransparency=.82,BorderSizePixel=0})
 tint:SetAttribute('AuditIgnore',true)
 T.make('UIGradient',tint,{Rotation=90,Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.45,1),NumberSequenceKeypoint.new(1,1)})})
 local root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local result -- the decoded RunResult
 local L,canvas,content,note,back
 local token=0

 local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
 local function draw()
  if content then content:Destroy();content=nil;note=nil;back=nil end
  if not result or not L then return end
  local r=result
  content=T.frame(canvas,'Content',0,0,L.w,L.h)
  -- The board: the title plate pokes 42 above it, under Roblox's top-bar band (L.top).
  local PW=math.min(1200,L.w-64);local PH=math.min(780,L.h-L.top-70)
  local px=(L.w-PW)/2;local py=L.top+48+math.max(0,(L.h-L.top-48-PH-16)/2)
  local board=T.panel(content,'Board',px,py,PW,PH,'panel')
  local look=TITLES[r.outcome] or TITLES.Left
  tint.BackgroundColor3=look[2]
  local plate=T.panel(content,'TitlePlate',px+(PW-560)/2,py-42,560,84,'panel');T.caps(plate,52)
  local title=centred(T.label(plate,'Title',look[1],20,6,520,72,58,look[2]))
  local pop=T.make('UIScale',plate,{Scale=1.25})
  TweenService:Create(pop,TweenInfo.new(.45,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
  title.TextStrokeTransparency=0
  -- Map, difficulty, and Endless when the run went past the win.
  local endless=(r.waves or 0)>(r.winWave or 20)
  local sub=string.upper((r.mapName or 'Pine Valley')..'  ·  '..(r.difficulty or 'Normal'))..(endless and '  ·  ENDLESS' or '')
  centred(T.label(board,'Sub',sub,28,50,PW-56,32,26,C.muted))
  -- Row A: emeralds on the left, three stat tiles on the right.
  local compact=PH<600
  local RA=compact and 116 or 136;local ay=92
  local RW=math.floor(PW*.44)-28
  local reward=T.panel(board,'Reward',28,ay,RW,RA,'inset')
  local es=RA-40
  T.icon(reward,'Emerald',16,20,es,'emerald')
  local value=T.label(reward,'Value','+'..(r.emeralds or 0),es+28,8,RW-es-40,RA*.5,64,C.emerald);value.TextXAlignment=Enum.TextXAlignment.Left
  local cap=T.label(reward,'Caption','EMERALDS EARNED',es+28,RA*.5+6,RW-es-40,26,20,C.muted);cap.TextXAlignment=Enum.TextXAlignment.Left
  local chips={}
  if (r.firstWin or 0)>0 then table.insert(chips,{'FIRST WIN +'..r.firstWin,Color3.fromRGB(120,88,10),C.gold}) end
  if r.newBest then table.insert(chips,{'NEW BEST',C.limeDark,C.limeSoft}) end
  if r.test then table.insert(chips,{'TEST RUN · NO REWARDS',Color3.fromRGB(110,26,30),C.negative}) end
  local cx=es+28
  for i,c in chips do
   local chip=T.chip(reward,'Chip'..i,c[1],cx,RA-34,c[2],c[3])
   cx+=chip.Size.X.Offset+8
  end
  local sx=28+RW+20;local tw=(PW-28-sx-28)/3
  for i,t in {{tostring(r.waves or 0),endless and 'WAVES (ENDLESS)' or 'WAVES CLEARED'},{tostring(r.level or 1),'LEVEL REACHED'},{tostring(r.best or 0),'BEST WAVE'}} do
   local tile=T.panel(board,'Stat'..i,sx+(i-1)*(tw+14),ay,tw,RA,'inset')
   centred(T.label(tile,'Value',t[1],8,10,tw-16,RA-52,48,i==3 and r.newBest and C.lime or C.white))
   centred(T.label(tile,'Caption',t[2],8,RA-42,tw-16,26,18,C.muted))
  end
  -- Build: the weapons the run ended with, then its items (scrolling when there are many).
  local by=ay+RA+18;local BH=PH-by-110
  local head=T.label(board,'BuildTitle','YOUR BUILD',28,by,300,30,26,C.cream);head.TextXAlignment=Enum.TextXAlignment.Left
  local cell=math.min(80,BH-40)
  for i,w in r.weapons or {} do
   local slot=T.panel(board,'Weapon'..i,28+(i-1)*(cell+8),by+38,cell,cell,'inset');T.setTier(slot,w.tier)
   T.icon(slot,'Icon',cell*.12,cell*.12,cell*.76,WeaponIcons[w.id])
   T.tierBadge(slot,w.tier,cell-2,cell-2,Vector2.new(1,1))
  end
  local ix=28+6*(cell+8)+16;local iw=PW-28-ix
  local items=T.scroll(board,'Items',ix,by+38,iw,math.max(cell,BH-38))
  local icell=math.min(64,cell);local cols=math.max(1,math.floor((iw-6)/(icell+8)))
  local list=r.items or {}
  if #list==0 then T.text(items,'None','No items this run.',4,4,iw-12,26,18,C.muted) end
  for i,it in list do
   local entry=Catalog.ById[it.id]
   if entry then
    local c=T.panel(items,'Item'..i,((i-1)%cols)*(icell+8),math.floor((i-1)/cols)*(icell+8),icell,icell,'inset');T.setTier(c,entry.tier)
    T.icon(c,'Icon',icell*.14,icell*.12,icell*.72,T.Asset[entry.icon] or entry.icon)
    if (it.count or 1)>1 then local n=T.label(c,'Count','×'..it.count,0,icell-26,icell-6,24,18);n.TextXAlignment=Enum.TextXAlignment.Right end
   end
  end
  items.CanvasSize=UDim2.fromOffset(0,math.ceil(#list/cols)*(icell+8))
  -- BACK TO LOBBY, and the countdown to the automatic return.
  back=T.button(board,'BackToLobby','BACK TO LOBBY',(PW-360)/2,PH-96,360,64,function()
   if not back or not back.Interactable then return end
   back.Interactable=false;back.Caption.Text='RETURNING...'
   combat.RunAction:FireServer('ReturnToLobby')
  end)
  back.Caption.TextSize=28
  note=centred(T.label(board,'Note','',28,PH-30,PW-56,24,18,C.muted))
  if UserInputService:GetLastInputType().Name:find('^Gamepad') then pcall(function() GuiService.SelectedObject=back end) end
 end
 local relayout
 canvas,relayout=T.canvas(root,function(layout) L=layout;if screen.Enabled then draw() end end)

 local function show()
  local ok,data=pcall(Http.JSONDecode,Http,player:GetAttribute('RunResult') or '')
  if not ok or type(data)~='table' then return end
  result=data;token+=1;local mine=token
  screen.Enabled=true;T.hideTouchControls('RunResults',true)
  T.sound(data.outcome=='Victory' and 'ui_upgrade' or 'ui_equip')
  relayout() -- the screen was off: measure it again (this draws)
  if not content then draw() end
  -- The countdown follows the server's clock (returnAt), so a slow client never shows it wrong.
  task.spawn(function()
   while token==mine and screen.Enabled do
    if note and result.returnAt then
     local left=math.max(0,math.ceil(result.returnAt-workspace:GetServerTimeNow()))
     note.Text=left>0 and ('Back to the lobby in '..left..'s') or 'Returning to the lobby...'
    end
    task.wait(.25)
   end
  end)
 end
 local function hide()
  token+=1;result=nil;screen.Enabled=false;T.hideTouchControls('RunResults',false)
  if content then content:Destroy();content=nil end
 end
 local function changed() if player:GetAttribute('RunResult') then show() else hide() end end
 player:GetAttributeChangedSignal('RunResult'):Connect(changed)
 changed()
 return M
end
return M
