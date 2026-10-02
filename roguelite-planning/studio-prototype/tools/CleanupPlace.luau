--!nonstrict
-- Edit-mode place cleanup for launch-audit L3/L4. The rows, the reasons and the lookup results are
-- in plans/2026-10-02-cleanup-manifest.md; MANIFEST below must match that table.
-- With tools/dev_server.py running, call from execute_luau (Edit) or the command bar:
--   local HS=game:GetService('HttpService')
--   local run=loadstring(HS:GetAsync('http://127.0.0.1:8934/studio-prototype/tools/CleanupPlace.luau?t='..os.clock(),true))()
--   return run()                 -- DRY RUN (the default): verifies everything, changes nothing
--   return run({apply=true})     -- removes every 'safe' row and anchors Lantern_Post_41
-- Options:
--   apply              false: only report. true: verify again, then change the place.
--   alsoDelete         ids of 'risky' rows to include (ids are printed by the dry run).
--   restoreLantern     false. true also moves Lantern_Post_41 back to its mirrored spot
--                      (-1460, 122.917, -13) and gives it a WarmLens copied from Lantern_Post_42's.
--   useOuterRecording  false. If ChangeHistoryService:TryBeginRecording returns nil because a
--                      recording is already open (the caller's wrapper), run inside that one.
-- All or nothing: every selected row must match exactly (parent, name, class, descendant count;
-- pivot for duplicates), and the reference, script-source, tag and baseplate checks must all pass
-- before anything changes. Removal is Parent=nil (not Destroy) inside one ChangeHistoryService
-- recording, so a single Undo brings everything back until the place is saved and closed.
-- Save an archive copy of the place (File > Save to File As) before apply=true.
return function(opts)
	opts = opts or {}
	local apply = opts.apply == true
	local RunService = game:GetService("RunService")
	local History = game:GetService("ChangeHistoryService")
	local SS = game:GetService("ServerStorage")
	local report = {}
	local function say(line)
		table.insert(report, line)
	end
	local function abort(why)
		table.insert(report, 1, "ABORT: " .. why .. " (nothing was changed)")
		return table.concat(report, "\n")
	end

	---------------------------------------------------------------------------------------------
	-- Manifest (snapshot 2026-10-02). verdict 'safe' rows are removed by apply; 'risky' rows only
	-- when their id is in opts.alsoDelete. Rows not listed here are never touched.
	---------------------------------------------------------------------------------------------
	local MANIFEST = {}
	local function row(verdict, cat, parent, name, class, desc, pos, size)
		table.insert(MANIFEST, {
			verdict = verdict,
			cat = cat,
			parent = parent,
			name = name,
			class = class,
			desc = desc,
			pos = pos,
			size = size,
		})
	end
	local function backup(name, class, desc)
		row("safe", "backup", "ServerStorage", name, class, desc)
	end
	local function oldLobby(name, class, desc)
		row("safe", "old lobby", "ServerStorage", name, class, desc)
	end
	local function oldImport(name, class, desc)
		row("safe", "old raw import", "ServerStorage", name, class, desc)
	end
	local function today(name, desc)
		row("risky", "today's backup", "ServerStorage", name, "Folder", desc)
	end

	-- ServerStorage: backups made before 2026-10-02 ("Before..." and other undo copies).
	backup("BeforeShardAura_20260922", "LocalScript", 0)
	backup("BeforeKatanaCombat", "Folder", 0)
	backup("BeforeSixWeaponSlots", "Folder", 3)
	backup("MapPBR_Backup_20260920", "Folder", 1)
	backup("BeforeWeaponFollow_20260921", "Folder", 3)
	backup("BeforeMovementTuning_20260921", "Folder", 2)
	backup("BeforeDirectionalFollow_20260921", "Folder", 2)
	backup("BeforeAirSpeedBoost_20260921", "Folder", 2)
	backup("BeforeKatanaDragCorrection_20260921", "Folder", 3)
	backup("BeforeWeaponSpacingOrientation_20260921", "Folder", 15)
	backup("BeforeIndependentWeaponFollow_20260922", "Folder", 6)
	backup("BeforeLauncherRearBoreScripts_20260922", "Folder", 1)
	backup("BeforeLauncherRearBore_20260922", "Folder", 9)
	backup("BeforeExcaliburSwingAndStaggeredFollow_20260922", "Folder", 3)
	backup("BeforeExcaliburReturnAndReach_20260922", "Folder", 4)
	backup("BeforeWeaponAttackStagger_20260922", "Folder", 3)
	backup("BeforeIndependentAttackClocks_20260922", "Folder", 1)
	backup("BeforeMirroredExcaliburSwings_20260922", "Folder", 3)
	backup("BeforeCuratedMobImpactFX_20260922", "Folder", 3)
	backup("BeforeSeparateVisibleHitImpact_20260922", "Folder", 1)
	backup("BeforeStrongerHitImpacts_20260922", "Folder", 1)
	backup("BeforeAllMeleeNormalSwings_20260922", "Folder", 4)
	backup("BeforeKatanaTrailAndTestControls_20260922", "Folder", 7)
	backup("BeforeKatanaSwingEdge_20260922", "Folder", 1)
	backup("BeforeControlledChainSwings_20260922", "Folder", 2)
	backup("BeforeChainEndDirection_20260922", "Folder", 3)
	backup("BeforeCrystalShards_20260922", "Folder", 8)
	backup("BeforeShardMagnet_20260922", "Folder", 5)
	backup("BeforeCurvedAttacks_20260922", "Folder", 10)
	backup("BeforeShardXP_20260922", "Folder", 5)
	backup("BeforeRetarget_20260922", "Folder", 6)
	backup("BeforeChainReadability", "Folder", 38)
	backup("BeforeMuzzleFlash_20260922", "Folder", 0) -- two folders share this name: the empty one
	backup("BeforeMuzzleFlash_20260922", "Folder", 3) -- and the one holding 3 scripts
	backup("BeforeWeaponBehaviorPass_20260923", "Folder", 6)
	backup("BeforeSpringCombos_20260923", "Folder", 7)
	backup("BeforeGripSwing_20260923", "Folder", 1)
	backup("BeforeHammerRock_20260923", "Folder", 3)
	backup("BeforeOverheadRhythm_20260923", "Folder", 2)
	backup("BeforeAllOverheadReach_20260923", "Folder", 2)
	backup("BeforeHammerBossContinuity_20260923", "Folder", 99)
	backup("BeforeHammerBossSkinGrip_20260923", "Folder", 99)
	backup("BeforeHammerBoss_20260923", "Folder", 3)
	backup("BeforeHammerBossTraps_20260923", "Folder", 131)
	backup("BeforeHammerBossHips_20260923", "Folder", 134)
	backup("BeforeHammerBossLever_20260923", "Folder", 135)
	backup("BeforeTravelAccuracy_20260923", "Folder", 12)
	backup("BeforeHammerBossPolish_20260923", "Folder", 10)
	backup("BeforeHammerBossWrist_20260923", "Folder", 9)
	backup("BeforeHammerBossElbowHinge", "Folder", 9)
	backup("BeforeHammerBossArmFlex_20260923", "Folder", 9)
	backup("BeforeHammerBossExtendedReach", "Folder", 9)
	backup("BeforeHammerBossFaceFollowThrough", "Folder", 9)
	backup("BeforeDesignerShirt_20260924", "Folder", 8)
	backup("BeforeHammerBossShoulderSweep", "Folder", 9)
	backup("BeforeBossDirectRecovery", "Folder", 10)
	backup("BeforeMobAttacks_20260927", "Folder", 1241)
	backup("BeforeGreenThemeHUD_20260927", "Folder", 9)
	backup("BeforeMonetizationDeath_20260927", "Folder", 7)
	backup("BeforeQueuePads_20260927", "Folder", 6)
	backup("BeforeStoreTabs_20260927", "Folder", 7)
	backup("BeforeRunSetup_20260927", "Folder", 4)
	backup("BeforeStorePolish_20260927", "Folder", 4)
	backup("BeforeQueueScreen_20260927", "Folder", 7)
	backup("BeforeStationFix", "Folder", 130) -- holds Lantern_Post_41's old WarmLens (see restoreLantern)
	backup("BeforeArmoryScreen_20260927", "Folder", 4)
	backup("BeforeLockedMapSilhouette_20260927", "Folder", 3)
	backup("BeforeMobPicker_20260927", "Folder", 4)
	backup("BeforeJumpableProps_20260928", "Folder", 135)
	backup("BeforeWaveSpeedSpawns_20260928", "Folder", 11)
	backup("BeforeLoadoutStarter_20260928", "Folder", 9)
	backup("BeforeSoundEffects_20260928", "Folder", 9)
	backup("BeforeSoundCueFix_20260928", "Folder", 2)
	backup("BeforeMusicAndSliders_20260928", "Folder", 4)
	backup("BeforeThreeArenas_20260930", "Folder", 6)
	backup("BeforeBossSync_20260930", "Folder", 8)
	backup("BeforeMapBoss_20260930", "Folder", 405)
	backup("BeforeBossBalance_20260930", "Folder", 9)
	backup("BeforeHammerCharge_20260930", "Folder", 7)
	backup("BeforeOriginalArenaRefresh_20261001", "Folder", 988)
	backup("BeforeGeneratedItemIcons_20261001", "Folder", 7)
	backup("BeforeTemplateScale_20261001", "Folder", 3522)
	backup("Weapon_Material_Correction_Backup", "Folder", 69)
	backup("SkyBackup_BeforeOriginalPaintedClouds", "Folder", 3)
	backup("GrassPatch_Originals_20260927", "Folder", 33)
	backup("MapGrouping_20260928", "Folder", 201) -- GroupMapAreas.luau undo log (ObjectValues only)
	backup("ZombiePreviousDecalHead", "Part", 7)
	backup("EggMerchantBackup", "Folder", 1)

	-- ServerStorage: old lobby versions.
	oldLobby("RogueliteLobby_PreV2", "Model", 1550)
	oldLobby("RogueliteLobby_PreV3", "Model", 1969)
	oldLobby("LobbyStations_PreV4_20260925_104024", "Folder", 44)
	oldLobby("LobbyStations_PreV4_20260925_104329", "Folder", 100)
	oldLobby("QuestBoard_BeforeGuildNotices_20260925_110739", "Folder", 4)
	oldLobby("Lobby_BeforeCohesionV6_20260925_123925", "Folder", 940)
	oldLobby("Islands_BeforeCliffsV7_20260925_203940", "Folder", 19)
	oldLobby("Islands_BeforeCliffsV8_20260925_211538", "Folder", 29)
	oldLobby("Lobby_BeforeV9_20260927_170029", "Folder", 1283)
	oldLobby("Lobby_BeforeLeaderboards_20260930_001400", "Folder", 13)

	-- ServerStorage: superseded raw imports and kits (no script or installer reads them).
	oldImport("Weapon_Import_FirstPass_Backup", "Model", 304)
	oldImport("Weapon_Import_Rigged_Backup", "Model", 350)
	oldImport("Weapon_Import_ExtraMetadata", "Model", 234)
	oldImport("ZombieRawImports", "Folder", 32)
	oldImport("HammerBoss_SourceImport", "Model", 16)
	oldImport("RegularEnemyRawImportsHistory", "Folder", 177)
	oldImport("RogueliteLobbyKit", "Folder", 18)
	oldImport("RogueliteLobby_ImportedOriginal", "Model", 18)
	oldImport("RogueliteLobby_CleanImportedOriginal", "Model", 3)
	oldImport("RogueliteLobbyKitV2", "Folder", 35)
	oldImport("RogueliteLobbyV2_ImportedOriginal", "Model", 34)
	oldImport("RogueliteLobbyLanding_ImportedOriginal", "Model", 1)
	oldImport("RogueliteLobbyKitV3", "Folder", 42)
	oldImport("RogueliteLobbyV3_ImportedOriginal", "Model", 42)
	oldImport("RogueliteLobbyV3_CapImportedOriginal", "Model", 4)
	oldImport("RogueliteStationKitV4", "Folder", 8)
	oldImport("RogueliteLobbyKitV6", "Folder", 43)
	oldImport("RogueliteIslandKitV7", "Folder", 8)
	oldImport("RogueliteIslandKitV8", "Folder", 8)

	-- ServerStorage: today's backups. A parallel map-polish session was still writing these during
	-- the scan (counts moved), so they are opt-in and need fresh counts from a dry run first.
	today("BeforeMainPineBeachRefresh_20261002", 4770)
	today("BeforeMainDesertRefresh_20261002", 1358)
	today("BeforeBiomePolish_20261002", 6681)
	today("BeforePinePlacementPolish_20261002", 2125)
	today("PineArchivedDuplicateVisuals_20261002", 14)
	today("BeforeBeachPlacementPolish_20261002", 1701)
	today("BeforeDesertPolish_20261002", 11)
	today("PineContactPass2Backup_20261002", 2)
	today("BeforeBiomeFollowup_20261002", 1718)
	today("BeforeBiomeFollowup", 175)

	-- Workspace: test models, strays near the world origin, empty or inert folders, the Baseplate.
	row("safe", "test model", "Workspace", "ZombieVariantPreviews", "Folder", 120)
	row(
		"safe",
		"test model",
		"Workspace",
		"Zombie_R15_ProvidedTextures_Studio",
		"Model",
		192,
		Vector3.new(35, 3.025, 39)
	)
	row("safe", "stray", "Workspace", "Log_Master", "Model", 2, Vector3.new(162, 0, 118))
	row("safe", "stray", "Workspace", "Log_Master", "Model", 2, Vector3.new(-11.746, 0, 25.183))
	row("safe", "stray", "Workspace", "Log_Master", "Model", 2, Vector3.new(0.988, 0, 38))
	row("safe", "stray", "Workspace", "13_Rock_Cluster", "Model", 2, Vector3.new(78.066, 0, 48.659))
	row("safe", "empty folder", "Workspace", "LukeSandboxTesting", "Folder", 0)
	row("safe", "empty folder", "Workspace", "RogueliteWeaponShowcase", "Folder", 1) -- an empty DisplayBases
	row("safe", "empty folder", "Workspace", "RogueliteWeaponShowcase_PlaySize", "Folder", 1) -- an empty DisplayBases
	row("safe", "inert folder", "Workspace", "Lighting", "Folder", 4) -- 4 post effects; inert under Workspace
	row("safe", "baseplate", "Workspace", "Baseplate", "Part", 1, Vector3.new(0, -8, 0), Vector3.new(2048, 16, 2048))
	row("risky", "not on list", "Workspace", "RogueliteEnvironmentAssets", "Folder", 3) -- master evergreen import

	-- Never touched; listed so the dry run can flag anything new in ServerStorage.
	local KEEP = {
		RogueliteNPCs = "runtime NPC templates",
		InactiveAreas = "runtime: ServerRole parks map folders here",
		InstallHammerBoss = "dev tool",
		RegularEnemyQA = "dev tool",
		EggMerchantSetup = "dev tool",
		ZombieVariantImportTools = "dev tool",
		RogueliteTests = "tests",
		Brushtool2_Plugin_Storage = "plugin storage",
		RBX_ANIMSAVES = "plugin storage (Animation Editor)",
		RegularEnemyRawImports = "current raw import (InstallRegularEnemyTemplates)",
		RegularEnemyProjectiles = "current raw import (InstallRegularEnemyTemplates)",
		MapBossRawImports = "current raw import (InstallMapBossTemplates)",
		PetRawImports = "current raw import (InstallPetTemplates)",
		GodlyWeaponImport = "current raw import (godly install_call)",
		GodlyWraithImport = "current raw import (wraith install_call)",
		BeachCoveKit = "current kit (BuildBeachCove)",
		RogueliteGrassKit = "current kit (blender-grass-kit manifest)",
		GrassPatch_Blender_Library = "current grass meshes",
		RogueliteLobbyKitV9 = "current lobby kit",
		LobbyLeaderboardsKitV1 = "current lobby kit",
	}
	-- Folders and models that must never be inside (or be) a target.
	local PROTECTED = {
		{ "Workspace", "RogueliteLobby" },
		{ "Workspace", "PineValleyArena" },
		{ "Workspace", "BeachCoveArena" },
		{ "Workspace", "BeachCoveExtras" },
		{ "Workspace", "DesertBasinArena" },
		{ "Workspace", "FrozenPassArena" },
		{ "Workspace", "VolcanicCraterArena" },
		{ "ServerStorage", "RogueliteNPCs" },
		{ "ServerStorage", "InactiveAreas" },
	}
	-- Live script lookups found 2026-10-02 that cope with the object missing (FindFirstChild or a
	-- WaitForChild timeout). Any other hit in a runtime script aborts.
	local KNOWN_HITS = {
		["ServerScriptService.RogueliteZombieChase|Zombie_R15_ProvidedTextures_Studio"] = "FindFirstChild in two raycast exclude lists (lines 165, 375); nil is skipped",
		["ServerScriptService.PracticeTarget|Zombie_R15_ProvidedTextures_Studio"] = "Studio-only; WaitForChild(...,10) returns nil and the script exits",
		["ServerScriptService.BossService|ZombieVariantPreviews"] = "FindFirstChild in a raycast exclude list (line 38); nil is skipped",
		["ServerScriptService.RogueliteCombat|RogueliteWeaponShowcase"] = "SHOWCASES list (line 106), FindFirstChild per frame; missing ones are skipped",
		["ServerScriptService.RogueliteCombat|RogueliteWeaponShowcase_PlaySize"] = "SHOWCASES list (line 106), FindFirstChild per frame; missing ones are skipped",
		["StarterPlayer.StarterPlayerScripts.CardShowcase|RogueliteWeaponShowcase"] = "FindFirstChild (line 5); its 18_Deck_of_Cards is already gone",
		["StarterPlayer.StarterPlayerScripts.CardShowcase|RogueliteWeaponShowcase_PlaySize"] = "FindFirstChild (line 5); its 18_Deck_of_Cards is already gone",
	}
	-- 'Lighting' is also the Lighting service, so only Workspace-qualified lookups count.
	local PATTERNS = {
		Lighting = {
			"[wW]orkspace%s*%.%s*Lighting",
			"[wW]orkspace%s*:%s*FindFirstChild%s*%(%s*['\"]Lighting['\"]",
			"[wW]orkspace%s*:%s*WaitForChild%s*%(%s*['\"]Lighting['\"]",
			"[wW]orkspace%s*%[%s*['\"]Lighting['\"]%s*%]",
		},
	}
	local LANTERN = {
		path = { "RogueliteLobby", "Scenery", "Lantern_Post_41" },
		class = "MeshPart",
		size = Vector3.new(1.52, 5.83, 1.52),
		now = Vector3.new(-1458.581, 122.917, -8.089),
		home = Vector3.new(-1460, 122.917, -13), -- mirror of Lantern_Post_48; its spot in older lobby backups
		lensSource = "Lantern_Post_42",
	}

	---------------------------------------------------------------------------------------------
	-- Ids, option checks, preconditions
	---------------------------------------------------------------------------------------------
	local dupCount = {}
	for _, r in MANIFEST do
		local key = r.parent .. "/" .. r.name
		dupCount[key] = (dupCount[key] or 0) + 1
	end
	local byId = {}
	for _, r in MANIFEST do
		local id = r.parent .. "/" .. r.name
		if r.pos and dupCount[id] > 1 then
			id ..= string.format("@%.0f,%.0f", r.pos.X, r.pos.Z)
		elseif dupCount[id] > 1 then
			id ..= "#" .. r.desc
		end
		assert(not byId[id], "duplicate manifest id " .. id)
		r.id = id
		byId[id] = r
	end
	local opted = {}
	for _, id in opts.alsoDelete or {} do
		local r = byId[id]
		if not r then
			return abort("alsoDelete id not in the manifest: " .. tostring(id))
		end
		opted[id] = true
	end
	if RunService:IsRunning() then
		return abort("Studio is in Play/Run; run this in Edit only")
	end

	local function countScripts(inst)
		local n = inst:IsA("LuaSourceContainer") and 1 or 0
		for _, d in inst:GetDescendants() do
			if d:IsA("LuaSourceContainer") then
				n += 1
			end
		end
		return n
	end
	local function near(a, b, tol)
		return (a - b).Magnitude <= tol
	end

	---------------------------------------------------------------------------------------------
	-- Resolve every row (all rows, so the dry run shows the risky ones too)
	---------------------------------------------------------------------------------------------
	local claimed = {}
	local problems = {}
	local selected = {}
	for _, r in MANIFEST do
		local parent = r.parent == "Workspace" and workspace or SS
		local matches = {}
		for _, c in parent:GetChildren() do
			if c.Name == r.name and c.ClassName == r.class and not claimed[c] then
				if r.pos then
					if c:IsA("PVInstance") and near(c:GetPivot().Position, r.pos, 0.05) then
						table.insert(matches, c)
					end
				else
					table.insert(matches, c)
				end
			end
		end
		if #matches > 1 then
			local exact = {}
			for _, c in matches do
				if #c:GetDescendants() == r.desc then
					table.insert(exact, c)
				end
			end
			matches = exact
		end
		local status
		if #matches == 0 then
			status = "MISSING"
		elseif #matches > 1 then
			status = "AMBIGUOUS (" .. #matches .. " matches)"
		else
			local inst = matches[1]
			local d = #inst:GetDescendants()
			if d ~= r.desc then
				status = string.format("MISMATCH descendants %d, manifest %d", d, r.desc)
			elseif r.size and not near(inst.Size, r.size, 0.01) then
				status = "MISMATCH size " .. tostring(inst.Size)
			else
				status = "OK"
				r.inst = inst
				claimed[inst] = true
			end
		end
		r.status = status
		local wanted = r.verdict == "safe" or opted[r.id]
		r.wanted = wanted
		if wanted then
			if status ~= "OK" then
				table.insert(problems, r.id .. ": " .. status)
			else
				table.insert(selected, r)
			end
		end
	end

	-- Protected roots must not be a target or sit inside one.
	for _, p in PROTECTED do
		local parent = p[1] == "Workspace" and workspace or SS
		for _, c in parent:GetChildren() do
			if c.Name == p[2] then
				for _, r in selected do
					if r.inst == c or c:IsDescendantOf(r.inst) then
						table.insert(problems, r.id .. " is or contains protected " .. p[1] .. "." .. p[2])
					end
				end
			end
		end
	end

	-- Fast membership: every target and all of its descendants.
	local inTarget = {}
	for _, r in selected do
		inTarget[r.inst] = r
		for _, d in r.inst:GetDescendants() do
			inTarget[d] = r
		end
	end

	---------------------------------------------------------------------------------------------
	-- Check 1: nothing outside the targets points into them (ObjectValue, joints, constraints,
	-- PrimaryPart, Adornee).
	---------------------------------------------------------------------------------------------
	local refHits = {}
	local function refs(d)
		local list = {}
		if d:IsA("ObjectValue") then
			table.insert(list, { "Value", d.Value })
		end
		if d:IsA("JointInstance") or d:IsA("WeldConstraint") or d:IsA("NoCollisionConstraint") then
			table.insert(list, { "Part0", d.Part0 })
			table.insert(list, { "Part1", d.Part1 })
		end
		if d:IsA("Constraint") or d:IsA("Beam") or d:IsA("Trail") then
			table.insert(list, { "Attachment0", d.Attachment0 })
			table.insert(list, { "Attachment1", d.Attachment1 })
		end
		if d:IsA("Model") then
			table.insert(list, { "PrimaryPart", d.PrimaryPart })
		end
		if
			d:IsA("Highlight")
			or d:IsA("SurfaceGui")
			or d:IsA("BillboardGui")
			or d:IsA("PVAdornment")
			or d:IsA("SelectionBox")
		then
			table.insert(list, { "Adornee", d.Adornee })
		end
		return list
	end
	local everything = {}
	for _, svc in game:GetChildren() do
		local ok, list = pcall(svc.GetDescendants, svc)
		if ok then
			for _, d in list do
				table.insert(everything, d)
			end
		end
	end
	for _, d in everything do
		if not inTarget[d] then
			local ok, list = pcall(refs, d)
			if ok then
				for _, pair in list do
					local r = pair[2] and inTarget[pair[2]]
					if r then
						table.insert(
							refHits,
							string.format("%s.%s -> %s (%s)", d:GetFullName(), pair[1], pair[2]:GetFullName(), r.id)
						)
					end
				end
			end
		end
	end
	for _, h in refHits do
		table.insert(problems, "reference into a target: " .. h)
	end

	---------------------------------------------------------------------------------------------
	-- Check 2: script sources outside the targets. Runtime scripts may only have KNOWN_HITS;
	-- scripts kept in ServerStorage (tools, tests) are reported, not blocking.
	---------------------------------------------------------------------------------------------
	local SCRIPT_SERVICES = {
		Workspace = true,
		ReplicatedStorage = true,
		ReplicatedFirst = true,
		ServerScriptService = true,
		ServerStorage = true,
		StarterGui = true,
		StarterPack = true,
		StarterPlayer = true,
		Lighting = true,
		SoundService = true,
		Teams = true,
		Chat = true,
		TextChatService = true,
		MaterialService = true,
	}
	local scripts = {}
	for _, svc in game:GetChildren() do
		if SCRIPT_SERVICES[svc.ClassName] then
			for _, d in svc:GetDescendants() do
				if d:IsA("LuaSourceContainer") and not inTarget[d] then
					table.insert(scripts, d)
				end
			end
		end
	end
	local runtimeRoots = { SS:FindFirstChild("InactiveAreas"), SS:FindFirstChild("RogueliteNPCs") }
	local function isRuntime(s)
		if not s:IsDescendantOf(SS) then
			return true
		end
		for _, root in runtimeRoots do
			if root and s:IsDescendantOf(root) then
				return true
			end
		end
		return false
	end
	local names = {}
	for _, r in selected do
		names[r.name] = true
	end
	local sourceInfo, sourceNew = {}, {}
	for _, s in scripts do
		local ok, src = pcall(function()
			return s.Source
		end)
		if ok and src ~= "" then
			for name in names do
				local pats = PATTERNS[name]
				local found = false
				if pats then
					for _, p in pats do
						if string.find(src, p) then
							found = true
							break
						end
					end
				else
					found = string.find(src, name, 1, true) ~= nil
				end
				if found then
					local lines = {}
					local n = 0
					for line in (src .. "\n"):gmatch("([^\n]*)\n") do
						n += 1
						local hit = false
						if pats then
							for _, p in pats do
								if string.find(line, p) then
									hit = true
								end
							end
						else
							hit = string.find(line, name, 1, true) ~= nil
						end
						if hit then
							table.insert(lines, n)
						end
					end
					local key = s:GetFullName() .. "|" .. name
					local where = s:GetFullName() .. ":" .. table.concat(lines, ",") .. " [" .. name .. "]"
					if not isRuntime(s) then
						table.insert(sourceInfo, "tool/test (not runtime): " .. where)
					elseif KNOWN_HITS[key] then
						table.insert(sourceInfo, "known, copes with nil: " .. where .. " - " .. KNOWN_HITS[key])
					else
						table.insert(sourceNew, where)
					end
				end
			end
		end
	end
	for _, h in sourceNew do
		table.insert(problems, "new runtime script lookup: " .. h)
	end

	---------------------------------------------------------------------------------------------
	-- Check 3: CollectionService tags on Workspace targets that runtime code names.
	---------------------------------------------------------------------------------------------
	local tags = {}
	for _, r in selected do
		if r.parent == "Workspace" then
			local list = r.inst:GetDescendants()
			table.insert(list, r.inst)
			for _, d in list do
				for _, t in d:GetTags() do
					if not t:find("^_Brushtool") and not t:find("^Assistant") then
						tags[t] = true
					end
				end
			end
		end
	end
	for _, s in scripts do
		if isRuntime(s) then
			local ok, src = pcall(function()
				return s.Source
			end)
			if ok then
				for t in tags do
					if string.find(src, t, 1, true) then
						table.insert(
							problems,
							"runtime script names tag '" .. t .. "' carried by a target: " .. s:GetFullName()
						)
					end
				end
			end
		end
	end

	---------------------------------------------------------------------------------------------
	-- Check 4: the Baseplate goes only if no map, spawn or loose part relies on it. Scans Workspace
	-- and the map folders parked in ServerStorage.InactiveAreas (ServerRole moves them into
	-- Workspace). Blocks on: a SpawnLocation over it, any part of a PROTECTED folder resting on or
	-- inside it, any unanchored part resting on or inside it. An anchored prop outside the maps
	-- only loses its floor; it is reported, not blocking.
	---------------------------------------------------------------------------------------------
	local protectedRoots = {}
	for _, p in PROTECTED do
		local parent = p[1] == "Workspace" and workspace or SS
		for _, c in parent:GetChildren() do
			if c.Name == p[2] then
				table.insert(protectedRoots, c)
			end
		end
	end
	local function inProtected(d)
		for _, root in protectedRoots do
			if d:IsDescendantOf(root) then
				return true
			end
		end
		return false
	end
	local floating = {}
	local baseRow
	for _, r in selected do
		if r.cat == "baseplate" then
			baseRow = r
		end
	end
	if baseRow then
		local bp = baseRow.inst
		if
			not near(bp.CFrame.LookVector, Vector3.new(0, 0, -1), 1e-3)
			or not near(bp.CFrame.UpVector, Vector3.new(0, 1, 0), 1e-3)
		then
			table.insert(problems, "Baseplate is rotated; the rest check assumes an axis-aligned slab")
		end
		local top = bp.Position.Y + bp.Size.Y / 2
		local bottom = bp.Position.Y - bp.Size.Y / 2
		local x0, x1 = bp.Position.X - bp.Size.X / 2, bp.Position.X + bp.Size.X / 2
		local z0, z1 = bp.Position.Z - bp.Size.Z / 2, bp.Position.Z + bp.Size.Z / 2
		local resting = {}
		local roots = { workspace }
		if SS:FindFirstChild("InactiveAreas") then
			table.insert(roots, SS.InactiveAreas)
		end
		for _, root in roots do
			for _, d in root:GetDescendants() do
				if d:IsA("BasePart") and not d:IsA("Terrain") and not inTarget[d] then
					local cf, sz = d.CFrame, d.Size
					local mn = Vector3.new(math.huge, math.huge, math.huge)
					local mx = -mn
					for _, sx in { -1, 1 } do
						for _, sy in { -1, 1 } do
							for _, sz2 in { -1, 1 } do
								local p =
									cf:PointToWorldSpace(Vector3.new(sx * sz.X / 2, sy * sz.Y / 2, sz2 * sz.Z / 2))
								mn = mn:Min(p)
								mx = mx:Max(p)
							end
						end
					end
					local overXZ = mx.X > x0 and mn.X < x1 and mx.Z > z0 and mn.Z < z1
					local onIt = mn.Y <= top + 1 and mx.Y >= bottom
					local where = d:GetFullName() .. string.format(" (bottom y=%.2f)", mn.Y)
					if overXZ and d:IsA("SpawnLocation") then
						table.insert(resting, "spawn " .. where)
					elseif overXZ and onIt then
						local root = d.AssemblyRootPart
						local anchored = d.Anchored or (root ~= nil and root.Anchored)
						if inProtected(d) then
							table.insert(resting, "map part " .. where)
						elseif not anchored then
							table.insert(resting, "unanchored " .. where)
						else
							table.insert(floating, where)
						end
					end
				end
			end
		end
		for _, p in resting do
			table.insert(problems, "rests on or inside the Baseplate: " .. p)
		end
		baseRow.note = string.format(
			"no map, spawn or loose part rests on it; anchored props left without a floor: %s; FallenPartsDestroyHeight=%s",
			#floating > 0 and table.concat(floating, ", ") or "none",
			tostring(workspace.FallenPartsDestroyHeight)
		)
	end

	---------------------------------------------------------------------------------------------
	-- Check 5: Lantern_Post_41
	---------------------------------------------------------------------------------------------
	local lantern = workspace
	for _, n in LANTERN.path do
		lantern = lantern and lantern:FindFirstChild(n)
	end
	local lanternPlan = "none"
	local lensTemplate, lensOffset
	if not lantern or lantern.ClassName ~= LANTERN.class then
		table.insert(problems, "Workspace." .. table.concat(LANTERN.path, ".") .. " missing or not a " .. LANTERN.class)
	elseif not near(lantern.Size, LANTERN.size, 0.02) then
		table.insert(problems, "Lantern_Post_41 size changed: " .. tostring(lantern.Size))
	elseif not (near(lantern.Position, LANTERN.now, 0.05) or near(lantern.Position, LANTERN.home, 0.05)) then
		table.insert(problems, "Lantern_Post_41 moved since the scan: " .. tostring(lantern.Position))
	else
		local joints = #lantern:GetJoints()
		lanternPlan = lantern.Anchored and "already anchored" or "anchor"
		if opts.restoreLantern then
			local lobby = workspace.RogueliteLobby
			local post = lobby.Scenery:FindFirstChild(LANTERN.lensSource)
			local accents = lobby:FindFirstChild("Accents")
			if post and accents then
				for _, c in accents:GetChildren() do
					if c.Name == "WarmLens" and c:IsA("BasePart") then
						local flat = Vector3.new(c.Position.X - post.Position.X, 0, c.Position.Z - post.Position.Z)
						if flat.Magnitude < 0.3 then
							lensTemplate = c
							lensOffset = c.Position - post.Position
						end
					end
				end
			end
			if not lensTemplate then
				table.insert(problems, "restoreLantern: no WarmLens above " .. LANTERN.lensSource .. " to copy")
			else
				local target = LANTERN.home + lensOffset
				for _, c in accents:GetChildren() do
					if c.Name == "WarmLens" and c:IsA("BasePart") and near(c.Position, target, 1) then
						table.insert(problems, "restoreLantern: a WarmLens already sits at " .. tostring(target))
					end
				end
				lanternPlan ..= ", move to " .. tostring(LANTERN.home) .. ", add WarmLens at " .. tostring(target)
			end
		end
		lanternPlan ..= string.format(
			" (Anchored=%s, joints=%d, at %s)",
			tostring(lantern.Anchored),
			joints,
			tostring(lantern.Position)
		)
	end

	---------------------------------------------------------------------------------------------
	-- Report
	---------------------------------------------------------------------------------------------
	local totalObjects, totalScripts = 0, 0
	local perCat = {}
	for _, r in selected do
		local objects = 1 + #r.inst:GetDescendants()
		local nScripts = countScripts(r.inst)
		totalObjects += objects
		totalScripts += nScripts
		local c = perCat[r.cat] or { rows = 0, objects = 0, scripts = 0 }
		c.rows += 1
		c.objects += objects
		c.scripts += nScripts
		perCat[r.cat] = c
	end
	say(
		(apply and "APPLY" or "DRY RUN")
			.. string.format(": %d targets, %d objects, %d scripts", #selected, totalObjects, totalScripts)
	)
	for cat, c in perCat do
		say(string.format("  %s: %d targets, %d objects, %d scripts", cat, c.rows, c.objects, c.scripts))
	end
	say("Rows:")
	for _, r in MANIFEST do
		local action = r.wanted and (r.status == "OK" and "remove" or "BLOCKED")
			or "skip (" .. r.verdict .. ", not opted in)"
		say(
			string.format(
				"  [%s] %s %s desc=%d %s -> %s%s",
				r.verdict,
				r.id,
				r.class,
				r.desc,
				r.status,
				action,
				r.note and ("; " .. r.note) or ""
			)
		)
	end
	local known = {}
	for _, r in MANIFEST do
		known[r.parent .. "/" .. r.name] = true
	end
	for _, c in SS:GetChildren() do
		if not known["ServerStorage/" .. c.Name] and not KEEP[c.Name] then
			say(
				"  unclassified, untouched: ServerStorage."
					.. c.Name
					.. " ("
					.. c.ClassName
					.. ", "
					.. #c:GetDescendants()
					.. " descendants)"
			)
		end
	end
	say("Lantern_Post_41: " .. lanternPlan)
	say("Script lookups:")
	for _, h in sourceInfo do
		say("  " .. h)
	end
	for _, h in sourceNew do
		say("  NEW (blocks): " .. h)
	end
	say(string.format("References into targets: %d", #refHits))
	if #problems > 0 then
		return abort(#problems .. " problem(s):\n  " .. table.concat(problems, "\n  "))
	end
	if not apply then
		say("Dry run only. Call with {apply=true} to make these changes.")
		return table.concat(report, "\n")
	end

	---------------------------------------------------------------------------------------------
	-- Apply: one recording, all or nothing
	---------------------------------------------------------------------------------------------
	local rid =
		History:TryBeginRecording("CleanupPlace", "Remove backups, old imports and strays; anchor Lantern_Post_41")
	if not rid then
		if not (opts.useOuterRecording and History:IsRecordingInProgress()) then
			return abort(
				"TryBeginRecording returned nil (a recording is already open, or Studio is not in Edit). Rerun with useOuterRecording=true to work inside the open recording"
			)
		end
		say("Running inside a ChangeHistory recording opened by the caller.")
	end
	local removed = {}
	local lanternWas, newLens
	local ok, err = pcall(function()
		for _, r in selected do
			local parent = r.inst.Parent
			r.inst.Parent = nil
			table.insert(removed, { r.inst, parent })
		end
		if lantern and lanternPlan ~= "none" then
			lanternWas = { anchored = lantern.Anchored, cframe = lantern.CFrame }
			lantern.Anchored = true
			if opts.restoreLantern then
				lantern.CFrame = CFrame.new(LANTERN.home) * lantern.CFrame.Rotation
				newLens = lensTemplate:Clone()
				newLens.CFrame = CFrame.new(LANTERN.home + lensOffset) * lensTemplate.CFrame.Rotation
				newLens.Parent = lensTemplate.Parent
			end
		end
		for _, r in selected do
			assert(r.inst.Parent == nil, r.id .. " still has a parent")
		end
		assert(not lantern or lantern.Anchored, "Lantern_Post_41 is not anchored")
	end)
	if not ok then
		if newLens then
			newLens.Parent = nil
		end
		if lanternWas then
			lantern.CFrame = lanternWas.cframe
			lantern.Anchored = lanternWas.anchored
		end
		for i = #removed, 1, -1 do
			removed[i][1].Parent = removed[i][2]
		end
		if rid then
			History:FinishRecording(rid, Enum.FinishRecordingOperation.Cancel)
		end
		return abort("failed while applying, everything put back: " .. tostring(err))
	end
	if rid then
		History:FinishRecording(rid, Enum.FinishRecordingOperation.Commit)
	end
	say(
		string.format(
			"Done: removed %d targets (%d objects, %d scripts). One Undo restores them until the place is saved.",
			#removed,
			totalObjects,
			totalScripts
		)
	)
	return table.concat(report, "\n")
end
