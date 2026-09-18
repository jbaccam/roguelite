-- One-third-size independent display copies; run once after material corrections.
local large=assert(workspace:FindFirstChild('RogueliteWeaponShowcase'))
assert(not workspace:FindFirstChild('RogueliteWeaponShowcase_PlaySize'),'Small showcase already exists')
local small=Instance.new('Folder');small.Name='RogueliteWeaponShowcase_PlaySize';small:SetAttribute('RelativeWeaponScale',1/3);small.Parent=workspace
local bases=Instance.new('Folder');bases.Name='DisplayBases';bases.Parent=small
local count=0
for _,source in large:GetChildren()do
 if source:IsA('Model')and source:GetAttribute('WeaponIndex')then
  local idx=source:GetAttribute('WeaponIndex');local m=source:Clone();m.Parent=small
  m:ScaleTo(source:GetScale()/3);m:SetAttribute('RelativeWeaponScale',1/3)
  local cf,s=m:GetBoundingBox();local origin=Vector3.new(45+(idx%6)*5,2.65,500+math.floor(idx/6)*5)
  m:PivotTo(CFrame.new(origin-Vector3.new(cf.X,cf.Y-s.Y/2,cf.Z))*m:GetPivot())
  local p=Instance.new('Part');p.Name=string.format('Base_%02d',idx);p.Size=Vector3.new(3.6,.3,3.6);p.Position=Vector3.new(origin.X,2.15,origin.Z);p.Anchored=true;p.Color=Color3.fromRGB(43,51,61);p.Material=Enum.Material.SmoothPlastic;p.Parent=bases
  local plaque=Instance.new('Part');plaque.Name='Label';plaque.Size=Vector3.new(3.3,.08,.65);plaque.Position=Vector3.new(origin.X,2.37,origin.Z+1.38);plaque.Anchored=true;plaque.CanCollide=false;plaque.Color=Color3.fromRGB(30,35,43);plaque.Parent=p
  local gui=Instance.new('SurfaceGui');gui.Face=Enum.NormalId.Top;gui.SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud;gui.PixelsPerStud=100;gui.LightInfluence=0;gui.Parent=plaque
  local text=Instance.new('TextLabel');text.Size=UDim2.fromScale(1,1);text.BackgroundTransparency=1;text.Text=source:GetAttribute('DisplayName');text.TextColor3=Color3.fromRGB(240,241,235);text.TextScaled=true;text.Font=Enum.Font.GothamMedium;text.Parent=gui
  count+=1
 end
end
assert(count==36)
for _,folder in {large,small}do
 for _,p in folder:GetDescendants()do if p:IsA('BasePart')then p.TopSurface=Enum.SurfaceType.Smooth;p.BottomSurface=Enum.SurfaceType.Smooth end end
end
local function sign(parent,name,text,pos,width)
 local p=Instance.new('Part');p.Name=name;p.Size=Vector3.new(width,2.4,.25);p.Position=pos;p.Anchored=true;p.CanCollide=false;p.Color=Color3.fromRGB(35,43,54);p.Parent=parent
 local g=Instance.new('SurfaceGui');g.Face=Enum.NormalId.Back;g.CanvasSize=Vector2.new(1200,180);g.LightInfluence=0;g.Parent=p
 local t=Instance.new('TextLabel');t.Size=UDim2.fromScale(.94,.8);t.Position=UDim2.fromScale(.03,.1);t.BackgroundTransparency=1;t.Text=text;t.TextScaled=true;t.TextColor3=Color3.fromRGB(241,240,230);t.Font=Enum.Font.GothamMedium;t.Parent=g
end
sign(small,'PlaySizeSign','PLAY SIZE  /  ONE-THIRD SCALE',Vector3.new(57.5,5,496.5),22)
sign(large,'LargeDisplaySign','LARGE WEAPON DISPLAY',Vector3.new(127.5,5,455),28)
game:GetService('Selection'):Set({})
workspace.CurrentCamera.CFrame=CFrame.lookAt(Vector3.new(82,62,568),Vector3.new(102,3,494))
game:GetService('ChangeHistoryService'):SetWaypoint('Added 36 one-third-size weapon displays')
return 'Created 36 small weapon models with independent rigs and loose components'
