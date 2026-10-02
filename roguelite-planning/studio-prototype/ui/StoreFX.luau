-- Store "pop" effects: rotating rays and glow behind featured icons, hover growth,
-- pulsing buy buttons, shine sweeps and ribbons. Presentation only.
local TweenService=game:GetService('TweenService')
local RunService=game:GetService('RunService')
local T=require(game:GetService('ReplicatedStorage'):WaitForChild('UITheme'))
local FX={}
FX.Asset={rays='rbxassetid://75268019571051',glow='rbxassetid://101092695897243'}

-- One Heartbeat drives every live spinner; it disconnects when none remain.
local spinners={};local driver
local function drive()
 if driver then return end
 driver=RunService.Heartbeat:Connect(function(dt)
  local any=false
  for image,speed in spinners do
   if image.Parent then any=true;image.Rotation=(image.Rotation+speed*dt)%360 else spinners[image]=nil end
  end
  if not any then driver:Disconnect();driver=nil end
 end)
end

-- Rays + glow centred on (cx,cy) of `parent`, drawn behind later siblings.
function FX.burst(parent,cx,cy,size,color,speed)
 local holder=T.make('Frame',parent,{Name='Burst',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(cx,cy),Size=UDim2.fromOffset(size,size),ZIndex=parent.ZIndex})
 T.make('ImageLabel',holder,{Name='Glow',BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=color,ImageTransparency=.35,Size=UDim2.fromScale(.9,.9),AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),ZIndex=parent.ZIndex})
 local rays=T.make('ImageLabel',holder,{Name='Rays',BackgroundTransparency=1,Image=FX.Asset.rays,ImageColor3=color,ImageTransparency=.45,Size=UDim2.fromScale(1,1),AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),ZIndex=parent.ZIndex})
 spinners[rays]=speed or 12;drive()
 return holder,rays
end

-- Icon that grows (and wiggles) when the pointer is over `hitbox`.
function FX.popIcon(hitbox,icon,burstRays)
 local scale=icon:FindFirstChildOfClass('UIScale') or T.make('UIScale',icon,{Scale=1})
 local function to(s,rot)
  TweenService:Create(scale,TweenInfo.new(.18,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s}):Play()
  TweenService:Create(icon,TweenInfo.new(.18,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Rotation=rot}):Play()
 end
 hitbox.MouseEnter:Connect(function() to(1.18,-6);if burstRays then spinners[burstRays]=45 end end)
 hitbox.MouseLeave:Connect(function() to(1,0);if burstRays then spinners[burstRays]=12 end end)
end

-- Gentle idle bob so featured art feels alive.
function FX.bob(icon,amount,period)
 local base=icon.Position
 local tw=TweenService:Create(icon,TweenInfo.new(period or 1.4,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Position=base+UDim2.fromOffset(0,-(amount or 6))})
 tw:Play();return tw
end

-- Buy button that breathes to draw the eye.
function FX.pulse(button,amount)
 local scale=T.make('UIScale',button,{Name='Pulse',Scale=1})
 TweenService:Create(scale,TweenInfo.new(.9,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Scale=1+(amount or .05)}):Play()
 return scale
end

-- Diagonal white shine that sweeps across a card every few seconds.
function FX.shine(card,every)
 local clip=T.make('Frame',card,{Name='ShineClip',BackgroundTransparency=1,ClipsDescendants=true,Position=UDim2.fromOffset(12,12),Size=UDim2.new(1,-24,1,-24),ZIndex=card.ZIndex+3})
 local bar=T.make('Frame',clip,{Name='Shine',BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.new(0,70,2,0),Position=UDim2.new(-.3,0,.5,0),Rotation=20,ZIndex=card.ZIndex+3})
 T.make('UIGradient',bar,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.5,.72),NumberSequenceKeypoint.new(1,1)})})
 task.spawn(function()
  while bar.Parent do
   bar.Position=UDim2.new(-.3,0,.5,0)
   TweenService:Create(bar,TweenInfo.new(.9,Enum.EasingStyle.Quad,Enum.EasingDirection.InOut),{Position=UDim2.new(1.3,0,.5,0)}):Play()
   task.wait((every or 3.5)+.9)
  end
 end)
 return clip
end

-- Lime ribbon across the top edge of a card (e.g. BEST VALUE).
function FX.ribbon(card,text,width,color)
 width=width or 190
 local r=T.panel(card,'Ribbon',0,0,width,34,'button');r.AnchorPoint=Vector2.new(.5,.5);r.Position=UDim2.new(.5,0,0,0);r.ZIndex=card.ZIndex+4
 if color then T.setTier(r,4);r.RarityCorners.ImageColor3=color;r.Image=T.Asset.button end
 local l=T.label(r,'Text',text,0,0,width,34,16);l.ZIndex=card.ZIndex+5
 local s=T.make('UIScale',r,{Scale=1})
 TweenService:Create(s,TweenInfo.new(.7,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Scale=1.06}):Play()
 return r
end

-- Whole card lifts slightly on hover.
function FX.lift(card)
 local base=card.Position
 card.MouseEnter:Connect(function() TweenService:Create(card,TweenInfo.new(.15),{Position=base+UDim2.fromOffset(0,-5)}):Play() end)
 card.MouseLeave:Connect(function() TweenService:Create(card,TweenInfo.new(.15),{Position=base}):Play() end)
end

-- Colour store and quest cards (plans/2026-10-01-H-store-and-quests.md) -------------------
-- The window, tabs and buttons keep the green theme; each offer card gets a saturated backdrop.
local Text=game:GetService('TextService')
local INK=Color3.fromRGB(7,9,10)
local SLICE=Rect.new(48,48,208,208)
local function rgb(r,g,b) return Color3.fromRGB(r,g,b) end
local function fade(a,b,c)
 return ColorSequence.new({ColorSequenceKeypoint.new(0,a),ColorSequenceKeypoint.new(.55,b),ColorSequenceKeypoint.new(1,c)})
end
-- top/mid/bottom backdrop; accent: corner brackets and tag text; glow and rays behind the art;
-- tag: the hanging tag's fill; tint: the bottom of the title's white-to-tint fill.
FX.Themes={
 gold={top=rgb(255,217,104),mid=rgb(240,161,36),bottom=rgb(165,86,11),accent=rgb(255,226,96),glow=rgb(255,246,200),rays=rgb(255,243,176),tag=rgb(150,78,6),tint=rgb(255,224,138)},
 fire={top=rgb(255,138,46),mid=rgb(194,24,31),bottom=rgb(61,5,9),accent=rgb(255,140,80),glow=rgb(255,176,112),rays=rgb(255,179,107),tag=rgb(140,14,24),tint=rgb(255,194,122)},
 shadow={top=rgb(160,22,46),mid=rgb(58,10,31),bottom=rgb(12,6,16),accent=rgb(255,70,96),glow=rgb(255,46,72),rays=rgb(255,74,96),tag=rgb(70,10,28),tint=rgb(255,154,168)},
 obsidian={top=rgb(90,29,58),mid=rgb(29,22,48),bottom=rgb(9,9,16),accent=rgb(255,203,64),glow=rgb(255,64,96),rays=rgb(255,215,106),tag=rgb(110,80,14),tint=rgb(255,215,106)},
 blue={top=rgb(95,178,255),mid=rgb(42,111,206),bottom=rgb(19,46,102),accent=rgb(160,224,255),glow=rgb(159,220,255),rays=rgb(191,232,255),tag=rgb(22,74,138),tint=rgb(205,238,255)},
 purple={top=rgb(177,112,255),mid=rgb(106,43,208),bottom=rgb(42,15,94),accent=rgb(232,196,255),glow=rgb(224,168,255),rays=rgb(240,210,255),tag=rgb(80,22,150),tint=rgb(243,217,255)},
 wood={top=rgb(209,154,85),mid=rgb(138,85,36),bottom=rgb(74,42,14),accent=rgb(255,212,146),glow=rgb(255,217,160),rays=rgb(255,226,176),tag=rgb(96,56,18),tint=rgb(255,229,191)},
 red={top=rgb(255,90,98),mid=rgb(192,32,46),bottom=rgb(94,12,20),accent=rgb(255,176,182),glow=rgb(255,176,182),rays=rgb(255,192,196),tag=rgb(120,16,26),tint=rgb(255,211,214)},
 emerald={top=rgb(96,236,150),mid=rgb(24,158,88),bottom=rgb(8,70,42),accent=rgb(176,255,206),glow=rgb(200,255,220),rays=rgb(200,255,220),tag=rgb(12,90,50),tint=rgb(205,255,222)},
 steel={top=rgb(160,174,182),mid=rgb(88,100,108),bottom=rgb(36,42,46),accent=rgb(222,230,234),glow=rgb(230,236,240),rays=rgb(230,236,240),tag=rgb(60,68,74),tint=rgb(232,238,242)},
 night={top=rgb(62,73,80),mid=rgb(40,48,53),bottom=rgb(24,29,32),accent=T.Color.lime,glow=rgb(200,220,210),rays=rgb(200,220,210),tag=rgb(30,36,40),tint=rgb(235,240,236)},
 teal={top=rgb(86,226,226),mid=rgb(22,140,160),bottom=rgb(8,54,70),accent=rgb(170,255,250),glow=rgb(190,255,250),rays=rgb(200,255,250),tag=rgb(10,80,96),tint=rgb(200,255,250)},
 ember={top=rgb(150,52,22),mid=rgb(78,22,14),bottom=rgb(30,10,8),accent=rgb(255,166,70),glow=rgb(255,150,60),rays=rgb(255,170,90),tag=rgb(110,34,10),tint=rgb(255,206,140)},
}
-- Item slot colours by rarity (Emerald for emerald amounts). Godly is dark with a red rim.
FX.Rarity={
 Godly={top=rgb(112,16,38),bottom=rgb(22,4,10),glow=rgb(255,70,96),rim=rgb(255,58,82)},
 Legendary={top=rgb(255,216,99),bottom=rgb(194,116,16),glow=rgb(255,250,220)},
 Epic={top=rgb(207,149,255),bottom=rgb(101,38,176),glow=rgb(245,225,255)},
 Rare={top=rgb(118,204,255),bottom=rgb(28,102,176),glow=rgb(225,245,255)},
 Common={top=rgb(224,230,233),bottom=rgb(124,137,143),glow=rgb(255,255,255)},
 Emerald={top=rgb(90,245,154),bottom=rgb(13,127,66),glow=rgb(225,255,235)},
}
FX.ChestRarity={Wooden='Common',Silver='Rare',Gold='Legendary',Magical='Epic',Legendary='Legendary'}
FX.INK=INK

-- Chunky outlined text: T.label with a dark UIStroke and, given `tint`, a white-to-tint fill.
function FX.title(parent,name,text,x,y,w,h,size,tint)
 local l=T.label(parent,name,text,x,y,w,h,size)
 l.TextXAlignment=Enum.TextXAlignment.Left;l.TextStrokeTransparency=1
 T.make('UIStroke',l,{Color=INK,Thickness=math.clamp(math.floor(size/11),2,5),LineJoinMode=Enum.LineJoinMode.Round})
 if tint then
  T.make('UIGradient',l,{Rotation=90,Color=ColorSequence.new({ColorSequenceKeypoint.new(0,Color3.new(1,1,1)),ColorSequenceKeypoint.new(.4,Color3.new(1,1,1)),ColorSequenceKeypoint.new(1,tint)})})
 end
 -- Big titles may shrink to 45% so they still fit when the window scales down on phones.
 l.FitText.MinTextSize=math.min(l.FitText.MinTextSize,math.max(9,math.floor(size*.45)))
 return l
end

-- Offer card. Returns the coloured face (put content on it) and its theme. The face sits in a
-- holder with a drop shadow; the holder lifts on hover. theme: a FX.Themes name or table.
function FX.card(parent,name,x,y,w,h,theme,noLift)
 theme=type(theme)=='string' and FX.Themes[theme] or theme or FX.Themes.night
 local holder=T.make('Frame',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h)})
 local shadow=T.make('Frame',holder,{Name='Shadow',BackgroundColor3=INK,BackgroundTransparency=.2,BorderSizePixel=0,Position=UDim2.fromOffset(0,7),Size=UDim2.fromScale(1,1)})
 T.make('UICorner',shadow,{CornerRadius=UDim.new(0,16)})
 local face=T.make('Frame',holder,{Name='Face',BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0,Size=UDim2.fromScale(1,1)})
 T.make('UICorner',face,{CornerRadius=UDim.new(0,16)})
 T.make('UIGradient',face,{Rotation=90,Color=fade(theme.top,theme.mid,theme.bottom)})
 T.make('UIStroke',face,{Color=INK,Thickness=4,ApplyStrokeMode=Enum.ApplyStrokeMode.Border})
 local lit=T.make('Frame',face,{Name='Lit',BackgroundColor3=Color3.new(1,1,1),BackgroundTransparency=.7,BorderSizePixel=0,Position=UDim2.fromOffset(16,4),Size=UDim2.new(1,-32,0,3)})
 T.make('UICorner',lit,{CornerRadius=UDim.new(1,0)})
 -- The theme's corner brackets (the same art as the panels), in the card's accent colour.
 T.make('ImageLabel',face,{Name='Corners',BackgroundTransparency=1,Image=T.Asset.corners,ImageColor3=theme.accent,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.45,Position=UDim2.fromOffset(2,2),Size=UDim2.new(1,-4,1,-4)})
 if not noLift then FX.lift(holder) end
 return face,theme
end

-- Rays and glow behind a card's art, clipped to the card; the art itself may stick out past the
-- card's edge. Grows and tilts while the pointer is over the card.
function FX.art(face,asset,cx,cy,size,theme,raySize)
 local clip=face:FindFirstChild('RayClip') or T.make('Frame',face,{Name='RayClip',BackgroundTransparency=1,ClipsDescendants=true,Position=UDim2.fromOffset(6,6),Size=UDim2.new(1,-12,1,-12)})
 local holder,rays=FX.burst(clip,cx-6,cy-6,raySize or size*1.9,theme.rays)
 holder.Glow.ImageColor3=theme.glow;holder.Glow.ImageTransparency=.25
 local icon=T.icon(face,'Art',cx-size/2,cy-size/2,size,asset)
 FX.popIcon(face,icon,rays)
 return icon,holder
end

-- Item slot: rarity colour, a glow behind the icon, a name strip along the bottom and an optional
-- count in the corner ('×3'). `w` wide, 8% taller. Godly slots get a pulsing red rim.
function FX.tile(parent,name,x,y,w,asset,label,rarity,amount)
 local h=math.floor(w*1.08)
 local r=FX.Rarity[rarity] or FX.Rarity.Common
 local t=T.make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
 T.make('UICorner',t,{CornerRadius=UDim.new(0,12)})
 T.make('UIGradient',t,{Rotation=90,Color=ColorSequence.new(r.top,r.bottom)})
 T.make('UIStroke',t,{Color=INK,Thickness=3,ApplyStrokeMode=Enum.ApplyStrokeMode.Border})
 T.make('ImageLabel',t,{Name='Glow',BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=r.glow,ImageTransparency=.3,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(.5,0,0,math.floor(h*.38)),Size=UDim2.fromOffset(w*.95,w*.95)})
 local strip=math.max(18,math.floor(h*.26))
 local icon=T.icon(t,'Icon',math.floor(w*.16),math.floor(h*.05),math.floor(w*.68),asset)
 if r.rim then
  local rim=T.make('Frame',t,{Name='Rim',BackgroundTransparency=1,Position=UDim2.fromOffset(3,3),Size=UDim2.new(1,-6,1,-6)})
  T.make('UICorner',rim,{CornerRadius=UDim.new(0,9)})
  local stroke=T.make('UIStroke',rim,{Color=r.rim,Thickness=2.5})
  TweenService:Create(stroke,TweenInfo.new(.9,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Transparency=.65}):Play()
 end
 if label and label~='' then
  local band=T.make('Frame',t,{Name='Strip',BackgroundColor3=INK,BackgroundTransparency=.45,BorderSizePixel=0,Position=UDim2.fromOffset(4,h-strip-4),Size=UDim2.new(1,-8,0,strip)})
  T.make('UICorner',band,{CornerRadius=UDim.new(0,8)})
  local l=T.label(band,'Label',label,3,0,0,0,math.clamp(math.floor(strip*.62),11,16));l.Size=UDim2.new(1,-6,1,0);l.TextWrapped=false
  l.FitText.MinTextSize=7 -- long names in small slots on phones
 end
 if amount and amount~='' then
  local a=T.label(t,'Amount',amount,4,1,w-9,24,math.clamp(math.floor(w*.19),13,19))
  a.TextXAlignment=Enum.TextXAlignment.Right;a.TextStrokeTransparency=1;a.TextWrapped=false
  T.make('UIStroke',a,{Color=INK,Thickness=2.5})
 end
 FX.popIcon(t,icon)
 return t,icon
end

-- Button whose caption sits in the middle 70% of its height, so on small screens (where the
-- window scales down) the text never touches the button's border. Same look on desktop.
function FX.button(parent,name,text,x,y,w,h,callback,neutral)
 local b=T.button(parent,name,text,x,y,w,h,callback,neutral)
 b.Caption.AnchorPoint=Vector2.new(.5,.5);b.Caption.Position=UDim2.fromScale(.5,.5);b.Caption.Size=UDim2.new(1,-16,.7,0)
 return b
end

-- Copy on a colour card: white with a dark outline, so it reads on every backdrop.
function FX.sub(parent,name,text,x,y,w,h,size,color)
 local l=T.text(parent,name,text,x,y,w,h,size or 18,color or Color3.new(1,1,1))
 l.TextStrokeTransparency=1
 T.make('UIStroke',l,{Color=INK,Thickness=1.6,Transparency=.1})
 return l
end

-- Diagonal band across a card's top-right corner (BEST VALUE, ONE TIME). Still; no bounce.
function FX.sash(card,text,top,bottom)
 local clip=T.make('Frame',card,{Name='Sash',BackgroundTransparency=1,ClipsDescendants=true,AnchorPoint=Vector2.new(1,0),Position=UDim2.new(1,-2,0,2),Size=UDim2.fromOffset(140,140)})
 local band=T.make('Frame',clip,{Name='Band',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(92,48),Size=UDim2.fromOffset(220,30),Rotation=45,BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
 T.make('UIGradient',band,{Rotation=90,Color=ColorSequence.new(top or rgb(255,226,102),bottom or rgb(232,150,20))})
 T.make('UIStroke',band,{Color=INK,Thickness=3})
 local l=T.label(band,'Text',text,60,0,100,30,16);l.TextWrapped=false
 return clip
end

-- Tag hanging off a card's top-left edge, e.g. ONE TIME OFFER. Fill and text in the card's colours.
function FX.tag(card,text,fill,color)
 local tw=Text:GetTextSize(text,16,T.Font,Vector2.new(1000,100)).X
 local t=T.make('Frame',card,{Name='Tag',Position=UDim2.fromOffset(24,-15),Size=UDim2.fromOffset(tw+48,30),BackgroundColor3=fill or INK,BorderSizePixel=0})
 T.make('UICorner',t,{CornerRadius=UDim.new(0,8)})
 T.make('UIStroke',t,{Color=INK,Thickness=3})
 local d=T.make('Frame',t,{Name='Diamond',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(17,15),Size=UDim2.fromOffset(9,9),Rotation=45,BackgroundColor3=color or T.Color.lime,BorderSizePixel=0})
 T.make('UIStroke',d,{Color=INK,Thickness=1.5})
 local l=T.label(t,'Text',text,30,0,tw+8,30,16,color);l.TextXAlignment=Enum.TextXAlignment.Left;l.TextWrapped=false
 return t
end

-- Centred section title between lime rules and diamonds, with an optional line under it.
-- Returns the sub label (a timer can rewrite it). Takes 46 px, or 72 with a sub line.
function FX.header(parent,title,sub,y,w)
 local tw=Text:GetTextSize(title,32,T.Font,Vector2.new(2000,100)).X
 local cx=math.floor(w/2)
 local l=T.label(parent,'Header_'..title,title,cx-tw*.75-20,y,tw*1.5+40,40,32);l.TextStrokeTransparency=1
 T.make('UIStroke',l,{Color=INK,Thickness=3})
 local function rule(x0,x1,toRight)
  if x1-x0<20 then return end
  local f=T.make('Frame',parent,{Name='Rule',Position=UDim2.fromOffset(x0,y+18),Size=UDim2.fromOffset(x1-x0,4),BackgroundColor3=T.Color.lime,BorderSizePixel=0})
  T.make('UICorner',f,{CornerRadius=UDim.new(1,0)})
  T.make('UIGradient',f,{Transparency=NumberSequence.new(toRight and 0 or 1,toRight and 1 or 0)})
 end
 local function diamond(x)
  local d=T.make('Frame',parent,{Name='Diamond',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(x,y+20),Size=UDim2.fromOffset(12,12),Rotation=45,BackgroundColor3=T.Color.lime,BorderSizePixel=0})
  T.make('UIStroke',d,{Color=INK,Thickness=2})
 end
 rule(8,cx-tw/2-34,false);rule(cx+tw/2+34,w-8,true)
 diamond(cx-tw/2-22);diamond(cx+tw/2+22)
 if sub then
  local s=T.text(parent,'HeaderSub_'..title,sub,60,y+42,w-120,24,17,T.Color.cream);s.TextXAlignment=Enum.TextXAlignment.Center
  return s
 end
end

-- Progress bar with "have / need" (or `text`) printed inside, in a dark well.
function FX.progress(parent,name,x,y,w,h,ratio,text,color)
 local fill,track=T.bar(parent,name,x,y,w,h,color)
 track:FindFirstChildOfClass('UIStroke').Thickness=3
 T.setBar(fill,ratio)
 local l=T.label(track,'Count',text or '',4,0,0,0,math.min(18,h-6));l.Size=UDim2.new(1,-8,1,0);l.ZIndex=3;l.TextStrokeTransparency=1;l.TextWrapped=false
 T.make('UIStroke',l,{Color=INK,Thickness=2.5})
 return track,fill
end

-- Lime circle with a drawn check mark (no glyph, so every font shows it).
function FX.check(parent,x,y,size)
 local c=T.make('Frame',parent,{Name='Check',Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),BackgroundColor3=T.Color.lime,BorderSizePixel=0})
 T.make('UICorner',c,{CornerRadius=UDim.new(1,0)})
 T.make('UIStroke',c,{Color=INK,Thickness=2.5})
 local s=size/24
 local function bar(px,py,len,rot)
  local b=T.make('Frame',c,{Name='Mark',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(px*s,py*s),Size=UDim2.fromOffset(len*s,3.5*s),Rotation=rot,BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
  T.make('UICorner',b,{CornerRadius=UDim.new(1,0)})
 end
 bar(9,13.5,8,45);bar(14.5,11.5,12,-50)
 return c
end
return FX
