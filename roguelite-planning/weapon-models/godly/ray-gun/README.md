# Ray Gun (Godly, ranged)

Status: **Blender-verified, Studio untested.**

Ability (RARITY_GODLY_ARMOR.md section 9): zappy green blasts. Enemies it kills disintegrate in a
burst that hits the ones nearby.

## Design

It follows the owner's direction to use the Call of Duty Zombies ray gun look (see `reference/`),
rebuilt in our chunky stylised low-poly style. There are no logos and no text, and it is not a 1:1
copy.

- **Body:** deep crimson painted metal with worn, chipped edges and gold lightning-bolt inlays. The
  bolt shape is our own design.
- **Focal piece:** a big round dial housing at the rear. It has:
  - a cream gauge face with red and yellow arc bands;
  - a glowing green "charged" arc;
  - tick marks and a sculpted needle;
  - a gold bezel and hub;
  - raised teeth on the rim.
- **Back of the housing:** two pointed spikes, a lower spike and a loop handle.
- **Energy chamber:** a glowing green glass chamber with pale-hot crackles and three leaning
  dark-steel coil rings.
- **Side details:** vent modules with steel rails over glowing green vent lines, a knurled knob and a
  toggle.
- **Barrel and muzzle:**
  - a gunmetal barrel with gold rings, and an antenna mast with a gold loop;
  - a swept crimson fin with a bolt inlay;
  - a flared crimson muzzle cone with gold bands and studs, a glowing mouth and an emitter bead.
- **Grip:** a big ribbed black grip in a crimson frame, with a sweeping trigger guard.

## Numbers

- **Triangles:** 15,712 in total.
  - `RayGun`: 15,004
  - `RayGun_Glow`: 352
  - `RayGun_GlowCore`: 356
- **Size:** about 3.4 x 1.9 x 0.6 studs (Studio X, Y, Z) at hero size. The suggested play scale is
  0.65–0.7.

## Studio setup

- **Texture:** one 1024 `BaseColor.png` with baked painterly lighting. Apply it with
  `MeshPart.TextureID`.
- **Glow meshes:** both use Neon.
  - `RayGun_Glow`, colour (16,255,40).
  - `RayGun_GlowCore`, colour (140,255,110).
- **Barrel direction:** Blender -x, which is Studio +X.
- **Attachment points:** `studio-install-data.json` gives the grip point, the muzzle attachment and
  `vfx_notes`. The notes cover the blast projectile, the muzzle flash, the disintegrate burst on kill
  with its hit-radius shell, and the idle chamber light.

## Files

- `build_ray_gun.py`: the generator.
- `Model.blend`, `Model.fbx`, `Model.glb`
- `validation.json`: results of re-importing the GLB and FBX.
- Renders: `Preview`, `Front`, `Back`, `Side`, `Hero`, `Scale`, `Compare_Catalog`, `Sheet`.

## Rebuild

```
blender -b --factory-startup --threads 2 --python build_ray_gun.py
```
