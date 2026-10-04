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
 local L,canvas,content,note,back,again
 local token=0

 local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
 -- While PLAY AGAIN waits (the server's PlayAgainStatus), its button cancels and the note says why.
 local function paintAgain()
  if not again or not again.Parent then return end
  local waiting=player:GetAttribute('PlayAgainStatus')
  again.Caption.Text=waiting and 'CANCEL' or 'PLAY AGAIN'
  if note and waiting then note.Text=waiting;note.TextColor3=C.lime elseif note then note.TextColor3=C.muted end
 end
 player:GetAttributeChangedSignal('PlayAgainStatus'):Connect(paintAgain)
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
  -- The tutorial (r.tutorial = TutorialConfig.Reward): its emeralds count up from 0.
  if r.tutorial then
   local target=r.tutorial.emeralds or 0;value.Text='+0'
   task.spawn(function() for i=1,24 do task.wait(.035);if not value.Parent then return end;value.Text='+'..math.floor(target*i/24+.5) end end)
  end
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
  local tiles={{tostring(r.waves or 0),endless and 'WAVES (ENDLESS)' or 'WAVES CLEARED'},{tostring(r.level or 1),'LEVEL REACHED'},{tostring(r.best or 0),'BEST WAVE'}}
  -- The tutorial: its chests instead of the best wave.
  if r.tutorial then local n=0;for _,c in r.tutorial.chests or {} do n+=c end;tiles[3]={'×'..n,'SILVER CHESTS'} end
  for i,t in tiles do
   local tile=T.panel(board,'Stat'..i,sx+(i-1)*(tw+14),ay,tw,RA,'inset')
   -- The tutorial's tiles pop in one after another.
   if r.tutorial then local pop=T.make('UIScale',tile,{Scale=0});TweenService:Create(pop,TweenInfo.new(.35,Enum.EasingStyle.Back,Enum.EasingDirection.Out,0,false,.3+.35*i),{Scale=1}):Play() end
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
  -- PLAY AGAIN (plan J item 9: a fresh run on this server with whoever presses it) beside BACK TO
  -- LOBBY, and the note under them: the countdown to the automatic return, or why PLAY AGAIN waits.
  local bw,gap=340,24;local bx=(PW-2*bw-gap)/2
  again=T.button(board,'PlayAgain','PLAY AGAIN',bx,PH-96,bw,64,function()
   if not again or not again.Interactable then return end
   combat.RunAction:FireServer('PlayAgain',player:GetAttribute('PlayAgainStatus')==nil)
  end)
  again.Caption.TextSize=28
  back=T.button(board,'BackToLobby','BACK TO LOBBY',bx+bw+gap,PH-96,bw,64,function()
   if not back or not back.Interactable then return end
   back.Interactable=false;back.Caption.Text='RETURNING...';if again then again.Interactable=false end
   combat.RunAction:FireServer('ReturnToLobby')
  end,true)
  back.Caption.TextSize=28
  -- The tutorial: no PLAY AGAIN; LOBBY is the one big button (the guide's arrow points at it).
  if r.tutorial then
   again.Visible=false
   back.Position=UDim2.fromOffset((PW-bw)/2,PH-96);T.setPrimary(back,true);back.Caption.Text='LOBBY'
  end
  -- Left with the party (LEAVE WITH PARTY, 2026-10-03): the party goes home together, so no PLAY
  -- AGAIN (the server refuses it too); BACK TO LOBBY takes everyone still on their results.
  if r.party and not r.tutorial then
   again.Visible=false
   back.Position=UDim2.fromOffset((PW-bw)/2,PH-96);T.setPrimary(back,true)
  end
  note=centred(T.label(board,'Note','',28,PH-30,PW-56,24,18,C.muted))
  paintAgain()
  if UserInputService:GetLastInputType().Name:find('^Gamepad') then pcall(function() GuiService.SelectedObject=again end) end
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
  -- The party leader ended the run (LEAVE WITH PARTY): say so up front, not just in the note.
  if type(data.notice)=='string' then T.toast(screen,data.notice,C.gold) end
  -- The countdown follows the server's clock (returnAt), so a slow client never shows it wrong.
  task.spawn(function()
   while token==mine and screen.Enabled do
    if note and player:GetAttribute('PlayAgainStatus') then paintAgain()
    elseif note and result.returnAt then
     local left=math.max(0,math.ceil(result.returnAt-workspace:GetServerTimeNow()))
     note.Text=left>0 and ('Back to the lobby in '..left..'s') or 'Returning to the lobby...'
     -- A party that left together: who ended it, and that you all go back together.
     if result.party then
      note.Text=(result.notice and (result.notice..'  ·  ') or '')..(left>0 and ('Back to the lobby with your party in '..left..'s') or 'Returning to the lobby with your party...')
      note.TextColor3=result.notice and C.gold or C.muted
     end
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

 -- Rejoin (plan J item 9): in a lobby, a run this player dropped out of that is still going (the
 -- server's RejoinOffer). A small card at the top: REJOIN goes back to it, NOT NOW forgets it.
 local offerGui=T.make('ScreenGui',player.PlayerGui,{Name='RejoinOffer',ResetOnSpawn=false,DisplayOrder=84,Enabled=false,
  ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
 local offerRoot=T.frame(offerGui,'Root',0,0,0,0);offerRoot.Size=UDim2.fromScale(1,1)
 local card
 local function drawOffer()
  if card then card:Destroy();card=nil end
  local ok,info=pcall(Http.JSONDecode,Http,player:GetAttribute('RejoinOffer') or '')
  offerGui.Enabled=ok and type(info)=='table'
  if not offerGui.Enabled then return end
  local W,H=640,info.error and 196 or 172
  local v=offerRoot.AbsoluteSize;local s=math.clamp((v.X-24)/W,.55,1)
  card=T.panel(offerRoot,'Card',0,0,W,H,'panel');card.AnchorPoint=Vector2.new(.5,0);card.Position=UDim2.new(.5,0,0,12)
  T.make('UIScale',card,{Scale=s})
  centred(T.label(card,'Title','YOUR RUN IS STILL GOING',20,14,W-40,40,32,C.gold))
  local sub=string.upper((info.mapName or 'Your run')..'  ·  '..(info.difficulty or 'Normal')..'  ·  WAVE '..tostring(info.wave or 1))
  centred(T.label(card,'Sub',sub,20,56,W-40,26,20,C.muted))
  local bh=math.max(56,math.ceil(40/s)) -- 40 px to tap on a phone
  local join
  join=T.button(card,'Rejoin','REJOIN',W/2-276,96,260,bh,function()
   if not join.Interactable then return end
   join.Interactable=false;join.Caption.Text='JOINING...'
   combat.RunAction:FireServer('Rejoin')
  end)
  join.Caption.TextSize=26
  local skip=T.button(card,'NotNow','NOT NOW',W/2+16,96,260,bh,function() combat.RunAction:FireServer('RejoinDismiss') end,true)
  skip.Caption.TextSize=24
  if info.error then centred(T.label(card,'Error',string.upper(info.error),20,96+bh+10,W-40,24,18,C.negative)) end
  card.Size=UDim2.fromOffset(W,math.max(H,96+bh+(info.error and 44 or 20)))
 end
 player:GetAttributeChangedSignal('RejoinOffer'):Connect(drawOffer)
 offerRoot:GetPropertyChangedSignal('AbsoluteSize'):Connect(function() if offerGui.Enabled then drawOffer() end end)
 drawOffer()

 -- Victory (user, 2026-10-03: "better clarification on when to leave and when the game is done
 -- (round 20)"): clearing wave 20 (RogueliteRunState.Won, RogueliteMeta) opens "YOU WON!" over the
 -- shop: LEAVE collects the rewards (results, then the lobby), KEEP GOING carries on into Endless
 -- (harder waves, emeralds every 5 more). Emeralds are paid at each clear, so they're safe either
 -- way. Shown once, when the win happens (not to someone rejoining an Endless run), and closed when
 -- the next wave starts. Never in the tutorial, which has no VICTORY banner on purpose (b22ff42).
 local victoryGui=T.make('ScreenGui',player.PlayerGui,{Name='VictoryPanel',ResetOnSpawn=false,DisplayOrder=75,
  ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
 local victoryWin
 task.spawn(function()
  local runState=RS:WaitForChild('RogueliteRunState',60);if not runState then return end
  local Rules=require(RS:WaitForChild('RunSetupRules'))
  runState:GetAttributeChangedSignal('Won'):Connect(function()
   if runState:GetAttribute('Won')~=true then if victoryWin then victoryWin.Close() end;return end
   if victoryWin or combat:GetAttribute('TutorialRun')==true or not player:GetAttribute('RunMember') or player:GetAttribute('RunResult') then return end
   local index=Rules.MapIndex[combat:GetAttribute('RunMap')]
   local sub=('WAVE %d CLEARED  ·  %s  ·  %s'):format(Rules.WinWave,string.upper(index and Rules.Maps[index].name or 'Pine Valley'),string.upper(combat:GetAttribute('RunDifficulty') or 'Normal'))
   T.sound('ui_upgrade')
   victoryWin=T.leaveConfirm(victoryGui,{victory=true,sub=sub,onClose=function() victoryWin=nil end,
    closeOn={runState:GetAttributeChangedSignal('Phase')},closeIf=function() return runState:GetAttribute('Phase')=='Combat' end})
  end)
 end)
 return M
end
return M
