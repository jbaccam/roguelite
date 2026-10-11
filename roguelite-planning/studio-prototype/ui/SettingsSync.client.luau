-- Settings follow the player (launch audit U1). The settings window (UITheme) writes the Setting_*
-- attributes on this client; about a second after the last change this sends them to the server,
-- which saves them with the profile (ProfileAction SaveSettings) and sets them again on the next
-- server's load, before ProfileLoaded. Example: music to 0% in the lobby, PLAY, and the match
-- starts silent. Unsandboxed, so it can call ProfileAction (UITheme is sandboxed).
local Players=game:GetService('Players')
local player=Players.LocalPlayer
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local KEYS={'VisualQuality','HudScale','ScreenShake','DamageNumbers','KillBoard','MusicVolume','SfxVolume'}
local sent={} -- what the server holds, per key: the values it loaded with, then what was saved
local function snapshot() local t={};for _,k in KEYS do t[k]=player:GetAttribute('Setting_'..k) end;return t end
local queued=false
local function send()
 queued=false
 if player:GetAttribute('ProfileLoaded')~=true then return end
 local t=snapshot();local changed=false
 for _,k in KEYS do if t[k]~=nil and t[k]~=sent[k] then changed=true end end
 if not changed then return end
 local ok,r=pcall(function() return combat:WaitForChild('ProfileAction'):InvokeServer('SaveSettings',t) end)
 if ok and type(r)=='table' and r.ok then for _,k in KEYS do sent[k]=t[k] end
 else queued=true;task.delay(2,send) end -- 'Slow down' or a hiccup: try again shortly
end
local function changed() if not queued then queued=true;task.delay(1,send) end end
for _,k in KEYS do player:GetAttributeChangedSignal('Setting_'..k):Connect(changed) end
-- What the server loaded is already saved: start from it, so loading doesn't send it straight back.
local function loaded() if player:GetAttribute('ProfileLoaded')==true then sent=snapshot() end end
player:GetAttributeChangedSignal('ProfileLoaded'):Connect(loaded);loaded()
