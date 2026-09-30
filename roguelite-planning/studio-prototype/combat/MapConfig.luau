-- Per-map match data for the server roles, the wave spawner and the boss trigger.
-- Keys are RunSetupRules.Maps ids (LOBBY_AND_MATCH_SERVERS.md §1, §3).
-- folders: the Workspace folders that make up the map; ServerRole.find searches them in order.
-- roster: EnemyCatalog ids cycled by spawn slot; repeating an id weights it. nil keeps Pine
-- Valley's wave-based zombie mix. boss: 'Hammer' or a MapBossDefs id, spawned at wave 20; nil
-- means the map is won by clearing wave 20.
local M={Default='PineValley',LobbyFolders={'RogueliteLobby'}}
M.Maps={
 PineValley={folders={'PineValleyArena'},boss='Hammer'},
 -- blender-beach-cove-kit rebuilds BeachCoveArena by deleting it, so the markers and the
 -- hand-placed props live beside it in BeachCoveExtras.
 BeachCove={folders={'BeachCoveArena','BeachCoveExtras'},roster='crab,snake,crab,hermit-crab,crab,rock-throwing-crab',boss='KingCrab'},
}
function M.valid(id) return type(id)=='string' and M.Maps[id]~=nil end
function M.get(id) return M.valid(id) and M.Maps[id] or nil end
return M
