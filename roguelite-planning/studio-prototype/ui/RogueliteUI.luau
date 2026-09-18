-- Reusable presentation only. No inventory, economy, damage, or reward authority.
local TweenService = game:GetService("TweenService")
local UI = {}
local C = {white=Color3.fromRGB(248,249,245), muted=Color3.fromRGB(174,183,185), lime=Color3.fromRGB(145,239,20), red=Color3.fromRGB(239,35,47)}
local A = {
 panel="rbxassetid://116439058081230", inset="rbxassetid://82653359149627", button="rbxassetid://72732018694626",
 stone="rbxassetid://107387940957948", heart="rbxassetid://101432943753406", gem="rbxassetid://102213113777434",
 bag="rbxassetid://82818131570338", teeth="rbxassetid://113971691535704", shoulders="rbxassetid://103758481309908",
 pan="rbxassetid://120727496371371", duck="rbxassetid://72853007735977", staff="rbxassetid://102427273904664",
}
UI.Assets = A
local function make(class, parent, props)
 local o=Instance.new(class)
 for k,v in props do o[k]=v end
 o.Parent=parent
 return o
end
local function frame(parent,name,x,y,w,h)
 return make("Frame",parent,{Name=name,BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h)})
end
local function panel(parent,name,x,y,w,h,kind)
 return make("ImageLabel",parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Image=A[kind or "panel"],ScaleType=Enum.ScaleType.Slice,SliceCenter=Rect.new(48,48,208,208),SliceScale=0.55})
end
local function icon(parent,name,x,y,size,asset)
 return make("ImageLabel",parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),Image=A[asset] or asset,ScaleType=Enum.ScaleType.Fit})
end
local function label(parent,name,text,x,y,w,h,size,color)
 local l=make("TextLabel",parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Text=text,TextColor3=color or C.white,Font=Enum.Font.FredokaOne,TextSize=size or 24,TextWrapped=true,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=0.12})
 return l
end
local function button(parent,name,text,x,y,w,h,callback,neutral)
 local b=make("ImageButton",parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Image=A[neutral and "panel" or "button"],ScaleType=Enum.ScaleType.Slice,SliceCenter=Rect.new(48,48,208,208),SliceScale=0.5,AutoButtonColor=false,Selectable=true})
 local t=label(b,"Caption",text,8,4,w-16,h-8,22)
 t.Size=UDim2.new(1,-16,1,-8)
 local function hover(on) b.ImageColor3=on and Color3.fromRGB(210,255,161) or Color3.new(1,1,1) end
 b.MouseEnter:Connect(function() hover(true) end)
 b.MouseLeave:Connect(function() hover(false) end)
 b.SelectionGained:Connect(function() hover(true) end)
 b.SelectionLost:Connect(function() hover(false) end)
 b.Activated:Connect(callback)
 return b
end
function UI.mount(playerGui, studioPreview)
 local gui=make("ScreenGui",playerGui,{Name="RogueliteHUD",ResetOnSpawn=false,DisplayOrder=20,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets,ClipToDeviceSafeArea=true})
 local root=frame(gui,"SafeArea",0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local hud=frame(root,"HUD",0,0,0,0);hud.Size=UDim2.fromScale(1,1)
 local health=frame(hud,"Health",20,16,382,72)
 local healthScale=make("UIScale",health,{Scale=1})
 panel(health,"HealthFrame",25,8,355,56,"inset")
 local track=make("Frame",health,{Name="Track",Position=UDim2.fromOffset(54,20),Size=UDim2.fromOffset(307,30),BackgroundColor3=Color3.fromRGB(34,39,43),BorderSizePixel=0,ClipsDescendants=true})
 local trail=make("Frame",track,{Name="DamageTrail",Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(248,172,104),BorderSizePixel=0})
 local fill=make("Frame",track,{Name="Fill",Size=UDim2.fromScale(1,1),BackgroundColor3=C.red,BorderSizePixel=0})
 make("UIGradient",fill,{Rotation=90,Color=ColorSequence.new({ColorSequenceKeypoint.new(0,Color3.fromRGB(255,109,103)),ColorSequenceKeypoint.new(0.18,Color3.fromRGB(255,45,54)),ColorSequenceKeypoint.new(0.52,Color3.fromRGB(227,22,35)),ColorSequenceKeypoint.new(1,Color3.fromRGB(165,16,27))})})
 local shine=make("Frame",fill,{Name="Shine",Position=UDim2.fromOffset(0,2),Size=UDim2.new(1,0,0,2),BackgroundColor3=Color3.fromRGB(255,152,144),BackgroundTransparency=0.4,BorderSizePixel=0})
 icon(health,"Heart",0,0,75,"heart")
 local hp=label(health,"HealthText","— / —",75,10,265,48,29)
 local timer=panel(hud,"Timer",0,14,225,65)
 timer.AnchorPoint=Vector2.new(0.5,0);timer.Position=UDim2.new(0.5,0,0,14)
 local timerScale=make("UIScale",timer,{Scale=1})
 icon(timer,"LeftStone",-14,10,44,"stone");icon(timer,"RightStone",195,10,44,"stone")
 local timeText=label(timer,"Time","--:--",25,3,175,42,35)
 local phase=panel(timer,"Phase",43,51,139,31)
 local phaseText=label(phase,"Label","PRACTICE",8,2,123,26,17)
 local low=label(health,"Warning","LOW HEALTH",92,63,250,22,16,C.red);low.Visible=false
 local overlay=make("Frame",root,{Name="Menus",Active=true,Visible=false,Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(5,9,10),BackgroundTransparency=0.14,BorderSizePixel=0})
 local header=panel(overlay,"Header",0,12,500,68)
 header.AnchorPoint=Vector2.new(0.5,0);header.Position=UDim2.new(0.5,0,0,12)
 local title=label(header,"Title","LEVEL UP!",15,7,470,49,34)
 title.Size=UDim2.new(1,-30,1,-14)
 local note=label(overlay,"PreviewNote","UI PREVIEW  ·  No gameplay changes",0,84,0,24,15,C.muted);note.Size=UDim2.new(1,0,0,24)
 local scroller=make("ScrollingFrame",overlay,{Name="Content",BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(12,120),Size=UDim2.new(1,-24,1,-193),CanvasSize=UDim2.new(),ScrollBarThickness=5,ScrollBarImageColor3=C.lime,ScrollingDirection=Enum.ScrollingDirection.Y})
 local content=frame(scroller,"Canvas",0,0,0,0)
 local footer=frame(overlay,"Footer",0,0,0,64);footer.AnchorPoint=Vector2.new(0.5,1);footer.Position=UDim2.new(0.5,0,1,-5);footer.Size=UDim2.new(1,-24,0,64)
 local status=label(overlay,"Status","",0,0,0,30,16,C.lime);status.AnchorPoint=Vector2.new(0.5,1);status.Position=UDim2.new(0.5,0,1,-70);status.Size=UDim2.new(1,-20,0,30);status.TextScaled=true
 make('UITextSizeConstraint',status,{MinTextSize=10,MaxTextSize=16})
 local controller={Gui=gui, HealthFill=fill, HealthText=hp, Mode=nil}
 local currentHp, currentMax=0,100
 local fillTween,trailTween
 function controller:SetHealth(value,maximum,immediate)
  value=math.max(0,value);maximum=math.max(0,maximum)
  local ratio=maximum>0 and math.clamp(value/maximum,0,1) or 0
  local decreasing=value<currentHp and not immediate
  currentHp,currentMax=value,maximum
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
 function controller:SetTimer(seconds,wave,phaseName)
  if seconds then local s=math.max(0,math.ceil(seconds));timeText.Text=string.format("%02d:%02d",math.floor(s/60),s%60) else timeText.Text="--:--" end
  phaseText.Text=wave and ("WAVE "..tostring(wave)) or string.upper(phaseName or "PRACTICE")
 end
 local upgrades={
  {id="teeth",name="Teeth",icon="teeth",effect="+3% Life Steal"},
  {id="shoulders",name="Shoulders",icon="shoulders",effect="+2 Ranged Damage"},
  {id="bag",name="Bandage Roll",icon="bag",effect="+1 HP Regeneration"},
 }
 local selected=nil
 local render
 local shopView
 local creativeInventory
 local function close()
  local wasOpen=overlay.Visible
  overlay.Visible=false;hud.Visible=true;controller.Mode=nil;gui:SetAttribute("PreviewScreen",nil)
  game:GetService("GuiService").SelectedObject=nil
  if wasOpen then
   -- Always hand preview input back to the normal Roblox character camera.
   -- No saved CameraSubject: it may belong to a character that has respawned.
   local player=game:GetService("Players").LocalPlayer
   local humanoid=player.Character and player.Character:FindFirstChildOfClass("Humanoid")
   local camera=workspace.CurrentCamera
   if camera and humanoid then
    camera.CameraSubject=humanoid
    camera.CameraType=Enum.CameraType.Custom
   end
   local input=game:GetService("UserInputService")
   input.MouseBehavior=Enum.MouseBehavior.Default
   input.MouseIconEnabled=true
  end
 end
 function controller:Close() close() end
 local shopTab=button(footer,"ShopTab","Shop",0,8,120,48,function() controller:ShowPreview("Shop") end,true)
 local upgradesTab=button(footer,"UpgradesTab","Upgrades",130,8,140,48,function() controller:ShowPreview("Upgrades") end,true)
 local inventoryTab=button(footer,"InventoryTab","Inventory",0,8,140,48,function() controller:ShowPreview("Inventory") end,true)
 local closeButton=button(footer,"Close","Back to game",280,8,210,48,close)
 closeButton.Modal=true -- Only while its menu is visible; releases first-person cursor.
 local previewButton
 if studioPreview then
  previewButton=button(hud,"PreviewButton","UI Preview",0,0,145,46,function() controller:ShowPreview("Upgrades") end,true)
  previewButton.AnchorPoint=Vector2.new(1,1);previewButton.Position=UDim2.new(1,-16,1,-16)
 end
 if studioPreview then

  local b=button(hud,'InventoryButton','Inventory [I]',0,0,170,46,function() controller:ShowPreview('Inventory') end,true)
  b.AnchorPoint=Vector2.new(1,1);b.Position=UDim2.new(1,-172,1,-16)
  game:GetService('UserInputService').InputBegan:Connect(function(input,processed)
   if processed or game:GetService('UserInputService'):GetFocusedTextBox() then return end
   if input.KeyCode==Enum.KeyCode.I then if controller.Mode=='Inventory' then close() else controller:ShowPreview('Inventory') end end
  end)
 end
 local statsView=require(game:GetService('ReplicatedStorage'):WaitForChild('CharacterStatsUI')).new(game:GetService('Players').LocalPlayer,{panel=panel,label=label,button=button})
 local statsTab=button(footer,'StatsTab','Stats',0,8,100,48,function() controller:ShowPreview('Stats') end,true)
 if studioPreview then
  local b=button(hud,'StatsButton','Stats / Test [P]',0,0,170,46,function() controller:ShowPreview('Stats') end,true)
  b.AnchorPoint=Vector2.new(1,1);b.Position=UDim2.new(1,-16,1,-70)
  game:GetService('UserInputService').InputBegan:Connect(function(input,processed) if not processed and input.KeyCode==Enum.KeyCode.P then if controller.Mode=='Stats' then close() else controller:ShowPreview('Stats') end end end)
 end
 local shopModule=require(game.ReplicatedStorage:WaitForChild('ShopUI'))
 shopView=shopModule.new(game.Players.LocalPlayer,{panel=panel,label=label,button=button,icon=icon},function() if render and (controller.Mode=='Shop' or controller.Mode=='Inventory') then render() elseif controller.Mode=='Stats' then local data=shopView:snapshot();if data then status.Text=data.message end end end)
 local statLabels={}
 creativeInventory=require(game.ReplicatedStorage:WaitForChild('WeaponInventoryUI')).new(game.Players.LocalPlayer,{panel=panel,label=label,button=button},function() if render and controller.Mode=='Inventory' then task.defer(render) end end)
 function controller:SetStats(maxHealth,walkSpeed)
  if statLabels.MaxHP then statLabels.MaxHP.Text=tostring(math.ceil(maxHealth)) end
  if statLabels.MoveSpeed then statLabels.MoveSpeed.Text=string.format("%.1f",walkSpeed) end
 end
 render=function()
  if not controller.Mode then return end
  local settings=shopModule.getLayout()
  local isShop=controller.Mode=='Shop'
  local inset=game:GetService('GuiService'):GetGuiInset().Y
  -- Extend the menu backdrop into the top inset, while keeping buttons below Roblox's bar.
  overlay.Position=UDim2.fromOffset(0,-inset);overlay.Size=UDim2.new(1,0,1,inset)
  local margin=isShop and math.floor(root.AbsoluteSize.X*settings.HorizontalMargin) or 12
  local top=isShop and settings.ContentTop or 88
  scroller.Position=UDim2.fromOffset(margin,top);scroller.Size=UDim2.new(1,-margin*2,1,-top-108)
  header.Position=UDim2.new(.5,0,0,settings.HeaderTop)
  note.Visible=not isShop
  content:ClearAllChildren();statLabels={}
  local width=math.max(260,scroller.AbsoluteSize.X-(isShop and 0 or 10))
  scroller.ScrollingEnabled=controller.Mode~='Shop'
  if controller.Mode=='Inventory' then
   local height=creativeInventory:render(content,width)
   if width>=850 then content.EquippedWeapons.Position=UDim2.fromOffset(content.EquippedWeapons.Position.X.Offset,scroller.CanvasPosition.Y) end
   content.Size=UDim2.fromOffset(width,height);scroller.CanvasSize=UDim2.fromOffset(0,height)
   title.Text='CREATIVE INVENTORY';note.Text='Choose a slot · Equip any weapon for free · Duplicates allowed'
   return
  end
  if controller.Mode=='Shop' then
   content.Size=UDim2.fromOffset(width,scroller.AbsoluteSize.Y);scroller.CanvasSize=UDim2.new()
   local data=shopView:render(content,width,scroller.AbsoluteSize.Y,controller.Mode=='Inventory')
   if data then title.Text=(controller.Mode=='Inventory' and 'INVENTORY · WAVE ' or 'SHOP · WAVE ')..data.wave;note.Text='';status.Text=data.message end
   return
  end
  if controller.Mode=='Stats' then
   local offset=shopView:debug(content,width)
   local inner=frame(content,'StatEditor',0,offset,width,1)
   local height=statsView:render(inner,width)+offset;inner.Size=UDim2.fromOffset(width,height-offset);content.Size=UDim2.fromOffset(width,height);scroller.CanvasSize=UDim2.fromOffset(0,height);return
  end
  -- The upgrades tab remains an explicitly labelled presentation preview.
  local usable=math.min(width,1100);local columns=usable>=800 and 3 or usable>=520 and 2 or 1
  local cw=(usable-(columns-1)*12)/columns;local x=(width-usable)/2
  for i,d in upgrades do
   local card=panel(content,'Upgrade_'..d.id,x+((i-1)%columns)*(cw+12),math.floor((i-1)/columns)*270,cw,258)
   icon(card,'Icon',(cw-90)/2,12,90,d.icon)
   label(card,'Name',d.name,10,108,cw-20,35,22)
   label(card,'Effect',d.effect,10,150,cw-20,40,18,C.lime)
   button(card,'Preview','Preview only',12,206,cw-24,38,function() status.Text='Upgrade selection is not implemented yet.' end,true).Caption.TextSize=15
  end
  local bottom=math.ceil(#upgrades/columns)*270
  content.Size=UDim2.fromOffset(width,bottom)
  scroller.CanvasSize=UDim2.fromOffset(0,bottom)
 end
 function controller:ShowPreview(mode)
  controller.Mode=mode;title.Text=mode=='Stats' and 'CHARACTER STATS' or mode=='Inventory' and 'WEAPON INVENTORY' or (mode=='Shop' and 'SHOP' or 'LEVEL UP!')
  note.Text=mode=='Stats' and 'STUDIO PRACTICE  ·  Server-applied edits  ·  No saved rewards' or mode=='Inventory' and 'Owned weapons and items' or mode=='Shop' and '' or 'UPGRADE PREVIEW · Not part of the shop economy' 
  overlay.Visible=true;hud.Visible=false;status.Text="";selected=nil
  gui:SetAttribute("PreviewScreen",mode)
  scroller.CanvasPosition=Vector2.zero;render()
  if game:GetService("UserInputService"):GetLastInputType()==Enum.UserInputType.Gamepad1 then
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
  local scale=math.clamp(w/1100,0.66,1)
  healthScale.Scale=scale;timerScale.Scale=scale
  health.Position=UDim2.fromOffset(12,12)
  timer.Position=compact and UDim2.new(1,-88*scale-15,0,78*scale+12) or UDim2.new(0.5,0,0,14)
  if w<1000 and not compact then timer.Position=UDim2.new(1,-130*scale,0,14) end
  header.Size=UDim2.fromOffset(math.min(500,w-28),46)
  note.Position=UDim2.fromOffset(0,60);note.TextSize=12
  scroller.Position=UDim2.fromOffset(12,88);scroller.Size=UDim2.new(1,-24,1,-196)
  title.TextSize=26
  local footerWidth=math.min(660,w-24)
  footer.Size=UDim2.fromOffset(footerWidth,64)
  local bw=(footerWidth-32)/5
  shopTab.Position=UDim2.fromOffset(0,8);shopTab.Size=UDim2.fromOffset(bw,48)
  upgradesTab.Position=UDim2.fromOffset(bw+8,8);upgradesTab.Size=UDim2.fromOffset(bw,48)
  inventoryTab.Position=UDim2.fromOffset(2*(bw+8),8);inventoryTab.Size=UDim2.fromOffset(bw,48)
  statsTab.Position=UDim2.fromOffset(3*(bw+8),8);statsTab.Size=UDim2.fromOffset(bw,48)
  for _,b in {shopTab,upgradesTab,inventoryTab,statsTab} do b.Caption.TextSize=w<600 and 12 or 18 end
  closeButton.Position=UDim2.fromOffset(4*(bw+8),8);closeButton.Size=UDim2.fromOffset(bw,48)
  closeButton.Caption.TextSize=w<600 and 12 or 18
  render()
 end
 root:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
 local lastPhase=nil
 local function phaseChanged()
  local data=shopView:snapshot();if not data then return end
  if data.phase~=lastPhase then
   lastPhase=data.phase
   if data.phase=='Shop' then controller:ShowPreview('Shop') elseif data.phase=='Combat' then close() end
  end
 end
 shopView.state:GetAttributeChangedSignal('ShopSnapshot'):Connect(phaseChanged)
 local shopButton=button(hud,'OpenShop','Shop [B]',16,100,128,38,function() controller:ShowPreview('Shop') end,true);shopButton.Caption.TextSize=16
 game:GetService('UserInputService').InputBegan:Connect(function(input,processed) if not processed and input.KeyCode==Enum.KeyCode.B then controller:ShowPreview('Shop') end end)
 task.defer(phaseChanged)
 task.defer(layout)
 return controller
end
return UI
