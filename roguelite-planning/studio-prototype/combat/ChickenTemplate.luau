-- Self-contained articulated chicken when the reviewed derp-chicken import is unavailable.
-- Imported ServerStorage.RogueliteAllies.EggChicken always wins. Six existing animation joints,
-- warm cream feather panels, mismatched eyes, comb, beak/tongue and three-toed feet; no asset calls.
local T={}
function T.build()
 local model=Instance.new('Model');model.Name='EggChicken'
 local cream=Color3.fromRGB(246,232,195);local white=Color3.fromRGB(255,249,226)
 local shade=Color3.fromRGB(222,195,148);local gold=Color3.fromRGB(245,168,48)
 local red=Color3.fromRGB(204,62,48);local black=Color3.fromRGB(39,30,29)
 local function part(name,size,position,color,shape)
  local p=Instance.new('Part');p.Name=name;p.Size=size;p.CFrame=CFrame.new(position);p.Color=color
  p.Shape=shape or Enum.PartType.Block;p.Material=Enum.Material.SmoothPlastic
  p.Anchored=false;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.Massless=true
  p.TopSurface=Enum.SurfaceType.Smooth;p.BottomSurface=Enum.SurfaceType.Smooth;p.Parent=model;return p
 end
 local function attach(parent,child)
  local weld=Instance.new('WeldConstraint');weld.Part0=parent;weld.Part1=child;weld.Parent=child
 end
 -- Default Humanoid has zero hip lift: the invisible root reaches the soles. No privileged
 -- AvatarAppearance/HipHeight property is needed by this sandboxed runtime fallback.
 local root=part('HumanoidRootPart',Vector3.new(.9,1.7,1.15),Vector3.new(0,.85,0),white)
 root.Transparency=1;root.Massless=false;root.CanCollide=true;root.CastShadow=false
 local body=part('Chicken_Body',Vector3.new(1.12,1.1,1.45),Vector3.new(0,1.12,.18),cream,Enum.PartType.Ball)
 local bib=part('CreamBib',Vector3.new(.83,.84,.3),Vector3.new(0,1.12,-.4),white,Enum.PartType.Ball);attach(body,bib)
 local head=part('Chicken_Head',Vector3.new(.82,.84,.84),Vector3.new(0,1.76,-.63),white,Enum.PartType.Ball)
 for i=-1,1 do
  local comb=part('CombLobe',Vector3.new(.18,.26+(i==0 and .12 or 0),.3),Vector3.new(0,2.2+(i==0 and .04 or 0),-.63+i*.22),red,Enum.PartType.Ball);attach(head,comb)
 end
 for _,side in {-1,1} do
  local eye=part('GooglyEye',Vector3.one*(side==1 and .34 or .29),Vector3.new(side*.32,1.85,-.92),white,Enum.PartType.Ball);attach(head,eye)
  local pupil=part('Pupil',Vector3.one*.14,eye.Position+Vector3.new(side*.025,side*.035,-.125),black,Enum.PartType.Ball);attach(head,pupil)
  local glint=part('EyeHighlight',Vector3.one*.045,pupil.Position+Vector3.new(-.025,.035,-.06),white,Enum.PartType.Ball);attach(head,glint)
 end
 local beak=part('Beak',Vector3.new(.37,.18,.38),Vector3.new(0,1.6,-1.12),gold);beak.CFrame*=CFrame.Angles(math.rad(9),0,0);attach(head,beak)
 local lower=part('LowerBeak',Vector3.new(.3,.10,.29),Vector3.new(0,1.45,-1.08),Color3.fromRGB(227,134,32));attach(head,lower)
 local tongue=part('DerpyTongue',Vector3.new(.12,.07,.3),Vector3.new(.09,1.5,-1.27),Color3.fromRGB(239,123,126),Enum.PartType.Ball);attach(head,tongue)
 local wattle=part('Wattle',Vector3.new(.18,.31,.18),Vector3.new(-.09,1.33,-.99),red,Enum.PartType.Ball);attach(head,wattle)
 local function joint(name,parent,child,pivot)
  local cf=CFrame.new(pivot);local j=Instance.new('Motor6D');j.Name=name;j.Part0=parent;j.Part1=child
  j.C0=parent.CFrame:ToObjectSpace(cf);j.C1=child.CFrame:ToObjectSpace(cf);j.Parent=child
 end
 joint('Body',root,body,Vector3.new(0,.85,0));joint('Neck',body,head,Vector3.new(0,1.5,-.45))
 for _,side in {-1,1} do
  local name=side<0 and 'Left' or 'Right'
  local wing=part('Chicken_'..name..'Wing',Vector3.new(.2,.61,.95),Vector3.new(side*.57,1.14,.19),white,Enum.PartType.Ball)
  for i=1,3 do
   local feather=part('WingFeather',Vector3.new(.08,.30,.19),Vector3.new(side*.665,.99,.05+(i-1)*.20),i%2==0 and cream or shade,Enum.PartType.Ball);attach(wing,feather)
  end
  joint(name..'Wing',body,wing,Vector3.new(side*.48,1.4,-.08))
  local leg=part('Chicken_'..name..'Leg',Vector3.new(.14,.45,.14),Vector3.new(side*.28,.37,-.04),gold)
  for toe=-1,1 do
   local foot=part('Toe',Vector3.new(.085,.09,.33),Vector3.new(side*.28+toe*.105,.14,-.15),gold)
   foot.CFrame*=CFrame.Angles(0,math.rad(toe*18),0);attach(leg,foot)
  end
  joint(name..'Hip',root,leg,Vector3.new(side*.28,.60,-.04))
 end
 for i=-1,1 do
  local tail=part('TailFeather',Vector3.new(.25,.47,.36),Vector3.new(i*.19,1.39,.89),i==0 and white or cream,Enum.PartType.Ball)
  tail.CFrame*=CFrame.Angles(math.rad(30),0,math.rad(-i*16));attach(body,tail)
 end
 local h=Instance.new('Humanoid');h.RequiresNeck=false;h.BreakJointsOnDeath=false
 -- DisplayDistanceType/HealthDisplayType also require AvatarAppearance. Keep default display
 -- settings rather than expanding runtime capabilities just to hide an optional nameplate.
 h.UseJumpPower=true;h.JumpPower=32
 h.WalkSpeed=22;h.MaxSlopeAngle=50;h.Parent=model;model.PrimaryPart=root
 model:SetAttribute('ProceduralChickenFallback',true)
 model:SetAttribute('GroundOffset',.85)
 return model
end
return T
