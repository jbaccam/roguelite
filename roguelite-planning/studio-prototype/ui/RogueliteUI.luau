-- Reusable presentation only. No inventory, economy, damage, or reward authority.
local TweenService=game:GetService("TweenService")
local Players=game:GetService("Players")
local RS=game:GetService("ReplicatedStorage")
local Input=game:GetService("UserInputService")
local TextService=game:GetService("TextService")
local T=require(RS:WaitForChild("UITheme"))
local UI={}
local C=T.Color
local A=T.Asset
UI.Assets=A
local make,frame,panel,icon,label,button=T.make,T.frame,T.panel,T.icon,T.label,T.button
function UI.mount(playerGui)
 local player=Players.LocalPlayer
 local gui=make("ScreenGui",playerGui,{Name="RogueliteHUD",ResetOnSpawn=false,DisplayOrder=20,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets,ClipToDeviceSafeArea=true})
 local root=frame(gui,"SafeArea",0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local hud=frame(root,"HUD",0,0,0,0);hud.Size=UDim2.fromScale(1,1)
 -- Upper left: health, XP, shards.
 local health=frame(hud,"Health",20,16,382,234)
 local healthScale=make("UIScale",health,{Scale=1})
 panel(health,"HealthFrame",25,8,355,56,"inset")
 -- Red health fill over an orange damage trail in a dark track. The boss bar uses the same one.
 local function healthTrack(parent,position,size)
  local t=make("Frame",parent,{Name="Track",Position=position,Size=size,BackgroundColor3=Color3.fromRGB(34,39,43),BorderSizePixel=0,ClipsDescendants=true})
  local damage=make("Frame",t,{Name="DamageTrail",Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(248,172,104),BorderSizePixel=0})
  local f=make("Frame",t,{Name="Fill",Size=UDim2.fromScale(1,1),BackgroundColor3=C.red,BorderSizePixel=0})
  make("UIGradient",f,{Rotation=90,Color=ColorSequence.new({ColorSequenceKeypoint.new(0,Color3.fromRGB(255,109,103)),ColorSequenceKeypoint.new(0.18,Color3.fromRGB(255,45,54)),ColorSequenceKeypoint.new(0.52,Color3.fromRGB(227,22,35)),ColorSequenceKeypoint.new(1,Color3.fromRGB(165,16,27))})})
  make("Frame",f,{Name="Shine",Position=UDim2.fromOffset(0,2),Size=UDim2.new(1,0,0,2),BackgroundColor3=Color3.fromRGB(255,152,144),BackgroundTransparency=0.4,BorderSizePixel=0})
  return t,f,damage
 end
 local _,fill,trail=healthTrack(health,UDim2.fromOffset(54,20),UDim2.fromOffset(307,30))
 icon(health,"Heart",0,0,75,"heart")
 local hp=label(health,"HealthText","— / —",75,10,265,48,29)
 local low=label(health,"Warning","LOW HEALTH",92,63,250,22,16,C.red);low.Visible=false
 -- Uploaded reference atlas is decoded by Roblox at 1023x341.
 -- Mask its baked sample text/fill; preserve its frame, potion and faceted fill art.
 local xpBar=frame(health,'Experience',0,84,384,76)
 make('ImageLabel',xpBar,{Name='ReferenceFrame',BackgroundTransparency=1,Size=UDim2.fromOffset(384,76),Image=A.xp,ImageRectOffset=Vector2.new(35,75),ImageRectSize=Vector2.new(960,190)})
 local xpTrack=make('Frame',xpBar,{Name='Track',Position=UDim2.fromOffset(48,27),Size=UDim2.fromOffset(316,29),BackgroundColor3=Color3.fromRGB(22,29,32),BorderSizePixel=0,ClipsDescendants=true})
 local xpClip=make('Frame',xpTrack,{Name='Fill',Size=UDim2.fromScale(0,1),BackgroundTransparency=1,ClipsDescendants=true})
 make('ImageLabel',xpClip,{Name='FacetedFill',BackgroundTransparency=1,Size=UDim2.fromOffset(316,29),Image=A.xp,ImageRectOffset=Vector2.new(190,148),ImageRectSize=Vector2.new(240,59)})
 make('ImageLabel',xpBar,{Name='Potion',BackgroundTransparency=1,Size=UDim2.fromOffset(60,76),Image=A.xp,ImageRectOffset=Vector2.new(35,75),ImageRectSize=Vector2.new(150,190),ZIndex=3})
 local xpText=label(xpBar,'XPText','0 / 20 XP',65,27,218,29,18);xpText.ZIndex=4
 local levelText=label(xpBar,'Level','LV. 1',286,27,76,29,16);levelText.ZIndex=4
 make('Frame',xpBar,{Name='Divider',Position=UDim2.fromOffset(284,31),Size=UDim2.fromOffset(1,21),BackgroundColor3=C.muted,BackgroundTransparency=.6,BorderSizePixel=0,ZIndex=4})
 -- Banked level-ups resolve between waves; this pill only counts them.
 local pending=panel(health,'PendingLevels',0,198,240,34,'button');pending.Visible=false
 local pendingText=label(pending,'Text','',0,0,0,0,17,C.white);pendingText.Size=UDim2.fromScale(1,1)
 -- Shards and bag split the bar width evenly (same left/right edges as the bars above).
 local half=(384-8)/2
 local shardRow=panel(health,'Shards',0,158,half,34,'inset')
 icon(shardRow,'ShardIcon',10,3,28,'shard')
 local shardText=label(shardRow,'ShardBalance','0',44,2,half-54,30,20,C.cyan);shardText.TextXAlignment=Enum.TextXAlignment.Left
 local bagRow=panel(health,'Bag',half+8,158,half,34,'inset')
 icon(bagRow,'ShardBag',8,2,30,'shardBag')
 local bagText=label(bagRow,'BaggedShards','0',44,2,half-54,30,20,C.muted);bagText.TextXAlignment=Enum.TextXAlignment.Left
 -- Top centre: wave countdown between stone caps.
 local timer=panel(hud,"Timer",0,14,225,65)
 timer.AnchorPoint=Vector2.new(0.5,0);timer.Position=UDim2.new(0.5,0,0,14)
 local timerScale=make("UIScale",timer,{Scale=1})
 icon(timer,"LeftStone",-14,10,44,"stone");icon(timer,"RightStone",195,10,44,"stone")
 local timeText=label(timer,"Time","--:--",25,3,175,42,35)
 local phase=panel(timer,"Phase",43,51,139,31)
 local phaseText=label(phase,"Label","PRACTICE",8,2,123,26,17)
 -- TEST RUN tag under the phase pill: the admin panel was used, so this run pays no rewards.
 local testTag=panel(timer,"TestRun",57,86,111,26,"inset");testTag.Visible=false
 local testText=label(testTag,"Label","TEST RUN",0,0,111,26,15,C.gold)
 -- Upper right: equipped weapons and collected items.
 local build=frame(hud,'Build',0,0,330,150);build.AnchorPoint=Vector2.new(1,0)
 local buildScale=make('UIScale',build,{Scale=1})
 local weaponPanel=panel(build,'Weapons',0,0,330,78,'panel')
 local slotCells={}
 for i=1,6 do
  -- Square slots; tier II-IV tint the frame and every filled slot gets a tier badge.
  local cell=panel(weaponPanel,'Slot'..i,11+(i-1)*52,14,50,54,'inset');cell.Size=UDim2.fromOffset(50,50)
  local art=make('ImageLabel',cell,{Name='Icon',BackgroundTransparency=1,Position=UDim2.fromOffset(6,6),Size=UDim2.fromOffset(38,38),ScaleType=Enum.ScaleType.Fit,Image=''})
  slotCells[i]={cell=cell,art=art}
 end
 local itemStrip=frame(build,'Items',0,88,330,62)
 make('UIListLayout',itemStrip,{FillDirection=Enum.FillDirection.Horizontal,HorizontalAlignment=Enum.HorizontalAlignment.Right,Wraps=true,Padding=UDim.new(0,4),SortOrder=Enum.SortOrder.LayoutOrder})
 -- Boss health, bottom centre, while a boss fight is on: the health bar's red fill and damage
 -- trail in a wide inset frame with the timer's stone caps, and the boss's name on a pill over
 -- its top edge (like the timer's wave pill, flipped).
 local BOSS_W,BOSS_H=700,96
 local bossBar=frame(hud,'BossHealth',0,0,BOSS_W,BOSS_H);bossBar.AnchorPoint=Vector2.new(.5,1);bossBar.Visible=false
 local bossScale=make('UIScale',bossBar,{Scale=1})
 local bossFrame=panel(bossBar,'BarFrame',0,30,BOSS_W,62,'inset');bossFrame.Size=UDim2.new(1,0,0,62)
 T.caps(bossFrame,50)
 local _,bossFill,bossTrail=healthTrack(bossFrame,UDim2.fromOffset(32,16),UDim2.new(1,-64,0,30))
 local bossHP=label(bossFill.Parent,'HealthText','',0,0,0,0,24);bossHP.Size=UDim2.fromScale(1,1);bossHP.ZIndex=2
 local bossPlate=panel(bossBar,'NamePlate',0,0,260,40,'panel');bossPlate.AnchorPoint=Vector2.new(.5,0);bossPlate.Position=UDim2.fromScale(.5,0);bossPlate.ZIndex=2
 local bossName=label(bossPlate,'BossName','',0,0,0,0,22);bossName.Size=UDim2.fromScale(1,1);bossName.ZIndex=3;bossName.TextWrapped=false
 -- Full-screen menus (shop, upgrades).
 local overlay=make("Frame",root,{Name="Menus",Active=true,Visible=false,Size=UDim2.fromScale(1,1),BackgroundColor3=C.shade,BackgroundTransparency=0.1,BorderSizePixel=0})
 local header=panel(overlay,"Header",0,12,500,68)
 header.AnchorPoint=Vector2.new(0.5,0);header.Position=UDim2.new(0.5,0,0,12)
 T.caps(header,40)
 local title=label(header,"Title","LEVEL UP!",15,7,470,49,34)
 title.Size=UDim2.new(1,-30,1,-14);title.Position=UDim2.fromOffset(15,7)
 local note=label(overlay,"PreviewNote","",0,84,0,24,15,C.muted);note.Size=UDim2.new(1,0,0,24)
 local scroller=make("ScrollingFrame",overlay,{Name="Content",BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(12,120),Size=UDim2.new(1,-24,1,-193),CanvasSize=UDim2.new(),ScrollBarThickness=5,ScrollBarImageColor3=C.lime,ScrollingDirection=Enum.ScrollingDirection.Y})
 local content=frame(scroller,"Canvas",0,0,0,0)
 local footer=frame(overlay,"Footer",0,0,0,64);footer.AnchorPoint=Vector2.new(0.5,1);footer.Position=UDim2.new(0.5,0,1,-5);footer.Size=UDim2.new(1,-24,0,64)
 local status=label(overlay,"Status","",0,0,0,30,16,C.lime);status.AnchorPoint=Vector2.new(0.5,1);status.Position=UDim2.new(0.5,0,1,-70);status.Size=UDim2.new(1,-20,0,30);status.TextScaled=true
 make('UITextSizeConstraint',status,{MinTextSize=10,MaxTextSize=16})
 local controller={Gui=gui, HealthFill=fill, HealthText=hp, Mode=nil}
 function controller:SetShards(value,bagged)
  shardText.Text=tostring(value or 0);bagText.Text=tostring(bagged or 0)
 end
 function controller:SetPendingLevels(count)
  count=count or 0
  pending.Visible=count>0
  pendingText.Text=count==1 and 'LEVEL UP READY' or ('LEVEL UP  ×'..count)
  gui:SetAttribute('DisplayedPendingLevels',count)
 end
 local bossTween,bossTrailTween;local lastBossHealth,lastBossMax,lastBossId
 -- Where the boss bar rests and where it slides in from; layout() picks bottom centre or, on
 -- phones, under the timer (clear of the thumbstick and jump button).
 local bossAt,bossFrom=UDim2.new(.5,0,1,-24),UDim2.new(.5,0,1,116)
 function controller:SetBossHealth(npc,value,maximum)
  local visible=npc~=nil and type(value)=='number' and type(maximum)=='number' and maximum>0 and value>0
  if not visible then bossBar.Visible=false;lastBossId=nil;gui:SetAttribute('BossHealthRatio',nil);gui:SetAttribute('DisplayedBossHealth',nil);return end
  value=math.clamp(value,0,maximum)
  if npc==lastBossId and value==lastBossHealth and maximum==lastBossMax then return end
  local fresh=npc~=lastBossId
  local decreasing=not fresh and value<lastBossHealth
  lastBossId,lastBossHealth,lastBossMax=npc,value,maximum
  local ratio=value/maximum;gui:SetAttribute('BossHealthRatio',ratio);gui:SetAttribute('DisplayedBossHealth',value)
  bossHP.Text=string.format('%d / %d',math.ceil(value),math.ceil(maximum))
  if bossTween then bossTween:Cancel() end
  if bossTrailTween then bossTrailTween:Cancel() end
  if fresh then
   -- A new fight: name the boss (BossName attribute, if the model has one) and rise into place.
   local name=string.upper(tostring(npc:GetAttribute('BossName') or 'Hammer Brute'))
   bossName.Text=name
   bossPlate.Size=UDim2.fromOffset(TextService:GetTextSize(name,22,T.Font,Vector2.new(1000,100)).X+64,40)
   bossFill.Size=UDim2.fromScale(ratio,1);bossTrail.Size=bossFill.Size
   bossBar.Position=bossFrom;bossBar.Visible=true
   TweenService:Create(bossBar,TweenInfo.new(.4,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Position=bossAt}):Play()
  else
   -- Same feel as the player's bar: the fill snaps down, the orange trail drains after it.
   bossTween=TweenService:Create(bossFill,TweenInfo.new(.16,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=UDim2.fromScale(ratio,1)});bossTween:Play()
   bossTrailTween=TweenService:Create(bossTrail,TweenInfo.new(decreasing and .55 or .16,Enum.EasingStyle.Quad,Enum.EasingDirection.Out,0,false,decreasing and .12 or 0),{Size=UDim2.fromScale(ratio,1)});bossTrailTween:Play()
  end
 end
 local xpTween;local lastXP,lastLevel,lastRequired
 function controller:SetXP(value,required,level)
  value=value or 0;required=required or 20;level=level or 1
  if value==lastXP and level==lastLevel and required==lastRequired then return end
  local initial=lastXP==nil
  lastXP,lastLevel,lastRequired=value,level,required
  xpText.Text=string.format('%d / %d XP',value,required);levelText.Text='LV. '..level
  local ratio=math.clamp(value/math.max(1,required),0,1)
  gui:SetAttribute('DisplayedXP',value);gui:SetAttribute('DisplayedLevel',level);gui:SetAttribute('XPRatio',ratio)
  if xpTween then xpTween:Cancel() end
  if initial then xpClip.Size=UDim2.fromScale(ratio,1) else
   xpTween=TweenService:Create(xpClip,TweenInfo.new(.22,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=UDim2.fromScale(ratio,1)});xpTween:Play()
  end
 end
 local currentHp=0
 local fillTween,trailTween
 function controller:SetHealth(value,maximum,immediate)
  value=math.max(0,value);maximum=math.max(0,maximum)
  local ratio=maximum>0 and math.clamp(value/maximum,0,1) or 0
  local decreasing=value<currentHp and not immediate
  currentHp=value
  hp.Text=string.format("%d / %d",math.ceil(value),math.ceil(maximum))
  low.Visible=ratio>0 and ratio<=0.25
  gui:SetAttribute("DisplayedHealth",value);gui:SetAttribute("DisplayedMaxHealth",maximum);gui:SetAttribute("HealthRatio",ratio)
  if fillTween then fillTween:Cancel() end
  if trailTween then trailTween:Cancel() end
  if immediate then fill.Size=UDim2.fromScale(ratio,1);trail.Size=fill.Size
  else
   fillTween=TweenService:Create(fill,TweenInfo.new(0.16,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=UDim2.fromScale(ratio,1)});fillTween:Play()
   trailTween=TweenService:Create(trail,TweenInfo.new(decreasing and 0.55 or 0.16,Enum.EasingStyle.Quad,Enum.EasingDirection.Out,0,false,decreasing and 0.12 or 0),{Size=UDim2.fromScale(ratio,1)});trailTween:Play()
  end
 end
 function controller:SetTimer(seconds,wave,phaseName,label)
  if label then timeText.Text=label
  elseif seconds then local s=math.max(0,math.ceil(seconds));timeText.Text=string.format("%02d:%02d",math.floor(s/60),s%60) else timeText.Text="--:--" end
  phaseText.Text=wave and ("WAVE "..tostring(wave)) or string.upper(phaseName or "PRACTICE")
 end
 function controller:SetTestRun(on)
  testTag.Visible=on==true;gui:SetAttribute("TestRunShown",on==true)
 end
 local render
 local shopView
 local levelUpView
 local settingsWindow
 local function close()
  local wasOpen=overlay.Visible
  overlay.Visible=false;hud.Visible=true;controller.Mode=nil;gui:SetAttribute("PreviewScreen",nil)
  T.hideTouchControls('RogueliteMenu',false)
  if wasOpen then
   -- Only drop the controller selection the menu owned (not the level-up or death screen's).
   pcall(function() game:GetService("GuiService").SelectedObject=nil end)
   -- Always hand preview input back to the normal Roblox character camera.
   -- No saved CameraSubject: it may belong to a character that has respawned.
   local humanoid=player.Character and player.Character:FindFirstChildOfClass("Humanoid")
   local camera=workspace.CurrentCamera
   if camera and humanoid then
    camera.CameraSubject=humanoid
    camera.CameraType=Enum.CameraType.Custom
   end
   Input.MouseBehavior=Enum.MouseBehavior.Default
   Input.MouseIconEnabled=true
  end
 end
 function controller:Close() close();if settingsWindow then settingsWindow.Close() end end
 local shopTab=button(footer,"ShopTab","Shop",0,8,120,48,function() controller:ShowPreview("Shop") end,true)
 local upgradesTab=button(footer,"UpgradesTab","Upgrades",130,8,140,48,function() controller:ShowPreview("Upgrades") end,true)
 local closeButton=button(footer,"Close","Back to game",280,8,210,48,close,true)
 -- The Shop / Upgrades / Back to game row is hidden (user, 2026-09-29): the shop opens and
 -- closes with the phase, and during a wave SHOP and B toggle the view.
 footer.Visible=false
 -- A modal button frees the first-person cursor only while it is visible, so the overlay
 -- carries its own empty one now that closeButton is hidden.
 local cursorFree=Instance.new('TextButton');cursorFree.Name='CursorFree';cursorFree.Text=''
 cursorFree.BackgroundTransparency=1;cursorFree.Size=UDim2.new();cursorFree.Selectable=false
 cursorFree.Modal=true;cursorFree.Parent=overlay
 local tabModes={Shop=shopTab,Upgrades=upgradesTab}
 local helpers={panel=panel,label=label,button=button,icon=icon}
 local shopModule=require(RS:WaitForChild('ShopUI'))
 shopView=shopModule.new(player,helpers,function() if render and controller.Mode=='Shop' then render() end end)
 function controller:SetStats() end -- RogueliteHUD still calls this; stat edits live in the ADMIN panel.
 -- Right edge: menu launchers. The ADMIN button (developers only) is AdminPanel.client's, at
 -- LayoutOrder 5 after SETTINGS; the old GEAR and STATS test tools moved into that panel.
 -- layout() stacks them down the right edge, or lays them in a row under the build strip when
 -- the column would reach the jump button (phones).
 local menu=frame(hud,'Menu',0,0,76,300);menu.AnchorPoint=Vector2.new(1,0)
 local menuScale=make('UIScale',menu,{Scale=1})
 local menuList=make('UIListLayout',menu,{Padding=UDim.new(0,6),HorizontalAlignment=Enum.HorizontalAlignment.Center,SortOrder=Enum.SortOrder.LayoutOrder})
 local function launcher(name,asset,caption,order,fn)
  local b=T.iconButton(menu,name,asset,caption,58,fn);b.LayoutOrder=order;return b
 end
 -- Toggle: with the footer gone, the same button (and B) closes a mid-wave shop view.
 -- Between waves the shop stays open; START WAVE closes it.
 local function toggleShop()
  if player:GetAttribute('RunDown') then return end -- not under the death screen
  local phase=(shopView:snapshot() or {}).phase
  if overlay.Visible and controller.Mode=='Shop' and phase~='Shop' then close() else controller:ShowPreview('Shop') end
 end
 launcher('OpenShop','store','SHOP',1,toggleShop)
 launcher('SettingsButton','settings','SETTINGS',4,function()
  if settingsWindow then settingsWindow.Close() return end
  settingsWindow=T.settingsWindow(gui)
  settingsWindow.Root.Destroying:Connect(function() settingsWindow=nil end)
 end)
 -- B on keyboard, X on a controller (X is unbound in runs; a selected menu button may mark it processed).
 Input.InputBegan:Connect(function(input,processed)
  if Input:GetFocusedTextBox() then return end
  if (input.KeyCode==Enum.KeyCode.B and not processed) or input.KeyCode==Enum.KeyCode.ButtonX then toggleShop() end
 end)
 -- Build strip: live server slots plus snapshot items.
 local Catalog=require(RS.RogueliteCombat.ShopCatalog)
 local weaponIcons=require(RS.WeaponInventoryUI).Icons
 -- The strip shows at most three rows of seven (layout() keeps the menu below them); past that
 -- the last cell becomes a "+N" chip.
 local MAX_ITEM_CELLS=21
 local buildS=.9 -- the build strip's on-screen scale, set by layout()
 -- Small labels grow on small HUD scales so they draw at least 10 px: at scale .55 a 13 px
 -- count becomes 19 (10.5 px on screen).
 local function readableSize(base,scale) return math.max(base,math.ceil(10/scale)) end
 local function drawBuild()
  local state=shopView.state
  for i,cell in slotCells do
   local slot=state:FindFirstChild('Slot'..i)
   local id=slot and slot:GetAttribute('WeaponId') or ''
   local tier=slot and slot:GetAttribute('Tier') or 1
   cell.art.Image=id~='' and (weaponIcons[id] or '') or ''
   cell.cell.Image=A.inset;cell.cell.ImageColor3=Color3.new(1,1,1)
   T.setTier(cell.cell,id~='' and tier or 1) -- tier 1 also clears an emptied slot's old corners
   cell.cell.ImageTransparency=id~='' and 0 or .35
   local old=cell.cell:FindFirstChild('TierBadge');if old then old:Destroy() end
   if id~='' then
    local badge=T.tierBadge(cell.cell,tier,52,52,Vector2.new(1,1))
    local size=readableSize(15,buildS)
    if size>15 then badge.Size=UDim2.fromOffset(math.round(badge.Size.X.Offset*size/15),math.round(badge.Size.Y.Offset*size/15));local t=badge:FindFirstChild('Tier');if t then t.TextSize=size end end
   end
  end
  for _,c in itemStrip:GetChildren() do if c:IsA('GuiObject') then c:Destroy() end end
  local data=shopView:snapshot()
  local list={}
  for _,it in (data and data.items or {}) do
   local entry=Catalog.ById[it.id]
   if entry then table.insert(list,{it=it,entry=entry}) end
  end
  local shown=#list>MAX_ITEM_CELLS and MAX_ITEM_CELLS-1 or #list
  local countSize=readableSize(13,buildS)
  for i=1,shown do
   local it,entry=list[i].it,list[i].entry
   local cell=panel(itemStrip,'Item'..i,0,0,38,38,'inset');cell.LayoutOrder=i;T.setTier(cell,entry.tier)
   icon(cell,'Icon',4,4,30,A[entry.icon] or entry.icon)
   if it.count>1 then local n=label(cell,'Count','×'..it.count,0,38-math.max(18,countSize+3),36,math.max(18,countSize+3),countSize);n.TextXAlignment=Enum.TextXAlignment.Right end
  end
  if #list>shown then
   local more=panel(itemStrip,'More',0,0,38,38,'inset');more.LayoutOrder=MAX_ITEM_CELLS
   label(more,'Count','+'..(#list-shown),2,2,34,34,readableSize(18,buildS))
  end
 end
 -- Attack clocks, aim and motion attributes change continuously; only identity
 -- and tier affect these cells. Coalesce a shop action's multiple slot changes.
 local buildQueued=false
 local function queueBuild()
  if buildQueued then return end
  buildQueued=true
  task.defer(function() buildQueued=false;drawBuild() end)
 end
 shopView.state:GetAttributeChangedSignal('ShopSnapshot'):Connect(queueBuild)
 shopView.state:GetAttributeChangedSignal('PendingLevelUps'):Connect(function() controller:SetPendingLevels(shopView.state:GetAttribute('PendingLevelUps')) end)
 for i=1,6 do
  local slot=shopView.state:WaitForChild('Slot'..i,5)
  if slot then
   slot:GetAttributeChangedSignal('WeaponId'):Connect(queueBuild)
   slot:GetAttributeChangedSignal('Tier'):Connect(queueBuild)
  end
 end
 controller:SetPendingLevels(shopView.state:GetAttribute('PendingLevelUps'))
 render=function()
  if not controller.Mode then return end
  local settings=shopModule.getLayout()
  local isShop=controller.Mode=='Shop'
  local inset=game:GetService('GuiService'):GetGuiInset().Y
  -- Extend the menu backdrop into the top inset, while keeping buttons below Roblox's bar.
  overlay.Position=UDim2.fromOffset(0,-inset);overlay.Size=UDim2.new(1,0,1,inset)
  overlay.BackgroundTransparency=isShop and 0 or .1 -- Shop is opaque so Studio test panels never show through.
  local margin=isShop and math.floor(root.AbsoluteSize.X*settings.HorizontalMargin) or 12
  -- Short screens (phones) give the shop nearly the full height: 4 px on top, and a 32 px band
  -- under it for the status line (a 311 px phone gets 275 px of shop instead of 185).
  local short=isShop and root.AbsoluteSize.Y<450
  local top=isShop and (short and 4 or 46)+inset or 88+inset
  local band=short and 32 or 80
  scroller.Position=UDim2.fromOffset(margin,top);scroller.Size=UDim2.new(1,-margin*2,1,-top-band)
  -- The status line sits in that band, below the shop (and its START WAVE button), never over it.
  local statusH=short and 24 or 30
  status.Size=UDim2.new(1,-20,0,statusH);status.Position=UDim2.new(.5,0,1,-math.floor((band-statusH)/2))
  local path=T.selectionPath(content) -- a controller's selection survives the redraw
  header.Position=UDim2.new(.5,0,0,settings.HeaderTop+inset)
  note.Position=UDim2.fromOffset(0,62+inset)
  header.Visible=not isShop;note.Visible=not isShop
  for mode,b in tabModes do T.setPrimary(b,mode==controller.Mode) end
  content:ClearAllChildren()
  local width=math.max(260,scroller.AbsoluteSize.X-(isShop and 0 or 10))
  scroller.ScrollingEnabled=controller.Mode~='Shop'
  if isShop then
   -- The scroller's size from the root (its AbsoluteSize can lag a frame behind a resize).
   local viewW,viewH=math.max(260,root.AbsoluteSize.X-margin*2),root.AbsoluteSize.Y+inset-top-band
   content.Size=UDim2.fromOffset(viewW,viewH);scroller.CanvasSize=UDim2.new()
   local data=shopView:render(content,viewW,viewH,false)
   if data then status.Text=data.message end
   T.restoreSelection(content,path)
   return
  end
  local pendingCount=(shopView:snapshot() or {}).pendingLevels or 0
  local box=panel(content,'NoUpgrades',math.max(0,(width-560)/2),30,math.min(560,width),150)
  label(box,'Text',pendingCount>0 and 'Choose your earned upgrades' or 'Collect crystals to earn XP.\nStat upgrade offers open between waves.',20,20,math.min(560,width)-40,110,24)
  content.Size=UDim2.fromOffset(width,200);scroller.CanvasSize=UDim2.fromOffset(0,200)
 end
 function controller:ShowPreview(mode)
  if levelUpView and levelUpView:Show() then return end
  if settingsWindow then settingsWindow.Close() end
  controller.Mode=mode;title.Text=mode=='Shop' and 'SHOP' or 'LEVEL UP!'
  note.Text=mode=='Shop' and '' or 'Upgrade offers appear here between waves'
  overlay.Visible=true;hud.Visible=false;status.Text=""
  gui:SetAttribute("PreviewScreen",mode)
  T.hideTouchControls('RogueliteMenu',true) -- the jump button would sit over the shop's buttons
  scroller.CanvasPosition=Vector2.zero;render()
  -- A controller starts on the shop's first button (no change for mouse and touch).
  T.gamepadSelect(content)
 end
 -- Touch play: Roblox's preferred-input signal where the engine has it, else the last input used.
 local function touchPlay()
  local ok,touch=pcall(function() return Input.PreferredInput==Enum.PreferredInput.Touch end)
  if ok then return touch end
  local last=Input:GetLastInputType()
  if last==Enum.UserInputType.Touch then return true end
  if last==Enum.UserInputType.None or last==Enum.UserInputType.Focus then return Input.TouchEnabled and not Input.KeyboardEnabled end
  return false
 end
 -- Jump button and thumbstick rest areas, {x0,y0,x1,y1} in root pixels. The jump button is read
 -- from Roblox's TouchGui when showing; else its defaults: 70 px, 25 px in from the bottom-right
 -- corner when the short side is 500 px or less (phones), 120 px on tablets.
 local function touchZones(w,h)
  local small=math.min(w,h)<=500
  local jump=small and {w-95,h-90,w-25,h-20} or {w-170,h-210,w-50,h-90}
  local stick=small and {0,h-150,170,h} or {0,h-260,260,h}
  local touchGui=player:FindFirstChild('PlayerGui') and player.PlayerGui:FindFirstChild('TouchGui')
  local frame=touchGui and touchGui:FindFirstChild('TouchControlFrame')
  local button=frame and frame:FindFirstChild('JumpButton')
  if button and button:IsA('GuiObject') and button.Visible and button.AbsoluteSize.X>0 then
   local p=button.AbsolutePosition-root.AbsolutePosition;local sz=button.AbsoluteSize
   jump={p.X,p.Y,p.X+sz.X,p.Y+sz.Y}
  end
  return jump,stick
 end
 local function overlaps(a,b,gap) return math.min(a[3],b[3])-math.max(a[1],b[1])>-gap and math.min(a[4],b[4])-math.max(a[2],b[2])>-gap end
 local lastBuildS,lastTouch
 local function layout()
  local w,h=root.AbsoluteSize.X,root.AbsoluteSize.Y
  if w<2 or h<2 then return end
  local touch=touchPlay();lastTouch=touch
  -- One HUD scale from the root's width and height, times the HUD size setting: 1 on desktops,
  -- .55 on a 750x311 phone (311/620 = .50, raised to .55 so text stays about 10 px).
  local scale=math.clamp(math.min(w/1100,h/620),.55,1)*T.setting('HudScale')
  -- Never so big that the health block reaches the timer: 12+384s+12 <= w/2-126.5s, so on a
  -- 1024 px tablet the Large setting stops at .96.
  scale=math.min(math.max(scale,.55),(w/2-24)/510.5)
  -- Build strip: .9 of that, but not below .55 so its tier badges and counts stay readable.
  buildS=math.max(scale*.9,math.min(scale,.55))
  local ms=math.clamp(scale,.7,1.1) -- launchers stay at least 40 px to tap
  healthScale.Scale=scale;timerScale.Scale=scale;buildScale.Scale=buildS;menuScale.Scale=ms;bossScale.Scale=scale
  for _,l in {{low,16},{levelText,16},{xpText,18},{phaseText,17},{testText,15},{pendingText,17}} do l[1].TextSize=readableSize(l[2],scale) end
  health.Position=UDim2.fromOffset(12,12)
  timer.Position=UDim2.new(0.5,0,0,14)
  build.AnchorPoint=Vector2.new(1,0);build.Position=UDim2.new(1,-12,0,12)
  local healthRight,buildLeft=12+384*scale,w-12-330*buildS
  local buildBottom=12+210*buildS -- weapons plus three item rows (MAX_ITEM_CELLS)
  local jump,stick=touchZones(w,h)
  local zones=touch and {jump,stick} or {}
  local function clear(r)
   if r[4]>h-8 then return false end
   for _,z in zones do if overlaps(r,z,8) then return false end end
   return true
  end
  -- Menu launchers: a column down the right edge (where it always was on desktops) that starts
  -- below the build strip; a row under the strip when the column would reach the jump button or
  -- the bottom edge (phones).
  local n=0;for _,c in menu:GetChildren() do if c:IsA('GuiButton') and c.Visible then n+=1 end end
  n=math.max(n,1)
  local top=math.max(.52*h-150*ms,buildBottom+10)
  local menuRect={w-10-76*ms,top,w-10,top+(80*n+6*(n-1))*ms}
  local vertical=clear(menuRect)
  if vertical then
   menuList.FillDirection=Enum.FillDirection.Vertical;menuList.Padding=UDim.new(0,6);menuList.HorizontalAlignment=Enum.HorizontalAlignment.Center
   menu.Size=UDim2.fromOffset(76,80*n+6*(n-1));menu.Position=UDim2.new(1,-10,0,top)
  else
   -- 44 apart: the captions are wider than the icons and must not touch.
   top=buildBottom+10
   local width=58*n+44*(n-1)
   menuList.FillDirection=Enum.FillDirection.Horizontal;menuList.Padding=UDim.new(0,44);menuList.HorizontalAlignment=Enum.HorizontalAlignment.Right
   menu.Size=UDim2.fromOffset(width,80);menu.Position=UDim2.new(1,-10-9*ms,0,top)
   menuRect={w-10-18*ms-width*ms,top,w-10,top+80*ms}
  end
  -- Boss bar (700x96 at the HUD scale). Short screens (phones): under the timer, between the
  -- health block and the build strip. Taller screens: bottom centre, narrowed to clear the touch
  -- controls and the menu. When the preferred spot is under 240 px wide, the wider of the two.
  local function topSlot()
   local y=14+112*scale+6
   local half=math.min(350*scale,w/2-healthRight-10,buildLeft-10-w/2)
   if not vertical and menuRect[2]<y+96*scale then half=math.min(half,menuRect[1]-10-w/2) end
   return {half,UDim2.new(.5,0,0,y),Vector2.new(.5,0),UDim2.new(.5,0,0,y-140)}
  end
  local function bottomSlot()
   local half=math.min(350*scale,w/2-16)
   local y0,y1=h-24-96*scale,h-24
   for _,z in zones do
    if z[2]<y1 and z[4]>y0 then
     if z[1]+z[3]<w then half=math.min(half,w/2-z[3]-10) else half=math.min(half,z[1]-10-w/2) end
    end
   end
   if menuRect[4]>y0 then half=math.min(half,menuRect[1]-10-w/2) end
   return {half,UDim2.new(.5,0,1,-24),Vector2.new(.5,1),UDim2.new(.5,0,1,116)}
  end
  local first,second=topSlot(),bottomSlot()
  if h>=500 then first,second=second,first end
  local pick=(first[1]*2>=240 or first[1]>=second[1]) and first or second
  bossBar.Size=UDim2.fromOffset(math.max(100,pick[1]*2/scale),BOSS_H)
  bossBar.AnchorPoint=pick[3];bossAt,bossFrom=pick[2],pick[4]
  bossBar.Position=bossAt
  header.Size=UDim2.fromOffset(math.min(500,w-28),46)
  note.TextSize=12
  title.TextSize=26
  local footerWidth=math.min(660,w-24)
  footer.Size=UDim2.fromOffset(footerWidth,64)
  local bw=(footerWidth-16)/3
  for i,b in {shopTab,upgradesTab,closeButton} do
   b.Position=UDim2.fromOffset((i-1)*(bw+8),8);b.Size=UDim2.fromOffset(bw,48);b.Caption.TextSize=w<600 and 12 or 18
  end
  if buildS~=lastBuildS then lastBuildS=buildS;drawBuild() end -- badge and count sizes follow the scale
  render()
 end
 root:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
 player:GetAttributeChangedSignal('Setting_HudScale'):Connect(layout)
 -- Touch clearance follows the input in use (a touch laptop switches when the screen is touched);
 -- the ADMIN launcher and Roblox's TouchGui arrive after mount.
 local function inputChanged() if touchPlay()~=lastTouch then layout() end end
 Input.LastInputTypeChanged:Connect(inputChanged)
 pcall(function() Input:GetPropertyChangedSignal('PreferredInput'):Connect(inputChanged) end)
 menu.ChildAdded:Connect(function() task.defer(layout) end)
 menu.ChildRemoved:Connect(function() task.defer(layout) end)
 player:WaitForChild('PlayerGui').ChildAdded:Connect(function(c) if c.Name=='TouchGui' then task.delay(.5,layout) end end)
 -- AbsoluteSize settles after parent layout; redraw using the resolved viewport.
 scroller:GetPropertyChangedSignal("AbsoluteSize"):Connect(function() task.defer(render) end)
 -- Purchase results (rerolls, revive) as a toast.
 RS.RogueliteCombat:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(_,ok,message)
  if gui.Enabled and type(message)=='string' then T.toast(gui,message,ok and C.lime or C.negative) end
 end)
 require(RS:WaitForChild('DeathScreenUI')).mount(player)
 local levelMount=require(RS:WaitForChild('LevelUpUI'))
 levelUpView=levelMount.mount(player,function() close() end,function(phaseNow) if phaseNow=='Shop' then controller:ShowPreview('Shop') end end)
 local lastPhase=nil
 local function phaseChanged()
  local data=shopView:snapshot();if not data then return end
  if data.phase~=lastPhase then
   lastPhase=data.phase
   -- Sandbox (phase Practice) has no shop: close any open menu, as a wave start does.
   if data.phase=='Shop' then controller:ShowPreview('Shop') elseif data.phase=='Combat' or data.phase=='Practice' then close() end
  end
 end
 shopView.state:GetAttributeChangedSignal('ShopSnapshot'):Connect(phaseChanged)
 task.defer(phaseChanged)
 task.defer(drawBuild)
 task.defer(layout)
 return controller
end
return UI
