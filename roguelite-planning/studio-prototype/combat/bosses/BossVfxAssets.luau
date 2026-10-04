-- Map-boss effect asset ids (plan F Task 10). Installed as RS.RogueliteCombat.BossVfxAssets; the
-- boss-vfx-kit mesh templates (IceSpike_A..E, Obelisk_A..C, ...) are this module's children.
-- Textures: boss-vfx-kit/textures/<name>.png, uploaded 2026-09-30. The four *_BaseColor atlases
-- are the ones the 3D Importer uploaded with AllMeshes.fbx (the mesh templates' TextureID).
-- Sounds: free Creator Store audio by ProSoundEffects (see studio-prototype/ASSETS.md).
return {
	Textures = {
		ShockwaveRing = "rbxassetid://73745779894728",
		ImpactStar = "rbxassetid://132900122818559",
		DustPuff_Flipbook4x4 = "rbxassetid://108391383565832",
		WaterSplash_Flipbook4x4 = "rbxassetid://99255856772433",
		Bubble = "rbxassetid://85054572566506",
		SandSpray_Flipbook4x4 = "rbxassetid://102816833190885",
		HieroglyphCircle = "rbxassetid://91511521884695",
		Hieroglyphs_Flipbook4x4 = "rbxassetid://101187847335243",
		SandBurst_Flipbook4x4 = "rbxassetid://139727948521833",
		CurseOrb = "rbxassetid://74654623742949",
		FrostFloor = "rbxassetid://123297047697784",
		FrostRing = "rbxassetid://113178010280765",
		FrostMist_Flipbook4x4 = "rbxassetid://107929552453550",
		SnowSparkle = "rbxassetid://131064842159851",
		LavaCracks = "rbxassetid://79279164324150",
		ScorchMark = "rbxassetid://92423458342016",
		Flame_Flipbook4x4 = "rbxassetid://132081298787809",
		Ember = "rbxassetid://116159534169534",
		SmokePuff_Flipbook4x4 = "rbxassetid://133683398795549",
		MoltenRock_EmissiveMask = "rbxassetid://85870086290990",
		IceSpikes_BaseColor = "rbxassetid://91357789960141",
		MoltenRock_BaseColor = "rbxassetid://139356687572385",
		Obelisk_BaseColor = "rbxassetid://114053127280741",
		ShellChip_BaseColor = "rbxassetid://118642052631884",
		-- Hammer Brute (2026-10-03): boss-vfx-kit/textures/EarthCracks.png, white-on-clear, tinted in
		-- game. Not uploaded yet: nil until its "rbxassetid://..." goes here, and C.texture /
		-- C.plate skip the crack decals meanwhile.
		EarthCracks = nil,
	},
	-- 4x4 grid sheets, 256 px frames, left-to-right then top-to-bottom (Roblox Grid4x4).
	Flipbook = {
		DustPuff_Flipbook4x4 = "4x4",
		WaterSplash_Flipbook4x4 = "4x4",
		SandSpray_Flipbook4x4 = "4x4",
		Hieroglyphs_Flipbook4x4 = "4x4",
		SandBurst_Flipbook4x4 = "4x4",
		FrostMist_Flipbook4x4 = "4x4",
		Flame_Flipbook4x4 = "4x4",
		SmokePuff_Flipbook4x4 = "4x4",
	},
	Sounds = {
		crab_windup = "rbxassetid://9114493410", -- Floor Creaks 3 (shell creak)
		crab_slam = "rbxassetid://9113469292", -- Body Fall 1 (into sand)
		crab_scuttle = "rbxassetid://9125917343", -- Scrolling Graphic Clicks Small Chattering Metal 5
		bubbles = "rbxassetid://9120309620", -- Underwater Bubbles Deeper Med 6
		pharaoh_windup = "rbxassetid://9116394545", -- Magic Glows Soft Clusters Of Chiming Hits 1
		pharaoh_charge = "rbxassetid://9120733055", -- Whoosh Rising Swish Airy Various Pitches 1
		pharaoh_bolt = "rbxassetid://9114157695", -- Doppler Whooshes Crackly Airy Bursts 2
		stone_rumble = "rbxassetid://9118692384", -- Rocks Movement 5
		sand_burst = "rbxassetid://9118597967", -- Rock Hit Dirt Impact 10
		ice_windup = "rbxassetid://9119628762", -- Steam Whoosh Phased 1
		ice_slam = "rbxassetid://9118585250", -- Rock Cracks Big Boulder Hits 4
		ice_crack = "rbxassetid://9119311395", -- Snowball Hit Vehicle Window 1
		ice_wave = "rbxassetid://9118588626", -- Rock Drops 10 Ft High Onto Rocks Dirt 6
		dragon_windup = "rbxassetid://9113971433", -- Creature Growls Lion 2
		dragon_inhale = "rbxassetid://9126102843", -- Time Warp Searing Build Up Large Suck Rumble 4
		fire_breath = "rbxassetid://9117987723", -- Pyro Fire Ball Burst 15
		tail_whoosh = "rbxassetid://9120727859", -- Whoosh Giant Swish By 8
		ground_quake = "rbxassetid://9125484359", -- Deep Hits Big Reverberant Booms Rumbling Tail 1
		lava_hiss = "rbxassetid://9125579324", -- Giant Steam Chuff Air Burst Through The Tube 6
		wing_flap = "rbxassetid://9120771885", -- Wing Flaps 29 (FrontStomp rear gust)
		-- Hammer Brute: the game's own small kit (audio/uploaded_ids.json, RogueliteSounds) and the
		-- Roblox bundled boom the old Hammer used, pitch-shifted per use in BossVfx/Hammer.
		hammer_whoosh = "rbxassetid://71697578984386", -- swing_heaviest
		hammer_thud = "rbxassetid://100368763538547", -- hit_thud
		hammer_boom = "rbxasset://sounds/impact_explosion_03.mp3", -- Roblox bundled (old Hammer slam, BossIntro)
		zombie_roar = "rbxassetid://137815495955079", -- mob_zombie
	},
}
