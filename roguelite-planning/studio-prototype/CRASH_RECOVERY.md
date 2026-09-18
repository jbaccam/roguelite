# Zombie crash recovery

Restored to roguelite place 107877054949326 on September 17, 2026 after the reopened place contained no zombie instances or scripts.

Used the saved reconstruction sequence in README.md: CreateNativeZombie, InstallPreferredZombie, InstallPersistentHead; restored both runtime scripts verbatim. Recreated the missing transparent RogueliteZombieSpawn at (56, 4.95, 450). Preserved existing map and player SpawnLocation.

Fresh Play verification: five live zombies, health 100, speed 13.5, Chasing=true; all reached the player's vicinity. Player speed 18. Client sees published head mesh 78893098815517 and forward shoulder transforms on all five. Static display remains anchored. Returned to Edit and confirmed display, template, persistent head and both enabled scripts remain.

This verifies restoration in the current Studio edit session, not a disk/cloud place save. Save the place from Studio to retain it across restarts. The reconstruction files and uploaded head/texture asset IDs are retained locally for recovery.
