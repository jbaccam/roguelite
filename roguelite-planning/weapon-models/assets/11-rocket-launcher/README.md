# Empty Rocket Launcher

The primary Model.blend/FBX/GLB contain the launcher only. Its front is a genuine open annular rim with a modeled inner wall and a dark closed backstop 2.94 units behind the muzzle. Preview and Alternate show the empty launcher.

The separate full rocket is in components/Rocket. Both mesh origins share the warhead rear shoulder / insertion socket, +X forward in Blender. Set rocket exported root transform to the launcher mesh transform to reproduce the loaded alignment. Full coordinate details and actual bore ray/standalone export checks are in rig_validation.json and validation.json.

Rebuild using batches/guns/separate_rocket.py with Blender --background --threads 4. Single packed base-color atlas per asset. No animation or Studio integration was added.
