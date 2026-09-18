from pathlib import Path
files=['roguelite-planning/MASTER_GAME_DESIGN.md','roguelite-planning/FLOATING_WEAPON_PRESENTATION.md','roguelite-planning/studio-prototype/combat/README.md']
for filename in files:
 p=Path(filename);s=p.read_text(encoding='utf-8')
 s=s.replace('It rapidly flips/aims toward enemies in any direction and may briefly reposition around the outside of the avatar for a clear slash, then returns home.','It rapidly turns and slashes directly toward the enemy from its assigned grip slot. It must not travel around the avatar or switch sides before attacking.')
 s=s.replace('It quickly turns/flips toward the target and takes a short outside repositioning arc when necessary, rather than limiting attacks to one side.','It quickly turns/flips toward the target directly from the assigned grip slot. Do not move it around the avatar or to the opposite side before swinging.')
 s=s.replace('The right slot is its idle/home position. The katana targets enemies on every side, takes a fast outside arc to an attack position, aims and slashes, then returns home. This brief targeted attack repositioning is not continuous orbiting.','The right slot is the grip anchor during attacks as well as idle. The katana turns and slashes directly at its target from that slot. It does not traverse the body perimeter or switch sides to prepare an attack. Only the minimum outward clearance correction is allowed.')
 s=s.replace('The weapon takes an outward path and returns to its slot.','The weapon aims from its slot, with a minimal outward correction if needed for avatar clearance.')
 s+='\nLatest correction: a rear target is attacked directly from the right-side slot; no front-of-avatar detour and no move to the left side. This supersedes the earlier attack-repositioning arc.\n'
 p.write_text(s,encoding='utf-8')
