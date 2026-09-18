-- Use the persisted native geometry; OBJ importer faces +Z, rig faces -Z.
local AS = game:GetService("AssetService")
local mesh = AS:CreateMeshPartAsync(Content.fromUri("rbxassetid://78893098815517"))
for _, model in {workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio"), game.ServerStorage.RogueliteNPCs:FindFirstChild("Zombie_NPC")} do
    if model then
        local head = model.Head
        local size, cf, texture = head.Size, head.CFrame, head.TextureID
        head:ApplyMesh(mesh)
        head.Size, head.CFrame, head.TextureID = size, cf, texture
        head.RenderFidelity = Enum.RenderFidelity.Precise
        model.Humanoid.AutomaticScalingEnabled = false
        head:SetAttribute("PublishedNativeHeadMesh", "rbxassetid://78893098815517")
        if not head:GetAttribute("NativeImportAttachmentFixed") then
            local turn = CFrame.Angles(0, math.pi, 0)
            for _, attachment in head:GetChildren() do
                if attachment:IsA("Attachment") then
                    attachment.CFrame = turn * attachment.CFrame
                    local original = attachment:FindFirstChild("OriginalPosition")
                    if original then original.Value = attachment.Position end
                end
            end
            head:SetAttribute("NativeImportAttachmentFixed", true)
        end
        if not head:GetAttribute("NativeImportFacingFixed") then
            local turn = CFrame.Angles(0, math.pi, 0)
            head.Neck.C1 = turn * head.Neck.C1
            head.CFrame = head.CFrame * turn
            head:SetAttribute("NativeImportFacingFixed", true)
        end
        head.Neck.C1 = head.NeckRigAttachment.CFrame
    end
end
mesh:Destroy()
return "Persistent heads installed and facing forward"
