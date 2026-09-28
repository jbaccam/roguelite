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
return FX
