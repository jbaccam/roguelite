-- Temporary, unshipped tests. run() only uses detached fixtures; live() creates/destroys one
-- local cosmetic scene using the current player's real avatar and the real lobby assets.
local Tests = {}
local Tags = game:GetService("CollectionService")

local function onlyEngineAttributes(instance)
	for name in instance:GetAttributes() do
		if not name:match("^RBX") then
			return false
		end
	end
	return true
end

local function countAppearance(model)
	local result = {}
	for _, child in model:GetDescendants() do
		if
			child:IsA("Accessory")
			or child:IsA("Shirt")
			or child:IsA("Pants")
			or child:IsA("BodyColors")
			or child:IsA("CharacterMesh")
			or child:IsA("WrapLayer")
			or child:IsA("Decal")
		then
			local key = child.ClassName .. ":" .. child.Name
			result[key] = (result[key] or 0) + 1
		end
	end
	return result
end

function Tests.run(Scene)
	local n = 0
	local function check(ok, why)
		assert(ok, why)
		n += 1
	end
	local fixture = Instance.new("Folder")
	local function make(class, name, parent)
		local x = Instance.new(class)
		x.Name = name or class
		x.Parent = parent or fixture
		return x
	end
	local ok, err = xpcall(function()
		local lobby = make("Model", "Lobby")
		local character = make("Model", "Character")
		make("Part", "HumanoidRootPart", character)
		make("Humanoid", "Humanoid", character)
		local player = { Character = character }
		local found, why = Scene.sources(lobby, player)
		check(found == nil and type(why) == "string", "Missing real island returns a clean error")
		local island = make("Model", "ChestIsland", lobby)
		local ground = make("Folder", "Ground", island)
		make("MeshPart", "Island_South_4_Top", ground)
		make("MeshPart", "Island_South_4_Cliff", ground)
		check(Scene.sources(lobby, player) == nil, "Missing real dummy has no generic fallback")
		local scenery = make("Folder", "Scenery", lobby)
		local dummy = make("MeshPart", "Practice_Dummy_85", scenery)
		dummy:SetAttribute("Asset", "Practice_Dummy")
		found = Scene.sources(lobby, player)
		check(
			found and found.dummy == dummy and found.avatar == character,
			"Edit source resolves exact dummy and avatar"
		)
		local wrapper = make("Model", "Practice_Dummy_85", scenery)
		dummy.Name = "ReviewedMesh"
		dummy.Parent = wrapper
		found = Scene.sources(lobby, player)
		check(found and found.dummy == dummy, "Runtime wrapper resolves authored mesh instead of invisible hitbox")
		check(Scene.sources(lobby, { Character = nil }) == nil, "Missing real avatar has no substitute figure")

		local actor = make("Model", "ScrubFixture")
		local root = make("Part", "HumanoidRootPart", actor)
		root.CFrame = CFrame.new(2, 9, -4)
		actor.PrimaryPart = root
		local foot = make("Part", "LeftFoot", actor)
		foot.CFrame = root.CFrame * CFrame.new(-1, -2.5, 0)
		local shirt = make("Shirt", "Shirt", actor)
		shirt.ShirtTemplate = "rbxassetid://1"
		local pants = make("Pants", "Pants", actor)
		pants.PantsTemplate = "rbxassetid://2"
		local accessory = make("Accessory", "Hat", actor)
		local handle = make("Part", "Handle", accessory)
		local decal = make("Decal", "face", foot)
		decal.Texture = "rbxassetid://3"
		make("BodyColors", "BodyColors", actor)
		local humanoid = make("Humanoid", "Humanoid", actor)
		local weld = make("Weld", "AccessoryWeld", handle)
		weld.Part0 = root
		weld.Part1 = handle
		local external = make("Part", "ExternalLivePart")
		external.CFrame = CFrame.new(500, 20, 30)
		local externalWeld = make("Weld", "ExternalLink", root)
		externalWeld.Part0 = root
		externalWeld.Part1 = external
		local attached = make("WeldConstraint", "PhysicsLink", root)
		attached.Part0 = root
		attached.Part1 = foot
		local removals = {}
		for _, class in
			{
				"Script",
				"LocalScript",
				"ModuleScript",
				"RemoteEvent",
				"RemoteFunction",
				"UnreliableRemoteEvent",
				"BindableEvent",
				"BindableFunction",
				"ProximityPrompt",
				"ClickDetector",
				"Tool",
				"ForceField",
				"Sound",
				"BillboardGui",
				"SurfaceGui",
				"BodyVelocity",
			}
		do
			table.insert(removals, make(class, class, root))
		end
		local weapon = make("Model", "Weapon_23", actor)
		make("Part", "Blade", weapon)
		local effect = make("ParticleEmitter", "GameplayEffect", root)
		for _, child in actor:GetDescendants() do
			child:SetAttribute("PracticeTarget", true)
			Tags:AddTag(child, "RogueliteZombie")
		end
		Tags:AddTag(actor, "LobbyPracticeDummy")
		actor:SetAttribute("PracticeHits", 400)
		Scene.scrub(actor, true)
		check(
			humanoid.Parent == actor and not humanoid.EvaluateStateMachine and not humanoid.AutoRotate,
			"Only inert avatar Humanoid survives"
		)
		check(shirt.Parent == actor and shirt.ShirtTemplate == "rbxassetid://1", "Shirt appearance survives")
		check(pants.Parent == actor and pants.PantsTemplate == "rbxassetid://2", "Pants appearance survives")
		check(
			accessory.Parent == actor and handle.Parent == accessory and weld.Parent == handle,
			"Internal accessory weld survives"
		)
		check(decal.Parent == foot and decal.Texture == "rbxassetid://3", "Actual face texture survives")
		check(
			externalWeld.Parent == nil and external.CFrame == CFrame.new(500, 20, 30),
			"External joint removed without moving source geometry"
		)
		check(
			attached.Parent == nil and not effect.Enabled and weapon.Parent == nil,
			"Physics, weapon attachments and live particles removed"
		)
		for _, child in removals do
			check(child.Parent == nil, "No interaction or gameplay instance: " .. child.ClassName)
		end
		for _, child in actor:GetDescendants() do
			check(
				#Tags:GetTags(child) == 0 and onlyEngineAttributes(child),
				"Descendant tags and gameplay attributes removed"
			)
			if child:IsA("BasePart") then
				check(
					child.Anchored and not child.CanCollide and not child.CanQuery and not child.CanTouch,
					"Cosmetic anchored geometry"
				)
			end
		end
		check(#Tags:GetTags(actor) == 0 and onlyEngineAttributes(actor), "Root tags and attributes removed")
		local nonAvatar = make("Model", "DummyFixture")
		local h = make("Humanoid", "Humanoid", nonAvatar)
		Scene.scrub(nonAvatar, false)
		check(h.Parent == nil, "Dummy cannot become a gameplay Humanoid")

		local relative = root.CFrame:ToObjectSpace(foot.CFrame)
		local scene = {
			groundAt = function(_, x, z)
				if x == 999 then
					return nil
				end
				return Vector3.new(1200 + x, 600 + z * 0.02, -9000 + z)
			end,
		}
		local item = { model = actor, root = root, footOffset = 3, scene = scene }
		for _, p in { { 0, 12 }, { -18, -28 }, { 18, 28 }, { -10, 8 }, { 10, -27 } } do
			check(Scene.place(item, p[1], p[2], Vector3.zAxis), "Valid lane placement")
			check(
				(root.Position - (scene:groundAt(p[1], p[2]) + Vector3.yAxis * 3.015)).Magnitude < 0.001,
				"Actual foot offset sits above grass"
			)
			check(
				(root.CFrame:ToObjectSpace(foot.CFrame).Position - relative.Position).Magnitude < 0.001,
				"Anchored limb offsets move with root"
			)
			check(
				item.rest == root.CFrame and actor:GetPivot() == item.rest,
				"Rest is primary root pivot, not bounding-box center"
			)
			check(root.CFrame.LookVector:Dot(Vector3.zAxis) > 0.999, "Explicit facing preserved")
		end
		local before = root.CFrame
		check(not Scene.place(item, 999, 0) and root.CFrame == before, "Off-island move cannot relocate actor")
		check(not pcall(Scene.place, item, 0 / 0, 0), "Nonfinite placement is rejected")
		Scene.repositionRoot(item, item.rest + Vector3.xAxis)
		check(
			(root.Position - item.rest.Position - Vector3.xAxis).Magnitude < 0.001,
			"Transient recoil does not overwrite rest"
		)
		Scene.setVisible(item, false)
		check(root.LocalTransparencyModifier == 1 and handle.LocalTransparencyModifier == 1, "Unused actor hidden")
		Scene.setVisible(item, true)
		check(
			root.LocalTransparencyModifier == 0 and handle.LocalTransparencyModifier == 0,
			"Actor visibility restored"
		)
	end, debug.traceback)
	fixture:Destroy()
	assert(ok, err)
	return { passed = n, detachedFixturesOnly = true }
end

function Tests.live(Scene, player, parent)
	assert(game:GetService("RunService"):IsClient(), "Live scene validation must run in the Studio client")
	player = player or game:GetService("Players").LocalPlayer
	local source, why = Scene.sources(nil, player)
	assert(source, why)
	local originalIslandPivot, originalDummyFrame = source.island:GetPivot(), source.dummy.CFrame
	local originalIslandCount, originalArchive = #source.island:GetDescendants(), source.avatar.Archivable
	local appearance = countAppearance(source.avatar)
	local scene, reason = Scene.new(parent or workspace.CurrentCamera, Vector3.new(2400, 700, -17000), player)
	assert(scene, reason)
	local n = 0
	local function check(ok, message)
		assert(ok, message)
		n += 1
	end
	local ok, err = xpcall(function()
		-- Engine avatar joint upgrading occurs when the copy enters Workspace. Verify the
		-- post-parent scrub survives real frames rather than inspecting only a detached clone.
		for _ = 1, 3 do
			game:GetService("RunService").Heartbeat:Wait()
			for _, child in scene.presenter.model:GetDescendants() do
				check(
					not child:IsA("Constraint") and not child:IsA("WeldConstraint"),
					"Engine avatar constraints stay removed after parenting"
				)
				if child:IsA("BasePart") then
					check(
						child.Anchored and not child.CanCollide and not child.CanQuery and not child.CanTouch,
						"Engine avatar initialization cannot restore body collisions on later frames"
					)
				end
			end
		end
		check(
			scene.islandScale == 1 and scene.island:GetScale() == source.island:GetScale(),
			"Reviewed island keeps native scale"
		)
		check(
			not scene.island:FindFirstChild("Chests") and not scene.island:FindFirstChild("Pedestals"),
			"Chest and reward stations removed only from copy"
		)
		check(
			scene.ground.MeshId == source.top.MeshId and scene.ground.TextureID == source.top.TextureID,
			"Actual lobby ground artwork"
		)
		check(#scene.dummies == 7, "Bounded reusable pool of seven real dummies")
		check(scene:createDummy("Extra", 0, 0) == nil, "No eighth dummy allocation")
		local copiedAppearance = countAppearance(scene.presenter.model)
		for key, count in appearance do
			check(copiedAppearance[key] == count, "Avatar appearance preserved: " .. key)
		end
		check(
			scene.presenter.model:FindFirstChildOfClass("Humanoid") ~= nil,
			"Avatar Humanoid retained for layered clothing"
		)
		for i, actor in scene.dummies do
			check(
				actor.target:IsA("MeshPart")
					and actor.target.MeshId == source.dummy.MeshId
					and actor.target.TextureID == source.dummy.TextureID,
				"Exact reviewed dummy artwork " .. i
			)
			check(
				actor.target.Size == source.dummy.Size and math.abs(actor.footOffset - source.dummy.Size.Y / 2) < 0.001,
				"Natural dummy size and ground offset " .. i
			)
			check(
				actor.root.CFrame == actor.rest and actor.model:GetPivot() == actor.rest,
				"Stage pivot contract " .. i
			)
			check(
				actor.highlight and actor.highlight.FillTransparency == 1 and actor.highlight.OutlineTransparency == 1,
				"Hit tint ready without changing authored texture " .. i
			)
			check(actor.visible == (i <= 3), "Only three initial targets visible " .. i)
			local surface =
				scene:groundAt(actor.root.Position.X - scene.origin.X, actor.root.Position.Z - scene.origin.Z)
			check(
				surface and math.abs(actor.root.Position.Y - actor.footOffset - 0.015 - surface.Y) < 0.005,
				"Dummy feet on actual grass " .. i
			)
		end
		for _, child in scene.folder:GetDescendants() do
			check(#Tags:GetTags(child) == 0 and onlyEngineAttributes(child), "Scene cannot inherit gameplay state")
			check(
				not child:IsA("LuaSourceContainer")
					and not child:IsA("RemoteEvent")
					and not child:IsA("RemoteFunction")
					and not child:IsA("ProximityPrompt")
					and not child:IsA("ClickDetector")
					and not child:IsA("Constraint")
					and not child:IsA("WeldConstraint"),
				"Scene contains no interactions or constraints"
			)
			if child:IsA("BasePart") then
				check(
					child.Anchored
						and not child.CanCollide
						and not child.CanTouch
						and (not child.CanQuery or child == scene.ground),
					"Only actual grass has cosmetic ray queries"
				)
			end
			if child:IsA("Humanoid") then
				check(
					child:IsDescendantOf(scene.presenter.model) and not child.EvaluateStateMachine,
					"No enemy Humanoid"
				)
			end
		end
		check(source.avatar.Archivable == originalArchive, "Original avatar cloning flag restored")
		check(
			source.island:GetPivot() == originalIslandPivot and #source.island:GetDescendants() == originalIslandCount,
			"Actual lobby island untouched"
		)
		check(
			source.dummy.CFrame == originalDummyFrame and source.dummy:GetAttribute("Asset") == "Practice_Dummy",
			"Actual lobby dummy untouched"
		)
	end, debug.traceback)
	scene:destroy()
	scene:destroy()
	assert(scene.folder.Parent == nil, "Scene cleaned on success or failure")
	assert(ok, err)
	return { passed = n, actualLobbyAssets = true, actualPlayerAvatar = true, cleaned = true }
end

return Tests
