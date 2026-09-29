-- Picks this server's role and parks unused areas as soon as the server starts (ServerRole).
local Role=require(script.Parent:WaitForChild('ServerRole'))
if game:GetService('RunService'):IsStudio() and Role.get()~='Combined' then
 warn(('Studio is running as a %s server (Workspace.StudioServerRole). Clear that attribute for the normal combined preview.'):format(Role.get()))
end
