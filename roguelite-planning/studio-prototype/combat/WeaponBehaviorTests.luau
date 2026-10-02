return function(combat)
 local M=require(combat.WeaponMotion)
 local P=require(combat.SpecialMotion)
 local C=require(combat.WeaponCatalog)
 local S=require(combat.CharacterStats)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 local stats=S.resolve('Brawler',1,{})
 for _,id in {'16','20','26','32'} do check(C.ById[id].kind=='Melee','Melee classification '..id) end
 check(C.ById['31'].cooldown>=1.95,'Hammer must retain a long cooldown') -- 1.97 s: Legendary power (WeaponCatalog)
 check(C.ById['05'].nativeKnockback>0 and C.ById['26'].nativeKnockback>0,'Native knockback')
 local heavy=S.weapon(C.ById['31'],stats,'Brawler',1)
 local light=S.weapon(C.ById['03'],stats,'Brawler',1)
 local chain=S.weapon(C.ById['02'],stats,'Brawler',1)
 check(math.abs(heavy.motionRate-light.motionRate)<1e-5,'Long cooldown must not slow the strike')
 check(chain.motionRate<light.motionRate,'Nunchuck animation should be slower')
 for count=1,4 do for serial=1,6 do check(M.chooseStyle('32',count,serial)=='Horizontal','Excalibur horizontal only') end end
 local root=CFrame.new(10,25,10)*CFrame.Angles(0,1,0);local target=Vector3.new(10,4,5)
 local attack=M.attackRoot(root,target)
 check(math.abs(attack.Y+.25-target.Y)<1e-5,'Jump-height compensation')
 for _,id in {'03','16','20','26','32'} do
  local template=combat.WeaponTemplates[id];local size=template:GetAttribute('BoundsSize');local center=template:GetAttribute('BoundsCenter')
  for _,style in {'Horizontal','Diagonal','Thrust','Downward','Slap'} do
   local last
   for step=0,60 do
    local cf=M.pose(attack,4.2,1,target,0,M.SwingHitEnd*step/60,'Melee',id,Vector3.new(0,0,-1),8,size,center,style)
    for _,v in {cf:GetComponents()} do check(v==v and math.abs(v)<1e5,'Finite pose') end
    if last then check((cf.Position-last.Position).Magnitude<1.5,'Active motion discontinuity') end
    last=cf
   end
   local idle=M.pose(root,4.2,1,nil,0,1e6,'Melee',id)
   local state={};local a=M.swingReturn(last,idle,M.SwingHitEnd,state,id,style)
   check((a.Position-last.Position).Magnitude<.001 and a.UpVector:Dot(last.UpVector)>.999,'Recovery starts at cut')
   local b=M.swingReturn(last,idle,M.SwingDuration,state,id,style)
   check((b.Position-idle.Position).Magnitude<.001 and b.UpVector:Dot(idle.UpVector)>.999,'Recovery returns to moving idle')
  end
 end
 local size=combat.WeaponTemplates['03']:GetAttribute('BoundsSize')
 local a=M.pose(attack,4.2,1,target,0,0,'Melee','03',Vector3.new(0,0,-1),11,size,Vector3.zero,'Thrust')
 check(a.Position.Z+size.Y*.5<attack.Z-1,'Thrust grip must begin outside avatar')
 local b=M.pose(attack,4.2,1,target,0,M.SwingHitEnd,'Melee','03',Vector3.new(0,0,-1),11,size,Vector3.zero,'Thrust')
 check(b.Position.Z+size.Y*.5<=target.Z+.5,'Grip should follow blade through target')
 for id,p in P.profiles do
  local origin,finish=Vector3.new(0,4,0),Vector3.new(6,4,-10)
  check((P.position(origin,finish,0,p.height)-origin).Magnitude<1e-5,'Launch endpoint '..id)
  check((P.position(origin,finish,1,p.height)-finish).Magnitude<1e-5,'Impact endpoint '..id)
 end
 check(P.profiles['13'].height==0,'Kunai flies straight')
 check(P.profiles['12'].returns and P.profiles['31'].returns,'Returning weapon definitions')
 check(P.profiles['14'].zone=='Fire' and P.profiles['08'].zone=='Poison','Lingering zones')
 check(P.profiles['15'].reserve and P.profiles['23'].reserve,'Three-model reserves')
 return {checks=checks}
end
