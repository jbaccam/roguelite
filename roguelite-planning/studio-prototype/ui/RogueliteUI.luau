-- Reusable presentation only. No inventory, economy, damage, or reward authority.
local TweenService=game:GetService("TweenService")
local Players=game:GetService("Players")
local RS=game:GetService("ReplicatedStorage")
local Input=game:GetService("UserInputService")
local T=require(RS:WaitForChild("UITheme"))
local UI={}
local C=T.Color
local A=T.Asset
UI.Assets=A
local make,frame,panel,icon,label,button=T.make,T.frame,T.panel,T.icon,T.label,T.button
function UI.mount(playerGui, studioPreview)
 local player=Players.LocalPlayer
 local gui=make("ScreenGui",playerGui,{Name="RogueliteHUD",ResetOnSpawn=false,DisplayOrder=20,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets,ClipToDeviceSafeArea=true})
 local root=frame(gui,"SafeArea",0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local hud=frame(root,"HUD",0,0,0,0);hud.Size=UDim2.fromScale(1,1)
 -- Upper left: health, XP, shards.
 local health=frame(hud,"Health",20,16,382,234)
 local healthScale=make("UIScale",health,{Scale=1})
 panel(health,"HealthFrame",25,8,355,56,"inset")
 local track=make("Frame",health,{Name="Track",Position=UDim2.fromOffset(54,20),Size=UDim2.fromOffset(307,30),BackgroundColor3=Color3.fromRGB(34,39,43),BorderSizePixel=0,ClipsDescendants=true})
 local trail=make("Frame",track,{Name="DamageTrail",Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(248,172,104),BorderSizePixel=0})
 local fill=make("Frame",track,{Name="Fill",Size=UDim2.fromScale(1,1),BackgroundColor3=C.red,BorderSizePixel=0})
 make("UIGradient",fill,{Rotation=90,Color=ColorSequence.new({ColorSequenceKeypoint.new(0,Color3.fromRGB(255,109,103)),ColorSequenceKeypoint.new(0.18,Color3.fromRGB(255,45,54)),ColorSequenceKeypoint.new(0.52,Color3.fromRGB(227,22,35)),ColorSequenceKeypoint.new(1,Color3.fromRGB(165,16,27))})})
 make("Frame",fill,{Name="Shine",Position=UDim2.fromOffset(0,2),Size=UDim2.new(1,0,0,2),BackgroundColor3=Color3.fromRGB(255,152,144),BackgroundTransparency=0.4,BorderSizePixel=0})
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
 label(testTag,"Label","TEST RUN",0,0,111,26,15,C.gold)
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
 -- Boss health, bottom centre.
 local bossBar=panel(hud,'BossHealth',0,0,460,68,'inset')
 bossBar.AnchorPoint=Vector2.new(.5,1);bossBar.Position=UDim2.new(.5,0,1,-88);bossBar.Visible=false
 local bossName=label(bossBar,'BossName','HAMMER BRUTE',14,5,432,24,20)
 bossName.Size=UDim2.new(1,-28,0,24)
 local bossTrack=make('Frame',bossBar,{Name='Track',Position=UDim2.fromOffset(18,34),Size=UDim2.new(1,-36,0,20),BackgroundColor3=Color3.fromRGB(40,28,32),BorderSizePixel=0,ClipsDescendants=true})
 local bossFill=make('Frame',bossTrack,{Name='Fill',Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(205,38,44),BorderSizePixel=0})
 make('UIGradient',bossFill,{Rotation=90,Color=ColorSequence.new(Color3.fromRGB(246,77,66),Color3.fromRGB(141,20,31))})
 local bossHP=label(bossTrack,'HealthText','',0,0,100,20,15);bossHP.Size=UDim2.fromScale(1,1);bossHP.ZIndex=2
 -- Full-screen menus (shop, inventory, stats, upgrades).
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
 local bossTween;local lastBossHealth,lastBossMax,lastBossId
 function controller:SetBossHealth(npc,value,maximum)
  local visible=npc~=nil and type(value)=='number' and type(maximum)=='number' and maximum>0 and value>0
  bossBar.Visible=visible
  if not visible then lastBossId=nil;gui:SetAttribute('BossHealthRatio',nil);gui:SetAttribute('DisplayedBossHealth',nil);return end
  value=math.clamp(value,0,maximum)
  if npc==lastBossId and value==lastBossHealth and maximum==lastBossMax then return end
  local fresh=npc~=lastBossId;lastBossId,lastBossHealth,lastBossMax=npc,value,maximum
  local ratio=value/maximum;gui:SetAttribute('BossHealthRatio',ratio);gui:SetAttribute('DisplayedBossHealth',value)
  bossHP.Text=string.format('%d / %d',math.ceil(value),math.ceil(maximum))
  if bossTween then bossTween:Cancel() end
  if fresh then bossFill.Size=UDim2.fromScale(ratio,1) else bossTween=TweenService:Create(bossFill,TweenInfo.new(.16),{Size=UDim2.fromScale(ratio,1)});bossTween:Play() end
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
 local creativeInventory
 local levelUpView
 local settingsWindow
 local function close()
  local wasOpen=overlay.Visible
  overlay.Visible=false;hud.Visible=true;controller.Mode=nil;gui:SetAttribute("PreviewScreen",nil)
  game:GetService("GuiService").SelectedObject=nil
  if wasOpen then
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
 local inventoryTab=button(footer,"InventoryTab","Inventory",0,8,140,48,function() controller:ShowPreview("Inventory") end,true)
 local statsTab=button(footer,'StatsTab','Stats',0,8,100,48,function() controller:ShowPreview('Stats') end,true)
 local closeButton=button(footer,"Close","Back to game",280,8,210,48,close,true)
 closeButton.Modal=true -- Only while its menu is visible; releases first-person cursor.
 local tabModes={Shop=shopTab,Upgrades=upgradesTab,Inventory=inventoryTab,Stats=statsTab}
 local helpers={panel=panel,label=label,button=button,icon=icon}
 local statsView=require(RS:WaitForChild('CharacterStatsUI')).new(player,helpers)
 local shopModule=require(RS:WaitForChild('ShopUI'))
 shopView=shopModule.new(player,helpers,function() if render and (controller.Mode=='Shop' or controller.Mode=='Inventory') then render() elseif controller.Mode=='Stats' then local data=shopView:snapshot();if data then status.Text=data.message end end end)
 creativeInventory=require(RS:WaitForChild('WeaponInventoryUI')).new(player,helpers,function() if render and controller.Mode=='Inventory' then task.defer(render) end end)
 function controller:SetStats() end -- Stats render from live server attributes inside the Stats view.
 -- Right edge: menu launchers. Inventory and Stats are Studio test tools.
 local menu=frame(hud,'Menu',0,0,76,300);menu.AnchorPoint=Vector2.new(1,.5)
 local menuScale=make('UIScale',menu,{Scale=1})
 make('UIListLayout',menu,{Padding=UDim.new(0,6),HorizontalAlignment=Enum.HorizontalAlignment.Center,SortOrder=Enum.SortOrder.LayoutOrder})
 local function launcher(name,asset,caption,order,fn)
  local b=T.iconButton(menu,name,asset,caption,58,fn);b.LayoutOrder=order;return b
 end
 launcher('OpenShop','store','SHOP',1,function() controller:ShowPreview('Shop') end)
 if studioPreview then
  launcher('InventoryButton','loadout','GEAR',2,function() controller:ShowPreview('Inventory') end)
  launcher('StatsButton','profile','STATS',3,function() controller:ShowPreview('Stats') end)
 end
 launcher('SettingsButton','settings','SETTINGS',4,function()
  if settingsWindow then settingsWindow.Close() return end
  settingsWindow=T.settingsWindow(gui)
  settingsWindow.Root.Destroying:Connect(function() settingsWindow=nil end)
 end)
 Input.InputBegan:Connect(function(input,processed)
  if processed or Input:GetFocusedTextBox() then return end
  if input.KeyCode==Enum.KeyCode.B then controller:ShowPreview('Shop')
  elseif studioPreview and input.KeyCode==Enum.KeyCode.I then if controller.Mode=='Inventory' then close() else controller:ShowPreview('Inventory') end
  elseif studioPreview and input.KeyCode==Enum.KeyCode.P then if controller.Mode=='Stats' then close() else controller:ShowPreview('Stats') end end
 end)
 -- Build strip: live server slots plus snapshot items.
 local Catalog=require(RS.RogueliteCombat.ShopCatalog)
 local weaponIcons=require(RS.WeaponInventoryUI).Icons
 local function drawBuild()
  local state=shopView.state
  for i,cell in slotCells do
   local slot=state:FindFirstChild('Slot'..i)
   local id=slot and slot:GetAttribute('WeaponId') or ''
   local tier=slot and slot:GetAttribute('Tier') or 1
   cell.art.Image=id~='' and (weaponIcons[id] or '') or ''
   cell.cell.Image=A.inset;cell.cell.ImageColor3=Color3.new(1,1,1)
   if id~='' then T.setTier(cell.cell,tier) end
   cell.cell.ImageTransparency=id~='' and 0 or .35
   local old=cell.cell:FindFirstChild('TierBadge');if old then old:Destroy() end
   if id~='' then T.tierBadge(cell.cell,tier,52,52,Vector2.new(1,1)) end
  end
  for _,c in itemStrip:GetChildren() do if c:IsA('GuiObject') then c:Destroy() end end
  local data=shopView:snapshot()
  for i,it in (data and data.items or {}) do
   local entry=Catalog.ById[it.id]
   if entry and i<=16 then
    local cell=panel(itemStrip,'Item'..i,0,0,38,38,'inset');cell.LayoutOrder=i;T.setTier(cell,entry.tier)
    icon(cell,'Icon',4,4,30,A[entry.icon] or entry.icon)
    if it.count>1 then local n=label(cell,'Count','×'..it.count,0,20,36,18,13);n.TextXAlignment=Enum.TextXAlignment.Right end
   end
  end
 end
 shopView.state:GetAttributeChangedSignal('ShopSnapshot'):Connect(drawBuild)
 shopView.state:GetAttributeChangedSignal('PendingLevelUps'):Connect(function() controller:SetPendingLevels(shopView.state:GetAttribute('PendingLevelUps')) end)
 for i=1,6 do
  local slot=shopView.state:WaitForChild('Slot'..i,5)
  if slot then slot.AttributeChanged:Connect(function() task.defer(drawBuild) end) end
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
  local top=isShop and 46+inset or 88+inset
  scroller.Position=UDim2.fromOffset(margin,top);scroller.Size=UDim2.new(1,-margin*2,1,-top-80)
  header.Position=UDim2.new(.5,0,0,settings.HeaderTop+inset)
  note.Position=UDim2.fromOffset(0,62+inset)
  header.Visible=not isShop;note.Visible=not isShop
  for mode,b in tabModes do T.setPrimary(b,mode==controller.Mode) end
  content:ClearAllChildren()
  local width=math.max(260,scroller.AbsoluteSize.X-(isShop and 0 or 10))
  scroller.ScrollingEnabled=controller.Mode~='Shop'
  if controller.Mode=='Inventory' then
   local height=creativeInventory:render(content,width)
   if width>=850 then content.EquippedWeapons.Position=UDim2.fromOffset(content.EquippedWeapons.Position.X.Offset,scroller.CanvasPosition.Y) end
   content.Size=UDim2.fromOffset(width,height);scroller.CanvasSize=UDim2.fromOffset(0,height)
   title.Text='CREATIVE INVENTORY';note.Text='Studio test tool  ·  Choose a slot  ·  Equip any weapon for free  ·  Duplicates allowed'
   return
  end
  if isShop then
   content.Size=UDim2.fromOffset(width,scroller.AbsoluteSize.Y);scroller.CanvasSize=UDim2.new()
   local data=shopView:render(content,width,scroller.AbsoluteSize.Y,false)
   if data then status.Text=data.message end
   return
  end
  if controller.Mode=='Stats' then
   local offset=shopView:debug(content,width)
   local inner=frame(content,'StatEditor',0,offset,width,1)
   local height=statsView:render(inner,width)+offset;inner.Size=UDim2.fromOffset(width,height-offset);content.Size=UDim2.fromOffset(width,height);scroller.CanvasSize=UDim2.fromOffset(0,height);return
  end
  local pendingCount=(shopView:snapshot() or {}).pendingLevels or 0
  local box=panel(content,'NoUpgrades',math.max(0,(width-560)/2),30,math.min(560,width),150)
  label(box,'Text',pendingCount>0 and 'Choose your earned upgrades' or 'Collect crystals to earn XP.\nStat upgrade offers open between waves.',20,20,math.min(560,width)-40,110,24)
  content.Size=UDim2.fromOffset(width,200);scroller.CanvasSize=UDim2.fromOffset(0,200)
 end
 function controller:ShowPreview(mode)
  if levelUpView and levelUpView:Show() then return end
  if settingsWindow then settingsWindow.Close() end
  controller.Mode=mode;title.Text=mode=='Stats' and 'CHARACTER STATS' or mode=='Inventory' and 'WEAPON INVENTORY' or (mode=='Shop' and 'SHOP' or 'LEVEL UP!')
  note.Text=mode=='Stats' and 'STUDIO PRACTICE  ·  Server-applied edits  ·  No saved rewards' or mode=='Inventory' and 'Owned weapons and items' or mode=='Shop' and '' or 'Upgrade offers appear here between waves'
  overlay.Visible=true;hud.Visible=false;status.Text=""
  gui:SetAttribute("PreviewScreen",mode)
  scroller.CanvasPosition=Vector2.zero;render()
  if Input:GetLastInputType()==Enum.UserInputType.Gamepad1 then
   game:GetService("GuiService").SelectedObject=closeButton
  end
 end
 scroller:GetPropertyChangedSignal('CanvasPosition'):Connect(function()
  local slots=content:FindFirstChild('EquippedWeapons')
  if controller.Mode=='Inventory' and slots and scroller.AbsoluteSize.X-10>=850 then slots.Position=UDim2.fromOffset(slots.Position.X.Offset,scroller.CanvasPosition.Y) end
 end)
 local function layout()
  local w=root.AbsoluteSize.X
  local compact=w<720
  local scale=math.clamp(w/1100,0.62,1)*T.setting('HudScale')
  healthScale.Scale=scale;timerScale.Scale=scale;buildScale.Scale=scale*.9;menuScale.Scale=math.clamp(scale,.7,1.1)
  bossBar.Size=UDim2.fromOffset(math.min(460,w-32),68)
  bossBar.Position=UDim2.new(.5,0,1,compact and -142 or -88)
  health.Position=UDim2.fromOffset(12,12)
  timer.Position=UDim2.new(0.5,0,0,14)
  -- Narrow screens: the build strip moves under the health block so nothing overlaps the timer.
  if compact then build.AnchorPoint=Vector2.new(0,0);build.Position=UDim2.fromOffset(12,12+240*scale)
  else build.AnchorPoint=Vector2.new(1,0);build.Position=UDim2.new(1,-12,0,12) end
  menu.Position=UDim2.new(1,-10,.52,0)
  header.Size=UDim2.fromOffset(math.min(500,w-28),46)
  note.TextSize=12
  title.TextSize=26
  local footerWidth=math.min(660,w-24)
  footer.Size=UDim2.fromOffset(footerWidth,64)
  local bw=(footerWidth-32)/5
  for i,b in {shopTab,upgradesTab,inventoryTab,statsTab,closeButton} do
   b.Position=UDim2.fromOffset((i-1)*(bw+8),8);b.Size=UDim2.fromOffset(bw,48);b.Caption.TextSize=w<600 and 12 or 18
  end
  render()
 end
 root:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
 player:GetAttributeChangedSignal('Setting_HudScale'):Connect(layout)
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
