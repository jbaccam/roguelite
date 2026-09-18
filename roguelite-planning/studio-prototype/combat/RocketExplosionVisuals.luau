-- Supplied transparent artwork, cropped at display time; no image pixels edited.
-- Roblox serves these uploaded 1254px atlases at 1024px texture resolution.
local RunService=game:GetService('RunService')
local V={}
local smallAtlas='rbxassetid://99550847281506'
local largeAtlas='rbxassetid://120401440349556'
function V.mount(visuals)
 local active={}
 local serial=0
 local function sprite(position,studs,central,variant,delay,duration)
  if #active>=144 then local old=table.remove(active,1);old.anchor:Destroy() end
  local anchor=Instance.new('Part');anchor.Name=central and 'RPGImpactBurst' or 'RPGScatterBurst'
  anchor.Size=Vector3.one*.05;anchor.Transparency=1;anchor.Anchored=true
  anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.CastShadow=false
  anchor.Position=position;anchor.Parent=visuals
  local gui=Instance.new('BillboardGui');gui.Name='ExplosionSprite';gui.Adornee=anchor
  gui.AlwaysOnTop=false;gui.LightInfluence=0;gui.MaxDistance=150;gui.Size=UDim2.fromOffset(1,1);gui.Parent=anchor
  local picture=Instance.new('ImageLabel');picture.BackgroundTransparency=1;picture.Size=UDim2.fromScale(1,1)
  picture.Image=central and largeAtlas or smallAtlas;picture.ImageTransparency=1
  picture.Rotation=(variant%5-2)*(central and 5 or 11)
  if central then
   picture.ImageRectOffset=Vector2.new((variant%2)*512,0);picture.ImageRectSize=Vector2.new(512,512)
  else
   local cell=variant%16;local col,row=cell%4,math.floor(cell/4)
   local x,y=math.floor(col*1024/4),math.floor(row*1024/4)
   picture.ImageRectOffset=Vector2.new(x,y)
   picture.ImageRectSize=Vector2.new(math.floor((col+1)*1024/4)-x,math.floor((row+1)*1024/4)-y)
  end
  picture.Parent=gui
  table.insert(active,{anchor=anchor,gui=gui,picture=picture,studs=studs,central=central,born=workspace:GetServerTimeNow()+delay,duration=duration})
 end
 RunService.RenderStepped:Connect(function()
  local camera=workspace.CurrentCamera;if not camera then return end
  local now=workspace:GetServerTimeNow()
  local focal=camera.ViewportSize.Y/(2*math.tan(math.rad(camera.FieldOfView)/2))
  for i=#active,1,-1 do
   local effect=active[i];local age=now-effect.born
   if age>=effect.duration then effect.anchor:Destroy();table.remove(active,i)
   elseif age>=0 then
    local t=age/effect.duration
    local grow=math.clamp(age/.07,0,1);grow=1-(1-grow)^3
    local scale=(.55+.5*grow)*(1-.18*t)
    local depth=math.max(.5,(effect.anchor.Position-camera.CFrame.Position):Dot(camera.CFrame.LookVector))
    local cap=math.min(effect.central and 150 or 65,math.min(camera.ViewportSize.X,camera.ViewportSize.Y)*(effect.central and .22 or .10))
    local pixels=math.min(cap,effect.studs*focal/depth)*scale
    effect.gui.Size=UDim2.fromOffset(pixels,pixels)
    local fade=math.clamp((t-.28)/.72,0,1)
    effect.picture.ImageTransparency=fade*fade*(3-2*fade)
   end
  end
 end)
 return function(position,radius)
  local camera=workspace.CurrentCamera
  if not camera or (position-camera.CFrame.Position).Magnitude>150 then return end
  serial+=1
  local rng=Random.new(serial*7919)
  radius=math.max(.5,radius)
  -- Two compact overlapping bursts emphasize contact, not a sphere filling the radius.
  sprite(position+Vector3.yAxis*.3,math.min(4.8,radius*.6),true,serial,0,.4)
  sprite(position+Vector3.new(.65,.8,.2),math.min(2.6,radius*.35),true,serial+1,.035,.33)
  -- Sparse satellites cover the damage footprint while leaving the scene visible.
  for i=1,7 do
   local angle=(i-1)*math.pi*2/7+rng:NextNumber(-.16,.16)
   local distance=radius*(i%3==0 and .42 or rng:NextNumber(.65,.85))
   local size=rng:NextNumber(.95,1.9)*math.min(1,radius/5)
   local offset=Vector3.new(math.cos(angle)*distance,rng:NextNumber(-.25,.6),math.sin(angle)*distance)
   sprite(position+offset,size,false,serial*7+i,rng:NextNumber(.015,.065),rng:NextNumber(.25,.36))
  end
 end
end
return V
