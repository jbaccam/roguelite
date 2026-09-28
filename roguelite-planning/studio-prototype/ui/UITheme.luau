-- Shared green UI theme: charcoal nine-slice panels with lime corners, lime buttons,
-- faceted stone end caps and FredokaOne type. Presentation only; no gameplay authority.
local TweenService=game:GetService('TweenService')
local Players=game:GetService('Players')
local T={}

T.Color={
 white=Color3.fromRGB(248,249,245), muted=Color3.fromRGB(174,183,185), dim=Color3.fromRGB(120,128,131),
 lime=Color3.fromRGB(145,239,20), limeSoft=Color3.fromRGB(210,255,161), limeDark=Color3.fromRGB(58,112,12),
 red=Color3.fromRGB(239,35,47), negative=Color3.fromRGB(255,105,105), gold=Color3.fromRGB(255,203,64),
 cyan=Color3.fromRGB(100,220,255), cream=Color3.fromRGB(234,221,167), emerald=Color3.fromRGB(70,226,120),
 well=Color3.fromRGB(34,39,43), track=Color3.fromRGB(22,29,32), shade=Color3.fromRGB(5,9,10), ink=Color3.fromRGB(10,14,8),
}
-- Rarity: common, rare, epic, legendary. Used as accent strips and name colours only.
T.Tier={Color3.fromRGB(218,224,228),Color3.fromRGB(79,183,245),Color3.fromRGB(192,116,249),Color3.fromRGB(248,88,99)}
T.Roman={'I','II','III','IV'}
T.Font=Enum.Font.FredokaOne
T.Body=Enum.Font.SourceSansBold

T.Asset={
 panel='rbxassetid://116439058081230', inset='rbxassetid://82653359149627', button='rbxassetid://72732018694626',
 stone='rbxassetid://107387940957948', heart='rbxassetid://101432943753406', gem='rbxassetid://102213113777434',
 bag='rbxassetid://82818131570338', shard='rbxassetid://119781825571908', xp='rbxassetid://101475186887359',
 teeth='rbxassetid://113971691535704', shoulders='rbxassetid://103758481309908', pan='rbxassetid://120727496371371',
 duck='rbxassetid://72853007735977', staff='rbxassetid://102427273904664',
 -- User-generated HUD icons (ui/assets/hud/asset-ids.json).
 play='rbxassetid://119231770241307', chest='rbxassetid://128369126123154', armory='rbxassetid://128990045041232',
 loadout='rbxassetid://73755136987218', store='rbxassetid://113789432822588', quests='rbxassetid://85014504299735',
 achievements='rbxassetid://79366861483753', profile='rbxassetid://138623258102251', party='rbxassetid://83985140371877',
 settings='rbxassetid://127804812980101',
 -- Rarity (build_assets.py): `panel` without accents, plus white corner accents to tint.
 panelPlain='rbxassetid://105310886449973', corners='rbxassetid://122511819290059',
 -- build_assets.py `lock`: steel shackle, brass body.
 lock='rbxassetid://89513131203273',
 -- User-supplied art: premium currency and the run's shard bag.
 emerald='rbxassetid://107205947937384', shardBag='rbxassetid://129322350142524',
}
-- The supplied shard art sits inside a larger atlas; crop to the crystal.
T.ShardRect={offset=Vector2.new(280,130),size=Vector2.new(460,780)}
local SLICE=Rect.new(48,48,208,208)

function T.make(class,parent,props)
 local o=Instance.new(class)
 for k,v in props do o[k]=v end
 o.Parent=parent
 return o
end
local make=T.make

function T.frame(parent,name,x,y,w,h)
 return make('Frame',parent,{Name=name,BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h)})
end
-- kind: 'panel' (lime corners), 'inset' (plain dark well) or 'button' (lime face).
function T.panel(parent,name,x,y,w,h,kind)
 return make('ImageLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Image=T.Asset[kind or 'panel'],ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.55})
end
function T.icon(parent,name,x,y,size,asset)
 local i=make('ImageLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),Image=T.Asset[asset] or asset or '',ScaleType=Enum.ScaleType.Fit})
 if asset=='shard' then i.ImageRectOffset=T.ShardRect.offset;i.ImageRectSize=T.ShardRect.size end
 return i
end
-- Chunky outlined headline text. Fixed TextSize; wraps inside its box.
function T.label(parent,name,text,x,y,w,h,size,color)
 return make('TextLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Text=text,TextColor3=color or T.Color.white,Font=T.Font,TextSize=size or 24,TextWrapped=true,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=.12})
end
-- Body copy: left aligned, shrinks to fit between 9px and `size`.
function T.text(parent,name,text,x,y,w,h,size,color)
 local l=make('TextLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Text=text,TextColor3=color or T.Color.white,Font=T.Body,TextSize=size or 16,TextScaled=true,TextWrapped=true,RichText=true,TextXAlignment=Enum.TextXAlignment.Left,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=.55})
 make('UITextSizeConstraint',l,{MinTextSize=9,MaxTextSize=size or 16})
 return l
end
function T.hex(color) return string.format('#%02X%02X%02X',math.round(color.R*255),math.round(color.G*255),math.round(color.B*255)) end

-- Buttons: lime face by default, charcoal panel when `neutral`. Interactable=false dims them.
function T.button(parent,name,text,x,y,w,h,callback,neutral)
 local b=make('ImageButton',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Image=T.Asset[neutral and 'panel' or 'button'],ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.5,AutoButtonColor=false,Selectable=true})
 b:SetAttribute('Neutral',neutral==true)
 local t=T.label(b,'Caption',text,8,4,w-16,h-8,22);t.Size=UDim2.new(1,-16,1,-8)
 local over=false
 local function paint()
  local enabled=b.Interactable
  local tier=b:GetAttribute('Tier') or 1
  if tier>1 then
   -- Same charcoal panel; only the corner accents (RarityCorners child) carry the colour.
   b.Image=T.Asset.panelPlain
   b.ImageColor3=not enabled and Color3.fromRGB(150,150,150) or over and Color3.fromRGB(215,222,228) or Color3.new(1,1,1)
  else
   b.Image=T.Asset[(b:GetAttribute('Neutral') or not enabled) and 'panel' or 'button']
   b.ImageColor3=not enabled and Color3.fromRGB(150,150,150) or over and T.Color.limeSoft or Color3.new(1,1,1)
  end
  t.TextTransparency=enabled and 0 or .4
 end
 b.MouseEnter:Connect(function() over=true;paint() end)
 b.MouseLeave:Connect(function() over=false;paint() end)
 b.SelectionGained:Connect(function() over=true;paint() end)
 b.SelectionLost:Connect(function() over=false;paint() end)
 b:GetPropertyChangedSignal('Interactable'):Connect(paint)
 b:GetAttributeChangedSignal('Neutral'):Connect(paint)
 b:GetAttributeChangedSignal('Tier'):Connect(paint)
 if callback then b.Activated:Connect(callback) end
 paint()
 return b
end
-- Switch an existing button between lime (selected/primary) and charcoal.
function T.setPrimary(b,primary) b:SetAttribute('Neutral',not primary) end

-- Rarity: same panel, corner accents recoloured (II blue, III purple, IV red). Common (I)
-- keeps the lime corners. Works on labels and buttons (buttons repaint through hover).
function T.setTier(obj,tier)
 tier=tier or 1
 obj:SetAttribute('Tier',tier)
 local corners=obj:FindFirstChild('RarityCorners')
 if tier>1 then
  if not obj:IsA('GuiButton') then obj.Image=T.Asset.panelPlain;obj.ImageColor3=Color3.new(1,1,1) end
  if not corners then
   corners=make('ImageLabel',obj,{Name='RarityCorners',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),Image=T.Asset.corners,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=obj.SliceScale,ZIndex=obj.ZIndex})
  end
  corners.ImageColor3=T.Tier[tier]
 elseif corners then corners:Destroy() end
 return obj
end
function T.rarityPanel(parent,name,x,y,w,h,tier)
 return T.setTier(T.panel(parent,name,x,y,w,h,'panel'),tier)
end
-- Solid rarity pill with the tier numeral (I-IV). Anchored by its top-left unless given.
T.TierFill={Color3.fromRGB(96,104,108),Color3.fromRGB(34,122,190),Color3.fromRGB(128,62,196),Color3.fromRGB(196,44,56)}
function T.tierBadge(parent,tier,x,y,anchor)
 tier=math.clamp(tier or 1,1,4)
 local b=make('Frame',parent,{Name='TierBadge',Position=UDim2.fromOffset(x,y),AnchorPoint=anchor or Vector2.zero,Size=UDim2.fromOffset(tier==1 and 22 or 18+#T.Roman[tier]*8,20),BackgroundColor3=T.TierFill[tier],BorderSizePixel=0,ZIndex=4})
 make('UICorner',b,{CornerRadius=UDim.new(0,5)})
 make('UIStroke',b,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 local l=T.label(b,'Tier',T.Roman[tier],0,0,0,0,15);l.Size=UDim2.fromScale(1,1);l.ZIndex=5;l.TextStrokeTransparency=.3
 return b
end
-- Upgrade progress: "have / need" printed inside a lime bar. need=nil means max tier.
function T.upgradeBar(parent,name,x,y,w,h,have,need)
 local fill,track=T.bar(parent,name,x,y,w,h,need and have>=need and T.Color.gold or T.Color.lime)
 T.setBar(fill,need and have/need or 1)
 local l=T.label(track,'Count',need and (have..' / '..need) or 'MAX',0,0,0,0,math.min(16,h),T.Color.white);l.Size=UDim2.fromScale(1,1);l.ZIndex=3;l.TextStrokeTransparency=0
 return track
end
-- Faceted stone end caps on either side of a header panel.
function T.caps(parent,size)
 size=size or 40
 local l=T.icon(parent,'LeftStone',0,0,size,'stone');l.AnchorPoint=Vector2.new(.5,.5);l.Position=UDim2.new(0,4,.5,0)
 local r=T.icon(parent,'RightStone',0,0,size,'stone');r.AnchorPoint=Vector2.new(.5,.5);r.Position=UDim2.new(1,-4,.5,0)
 return l,r
end
-- Progress bar in a dark inset well. Returns the fill frame; call T.setBar(fill,ratio).
function T.bar(parent,name,x,y,w,h,color)
 local track=make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=T.Color.track,BorderSizePixel=0,ClipsDescendants=true})
 make('UICorner',track,{CornerRadius=UDim.new(0,4)})
 make('UIStroke',track,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 local fill=make('Frame',track,{Name='Fill',Size=UDim2.fromScale(0,1),BackgroundColor3=color or T.Color.lime,BorderSizePixel=0})
 make('UICorner',fill,{CornerRadius=UDim.new(0,4)})
 make('UIGradient',fill,{Rotation=90,Color=ColorSequence.new(Color3.new(1,1,1),Color3.fromRGB(165,165,165))})
 return fill,track
end
function T.setBar(fill,ratio,animate)
 ratio=math.clamp(ratio or 0,0,1)
 if animate then TweenService:Create(fill,TweenInfo.new(.22,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=UDim2.fromScale(ratio,1)}):Play()
 else fill.Size=UDim2.fromScale(ratio,1) end
end
-- Red notification pill in a corner. Text '' or nil hides it.
function T.badge(parent,text)
 local b=parent:FindFirstChild('Badge')
 if not b then
  b=make('Frame',parent,{Name='Badge',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(1,-8,0,8),Size=UDim2.fromOffset(28,28),BackgroundColor3=Color3.fromRGB(214,38,46),BorderSizePixel=0,ZIndex=5})
  make('UICorner',b,{CornerRadius=UDim.new(1,0)})
  make('UIStroke',b,{Color=Color3.fromRGB(20,10,10),Thickness=2.5})
  local l=T.label(b,'Count','',0,0,28,28,17);l.Size=UDim2.fromScale(1,1);l.ZIndex=6
 end
 b.Visible=text~=nil and text~=''
 b.Count.Text=text or ''
 b.Size=UDim2.fromOffset(math.max(28,12+#(text or '')*11),28)
 return b
end
-- Large icon-with-caption launcher (lobby bar, HUD menu). Grows slightly on hover.
function T.iconButton(parent,name,asset,caption,size,callback)
 local b=make('ImageButton',parent,{Name=name,BackgroundTransparency=1,Image='',Size=UDim2.fromOffset(size,size+(caption~='' and 22 or 0)),AutoButtonColor=false,Selectable=true})
 local scale=make('UIScale',b,{Scale=1})
 local art=T.icon(b,'Icon',0,0,size,asset)
 local l
 if caption~='' then l=T.label(b,'Caption',caption,-20,size-10,size+40,30,math.clamp(math.floor(size*.3),14,24));l.TextWrapped=false end
 local function to(v) TweenService:Create(scale,TweenInfo.new(.12,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=v}):Play() end
 b.MouseEnter:Connect(function() to(1.08) end);b.MouseLeave:Connect(function() to(1) end)
 b.SelectionGained:Connect(function() to(1.08) end);b.SelectionLost:Connect(function() to(1) end)
 b.MouseButton1Down:Connect(function() to(.94) end);b.MouseButton1Up:Connect(function() to(1.08) end)
 if callback then b.Activated:Connect(callback) end
 return b,art,l
end
-- Row of tab buttons. The selected tab is lime; the rest charcoal.
function T.tabs(parent,x,y,w,h,list,selected,callback)
 local gap=8;local bw=(w-gap*(#list-1))/#list;local out={}
 for i,id in list do
  local b=T.button(parent,'Tab_'..id,id,x+(i-1)*(bw+gap),y,bw,h,function() callback(id) end,id~=selected)
  b.Caption.TextSize=math.min(20,h-14);out[id]=b
 end
 return out
end
function T.scroll(parent,name,x,y,w,h)
 return make('ScrollingFrame',parent,{Name=name,BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),CanvasSize=UDim2.new(),ScrollBarThickness=6,ScrollBarImageColor3=T.Color.lime,ScrollingDirection=Enum.ScrollingDirection.Y,VerticalScrollBarInset=Enum.ScrollBarInset.ScrollBar})
end
-- Small rounded chip, e.g. PREVIEW / LOCKED / OWNED.
function T.chip(parent,name,text,x,y,color,textColor)
 local size=game:GetService('TextService'):GetTextSize(text,14,T.Font,Vector2.new(1000,100))
 local c=make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size.X+16,22),BackgroundColor3=color or T.Color.well,BorderSizePixel=0})
 make('UICorner',c,{CornerRadius=UDim.new(0,6)})
 make('UIStroke',c,{Color=Color3.fromRGB(8,10,11),Thickness=1.5})
 local l=T.label(c,'Text',text,0,0,0,0,14,textColor);l.Size=UDim2.fromScale(1,1);l.TextStrokeTransparency=.6
 return c
end
-- rbxthumb content goes through the normal image cache: no web call each time a window opens,
-- and AssetPreloader warms the local player's portrait at join.
function T.headshotId(userId) return 'rbxthumb://type=AvatarHeadShot&id='..userId..'&w=150&h=150' end
function T.headshot(image,userId) image.Image=T.headshotId(userId) end

-- Modal window: dimmed backdrop, lime-cornered frame, title with stone caps, close button.
-- `w`/`h` is the content layout size; the frame adds WINDOW_MARGIN of breathing room on every
-- side. Scales to fit the viewport, up to WINDOW_MAX_SCALE on large screens.
-- Returns an object with Body (content frame, w-36 wide) and Close().
-- opts.large: content-heavy windows (Store) centre on screen and use nearly the full height
-- instead of leaving room for the lobby HUD, which the backdrop dims anyway.
T.WINDOW_MARGIN=22;T.WINDOW_MAX_SCALE=1.15;T.LARGE_WINDOW_MAX_SCALE=1.3
function T.window(screen,name,title,w,h,onClose,opts)
 local large=opts and opts.large
 local m=T.WINDOW_MARGIN;w+=m*2;h+=m*2
 -- Extends above the safe area so the dim also covers Roblox's top bar strip.
 local backdrop=make('TextButton',screen,{Name=name,Text='',AutoButtonColor=false,Active=true,Modal=true,Position=UDim2.fromOffset(0,-120),Size=UDim2.new(1,0,1,120),BackgroundColor3=T.Color.shade,BackgroundTransparency=.35,BorderSizePixel=0,ZIndex=20,Selectable=false})
 local holder=T.frame(backdrop,'Window',0,0,w,h);holder.AnchorPoint=Vector2.new(.5,.5)
 -- Backdrop starts 120 px above the screen: +76 puts the frame centre 16 px below screen centre,
 -- which centres frame + title plate together.
 holder.Position=large and UDim2.new(.5,0,.5,76) or UDim2.new(.5,0,.53,60)
 local scale=make('UIScale',holder,{Scale=1})
 local frame=T.panel(holder,'Frame',0,0,w,h,'panel');frame.Size=UDim2.fromScale(1,1);frame.Active=true
 local head=T.panel(holder,'TitlePlate',18,-30,0,56,'panel')
 local titleSize=game:GetService('TextService'):GetTextSize(title,32,T.Font,Vector2.new(2000,100)).X
 head.Size=UDim2.fromOffset(titleSize+76,56);head.Active=true
 T.caps(head,40)
 local titleLabel=T.label(head,'Title',title,0,0,0,0,32);titleLabel.Size=UDim2.fromScale(1,1)
 local body=T.frame(holder,'Body',18+m,40+m,w-36-m*2,h-58-m*2)
 local self={Root=backdrop,Holder=holder,Body=body,Title=titleLabel,Scale=scale}
 -- Red-cornered close button with a red X so it reads as 'close' at a glance.
 local close=T.button(holder,'Close','X',w-62,-22,58,58,nil,true);T.setTier(close,4);close.Caption.TextColor3=T.Color.negative;close.Caption.TextSize=34
 local function fit()
  local v=screen.AbsoluteSize
  if v.X<=0 then return end
  if large then scale.Scale=math.min(T.LARGE_WINDOW_MAX_SCALE,(v.X-32)/w,(v.Y-40)/(h+34))
  else scale.Scale=math.min(T.WINDOW_MAX_SCALE,(v.X-24)/w,(v.Y-184)/(h+34)) end
 end
 local conn=screen:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit);fit()
 function self.Close()
  if not backdrop.Parent then return end
  conn:Disconnect();backdrop:Destroy()
  if onClose then onClose() end
 end
 close.Activated:Connect(self.Close)
 backdrop.Activated:Connect(self.Close)
 scale.Scale*=.92;TweenService:Create(scale,TweenInfo.new(.14,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=scale.Scale/.92}):Play()
 return self
end

-- Short message near the top of a screen (purchase results, errors). Replaces any previous one.
function T.toast(screen,text,color)
 local old=screen:FindFirstChild('Toast');if old then old:Destroy() end
 local size=game:GetService('TextService'):GetTextSize(text,20,T.Font,Vector2.new(900,100))
 local t=T.panel(screen,'Toast',0,0,size.X+60,52,'panel');t.AnchorPoint=Vector2.new(.5,0);t.Position=UDim2.new(.5,0,0,96);t.ZIndex=50
 local l=T.label(t,'Text',text,0,0,0,0,20,color or T.Color.white);l.Size=UDim2.fromScale(1,1);l.ZIndex=51
 task.delay(2.6,function()
  if not t.Parent then return end
  TweenService:Create(t,TweenInfo.new(.3),{ImageTransparency=1}):Play()
  TweenService:Create(l,TweenInfo.new(.3),{TextTransparency=1,TextStrokeTransparency=1}):Play()
  task.delay(.3,function() t:Destroy() end)
 end)
 return t
end

-- Local presentation settings, stored as LocalPlayer attributes for this session.
-- Combat presentation reads Setting_ScreenShake and Setting_DamageNumbers.
T.SettingDefaults={HudScale=1,ScreenShake=true,DamageNumbers=true}
function T.setting(key)
 local v=Players.LocalPlayer:GetAttribute('Setting_'..key)
 if v==nil then return T.SettingDefaults[key] end
 return v
end
function T.setSetting(key,value) Players.LocalPlayer:SetAttribute('Setting_'..key,value) end
function T.settingsWindow(screen)
 local win=T.window(screen,'SettingsWindow','Settings',520,330)
 local body=win.Body;local w=520-36
 local function row(y,title,help)
  T.label(body,title..'Title',title,14,y,w*.5,30,22).TextXAlignment=Enum.TextXAlignment.Left
  T.text(body,title..'Help',help,14,y+30,w*.5,20,14,T.Color.muted)
 end
 local function draw()
  for _,c in body:GetChildren() do c:Destroy() end
  row(16,'HUD size','Scales the in-run HUD.')
  local current=T.setting('HudScale')
  for i,opt in {{'Small',.85},{'Normal',1},{'Large',1.15}} do
   T.button(body,'Scale'..opt[1],opt[1],w*.5+(i-1)*(w*.5/3),18,w*.5/3-6,44,function() T.setSetting('HudScale',opt[2]);draw() end,math.abs(current-opt[2])>.01).Caption.TextSize=18
  end
  for i,opt in {{'ScreenShake','Screen shake','Camera shake when you take damage.'},{'DamageNumbers','Damage numbers','Numbers above enemies you hit.'}} do
   local y=16+i*84;row(y,opt[2],opt[3])
   local on=T.setting(opt[1])
   T.button(body,opt[1],on and 'ON' or 'OFF',w*.5+w*.25,y+2,w*.25-6,44,function() T.setSetting(opt[1],not T.setting(opt[1]));draw() end,not on).Caption.TextSize=20
  end
  T.text(body,'Note','Settings last for this session.',14,254,w-28,20,14,T.Color.dim)
 end
 draw()
 return win
end

return T
