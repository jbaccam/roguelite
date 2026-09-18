-- Studio practice tuning. IDs match the reviewed, user-sized showcase models.
local C={Slots=6, List={}, ById={}}
local names={'Glock','Frying Pan','Nunchucks','Katana','Kusarigama','Spatula','Baseball Bat','Draco','Fart Gun','Shotgun','T-Shirt Cannon','Rocket Launcher','Boomerang','Kunai','Molotov','Egg','Steak','Rubber Duck','Deck of Cards','Boxing Gloves','Cinder Block','Yo-Yo','Bowling Ball','Bowling Pin','Nail Gun','Wrecking Ball','Shovel','Paint Roller','Vacuum Cleaner','Power Washer','Magic Staff','Mjolnir','Excalibur',"Pandora's Box","Medusa's Head",'Crystal Ball'}
local ranged={[0]=true,[7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true,[13]=true,[14]=true,[15]=true,[18]=true,[22]=true,[24]=true,[28]=true,[29]=true,[30]=true,[33]=true,[34]=true,[35]=true}
for i,name in names do
 local n=i-1
 local kind=ranged[n] and 'Ranged' or 'Melee'
 if n==11 or n==14 then kind='Blast' elseif n==9 then kind='Spread' end
 local d={id=string.format('%02d',n),name=name,kind=kind,damage=kind=='Melee' and 25 or 16,cooldown=kind=='Melee' and .65 or .6,range=kind=='Melee' and 6 or 45}
 if kind=='Blast' then d.damage=40;d.cooldown=1.5;d.range=50 end
 if kind=='Spread' then d.damage=12;d.cooldown=.95;d.range=24 end
 if n==7 or n==24 then d.damage=9;d.cooldown=.22 end
 if n==11 then d.damage=70;d.cooldown=2.8;d.range=70;d.projectileSpeed=55;d.blastRadius=9 end
 if n==3 then d.damage=25;d.cooldown=.58 end
 d.home=n>=30 and 'Mage' or (n>=24 and 'Handyman' or (n>=17 and n~=18 and 'Juggler' or (n>=12 and 'Thrower' or (n==0 or n>=7) and 'Gunner' or 'Brawler')))
 if n==16 then d.kind='Ranged';d.range=32 end
 if n==17 or n==20 or n==21 or n==23 then d.kind='Ranged';d.range=28 end
 d.elemental=d.home=='Mage' or n==8 or n==14
 d.utility=d.home=='Handyman'
 d.burn=n==14 and 100 or 0;d.poison=n==8 and 100 or 0;d.slow=n==34 and 100 or 0;d.lightning=n==30 or n==31
 d.tags={d.kind=='Melee' and 'Melee' or 'Projectile',d.home}
 if d.elemental then table.insert(d.tags,'Elemental') end
 if d.utility then table.insert(d.tags,'Utility') end
 table.insert(C.List,d);C.ById[d.id]=d
end
function C.validSlot(slot)
 return type(slot)=='number' and slot==slot and slot%1==0 and slot>=1 and slot<=C.Slots
end
function C.validate(slot,id)
 return C.validSlot(slot) and type(id)=='string' and (id=='' or C.ById[id]~=nil)
end
return C
