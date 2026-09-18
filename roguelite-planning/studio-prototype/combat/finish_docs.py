from pathlib import Path
p=Path('roguelite-planning/FLOATING_WEAPON_PRESENTATION.md')
b=p.read_bytes()
try:s=b.decode('utf-8')
except UnicodeDecodeError:s=b.decode('cp1252')
p.write_text(s,encoding='utf-8')
p=Path('roguelite-planning/MASTER_GAME_DESIGN.md');s=p.read_text(encoding='utf-8')
s=s.replace('0.32 — visible floating auto-attacking weapons','0.33 — fixed weapon slots and katana combat prototype')
s=s.replace('Default floating formation is not constant orbiting; dedicated orbitals may circle.','Weapons occupy specific assigned floating slots; they do not spin 360 degrees around the avatar. Earlier orbital concepts require review against this rule.')
s=s.replace('Start with waist-to-chest-height placement and tune readability in Studio.','Start with waist-to-chest-height placement and tune readability in Studio. Weapon geometry must stay outside the avatar during idle and every attack phase. Rear/side weapons must take a clear outward route or wait for a reachable target, never slash through the player to reach a front enemy. Confirmed hits show actual damage numbers above the enemy.')
s+='\n### Katana combat prototype — 2026-09-17\n\nThe first combat weapon is the user-resized katana, in a fixed right-side slot. Automatic slashes damage zombies on the server and display floating damage numbers. Studio-only Zombies [Z] and Katana [K] toggles independently control the wave and weapon. Initial test values: 25 damage, 1.05-second cadence, 100-health zombies, three-second replacement after a kill. Details: [Combat prototype](studio-prototype/combat/README.md).\n'
p.write_text(s,encoding='utf-8')
p=Path('roguelite-planning/CURRENT_GAME_STRUCTURE.md');s=p.read_text(encoding='utf-8').replace('They do not all continuously orbit; dedicated orbital weapons may circle.','Each weapon occupies a specific floating slot; the formation does not rotate 360 degrees around the avatar. Attacks must preserve avatar clearance and show damage numbers for confirmed enemy hits.');p.write_text(s,encoding='utf-8')
