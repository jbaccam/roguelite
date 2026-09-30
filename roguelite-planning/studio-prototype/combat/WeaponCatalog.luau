-- Studio practice tuning. IDs match the reviewed, user-sized showcase models.
local C={Slots=6, List={}, ById={}}
local names={'Glock','Frying Pan','Nunchucks','Katana','Kusarigama','Spatula','Baseball Bat','Draco','Fart Gun','Shotgun','T-Shirt Cannon','Rocket Launcher','Boomerang','Kunai','Molotov','Egg','Steak','Rubber Duck','Deck of Cards','Boxing Gloves','Cinder Block','Yo-Yo','Bowling Ball','Bowling Pin','Nail Gun','Wrecking Ball','Shovel','Paint Roller','Vacuum Cleaner','Power Washer','Magic Staff','Mjolnir','Excalibur',"Pandora's Box","Medusa's Head",'Crystal Ball'}
local ranged={[0]=true,[7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true,[13]=true,[14]=true,[15]=true,[18]=true,[22]=true,[24]=true,[28]=true,[29]=true,[30]=true,[33]=true,[34]=true,[35]=true}
-- Tiers trade two copies for one stronger copy; some weapons improve crowd handling.
-- Range is in Roblox studs. Damage is per hit (Deck of Cards: total three-card volley).
local profiles={
 {12,.72,45,{12,18,27,40}}, -- Glock
 {16,1.05,6,{16,25,39,60}}, -- Pan
 {6,.5,6,{6,9,14,21}}, -- Nunchucks
 {18,.95,11,{18,27,41,62}}, -- Katana
 {15,1.15,12,{15,23,35,53}}, -- Kusarigama
 {9,.55,6,{9,14,21,32}}, -- Spatula
 {20,1.25,8,{20,30,46,70}}, -- Bat
 {3,.17,42,{3,4,6,9}}, -- Draco
 {4,.8,28,{4,6,9,14}}, -- Fart Gun (poison)
 {3,1.1,24,{3,4,5,7},nil,'pellets'}, -- Shotgun
 {18,1.35,40,{18,27,40,60},nil,'pierce'}, -- T-shirt
 {32,2.4,70,{32,48,72,108}}, -- Rocket
 {7,.9,35,{7,10,14,20},nil,'bounce'}, -- Boomerang
 {6,.48,38,{6,9,14,21},nil,'pierce'}, -- Kunai
 {3,1.7,38,{3,5,8,12}}, -- Molotov (burn)
 {10,.85,32,{10,15,23,35}}, -- Egg
 {16,.85,6,{16,24,36,54}}, -- Steak
 {5,.32,12,{5,8,12,18},nil,'bounce'}, -- Duck
 {15,.95,42,{15,21,30,42},nil,'cards'}, -- Cards
 {8,.42,6.5,{8,15,28,48},{1,.94,.88,.76}}, -- Gloves: alternating quick jabs (T4 ~150 DPS: the close-range trade)
 {30,1.35,7,{30,45,68,102}}, -- Block
 {8,.7,28,{8,12,18,27},nil,'bounce'}, -- Yo-yo
 {24,1.6,35,{24,36,54,81},nil,'pierce'}, -- Ball
 {13,1.25,28,{13,20,30,45}}, -- Pin
 {4,.28,40,{4,6,8,12},nil,'pierce'}, -- Nails
 {28,1.6,12,{28,42,63,95}}, -- Wrecking ball
 {18,1.15,8,{18,28,42,64}}, -- Shovel
 {10,.8,9,{10,15,23,35}}, -- Roller
 {4,.32,20,{4,6,9,14}}, -- Vacuum
 {3,.24,30,{3,4,6,9},nil,'pierce'}, -- Washer
 {9,1.15,45,{9,14,21,32}}, -- Staff (arcane energy orb)
 {22,2.4,8,{22,33,50,75}}, -- Mjolnir
 {26,1.35,8.5,{26,39,59,89}}, -- Excalibur
 {25,2,50,{25,38,57,86}}, -- Pandora
 {5,1.2,38,{5,8,12,18},nil,'shots'}, -- Medusa (slow)
 {13,1.05,48,{13,20,30,45},nil,'bounce'}, -- Crystal (lightning)
}
for i,name in names do
 local n=i-1
 local kind=ranged[n] and 'Ranged' or 'Melee'
 if n==11 or n==14 or n==33 then kind='Blast' elseif n==9 then kind='Spread' end
 local d={id=string.format('%02d',n),name=name,kind=kind}
 -- Damage/cooldown pairs are authored per weapon, not shared by an entire class.
 local profile=profiles[i]
 d.damage=profile[1];d.cooldown=profile[2];d.range=profile[3]
 d.tierDamage=profile[4];d.tierCooldown=profile[5] or {1,.95,.9,.84}
 d.trait=profile[6] or ''
 if n==10 then d.projectileSpeed=48 end
 if n==11 then d.projectileSpeed=80;d.blastRadius=9 end
 if n==18 then d.projectileSpeed=90 end
 if n==33 then d.projectileSpeed=45;d.blastRadius=7 end
 d.home=n>=30 and 'Mage' or (n>=24 and 'Handyman' or (n>=17 and n~=18 and 'Juggler' or (n>=12 and 'Thrower' or (n==0 or n>=7) and 'Gunner' or 'Brawler')))

 if n==17 or n==21 or n==23 then d.kind='Ranged' end
 d.nativeKnockback=(n==5 and 14 or n==26 and 20 or n==20 and 16 or 0)
 if n==31 then d.hybridRange=32;d.projectileSpeed=42 end
 if n==8 then d.projectileSpeed=150 end
 local thrownSpeed={[12]=40,[13]=65,[14]=28,[15]=35,[22]=32,[23]=24}
 if thrownSpeed[n] then d.projectileSpeed=thrownSpeed[n] end
 d.elemental=d.home=='Mage' or n==8 or n==14 or n==17
 d.utility=d.home=='Handyman'
 d.burn=n==14 and 100 or 0;d.poison=n==8 and 100 or 0;d.slow=n==34 and 100 or 0;d.lightning=n==35 or n==31
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
