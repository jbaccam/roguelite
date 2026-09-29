-- Run once in Studio (Edit, command bar or MCP) to save ReplicatedStorage.RogueliteSoundCue.
-- UI modules are sandboxed, and a sandboxed thread may only fire an event that is sandboxed too,
-- so the cue copies UITheme's Sandboxed/Capabilities. StarterPlayerScripts.RogueliteSounds
-- (unsandboxed) listens to it and plays the named sound; UITheme's T.sound(name) fires it.
local RS=game:GetService('ReplicatedStorage')
local theme=RS:WaitForChild('UITheme')
local cue=RS:FindFirstChild('RogueliteSoundCue')
if cue and not cue:IsA('BindableEvent') then cue:Destroy();cue=nil end
cue=cue or Instance.new('BindableEvent')
cue.Name='RogueliteSoundCue'
cue.Sandboxed=true
cue.Capabilities=theme.Capabilities
cue.Parent=RS
print('RogueliteSoundCue ready: Sandboxed='..tostring(cue.Sandboxed)..' Capabilities='..tostring(cue.Capabilities))
