# EASU for Ren'Py

A single-file texture magnification filter for Ren'Py, adapted from AMD FidelityFX Super Resolution 1's Edge-Adaptive Spatial Upsampling (EASU) algorithm.

Copy [`easu.rpy`](easu.rpy) into your game's `game/` directory and restart the game. The script replaces Ren'Py's `renpy.texture` shader part, applying EASU to eligible magnified textures without requiring per-image transforms.

> This is an unofficial shader override targeting Ren'Py 8.5.3. It uses a reserved shader part and may need changes for other engine versions. Compatibility and performance should be checked in your own game.

## Features

- Single-pass, edge-adaptive filtering for magnified textures.
- Derivative-based scale detection, including rotated meshes, with native filtering retained for minification and near-1:1 rendering.
- Conservative native-filtering fallback around transparent or partially transparent samples.
- Neighborhood color clamping to limit overshoot.
- A magenta diagnostic mode for checking whether the magnification path is reached.

This implements the EASU stage only. It does not include RCAS sharpening, temporal reconstruction, or a complete FSR rendering pipeline.

## Installation

1. Download [`easu.rpy`](easu.rpy).
2. Remove or disable any SGSR implementation or other script that overrides `renpy.texture`. Remove the corresponding orphaned `.rpyc` files as well.
3. Copy `easu.rpy` into your project's `game/` directory:

   ```text
   your-project/
   └── game/
       ├── easu.rpy
       ├── script.rpy
       └── ...
   ```

4. Fully quit and restart the game.

No layer transform or `gui.init` change is required. The filter runs automatically when a texture using `renpy.texture` meets the magnification and opacity checks.

## Configuration

Edit the flags near the start of `easu.rpy`, then fully restart the game:

```python
init 999 python:
    EASU_ENABLED = True
    EASU_DEBUG_MAGNIFICATION = False
```

| Setting | Default | Behavior |
| --- | --- | --- |
| `EASU_ENABLED` | `True` | Registers the EASU replacement for `renpy.texture`. Set to `False` to skip registration. |
| `EASU_DEBUG_MAGNIFICATION` | `False` | Tints eligible magnification paths magenta when enabled. |

These are initialization flags, not runtime toggles. The magenta diagnostic happens before the opacity checks, so it can appear in areas that would otherwise fall back to native filtering.

## Scope and limitations

- **Engine integration:** The script overrides a reserved Ren'Py shader part. Another override can conflict with it or replace it, depending on initialization order.
- **Rendering scope:** UI and intermediate textures using `renpy.texture` can also be affected. Coverage of movies, transitions, and Live2D is not guaranteed.
- **Transparency:** If the native sample or any of the 12 EASU neighborhood samples has alpha below `0.9999`, the shader returns the native result. Transparent sprite edges may therefore look unchanged.
- **Texture atlases:** Reads are clamped to the whole texture, not individual atlas subrectangles. Adjacent atlas images can bleed into the filter. Use dedicated textures or sufficient gutters where possible.
- **Graphics support:** The shader requires fragment derivatives (`dFdx` and `dFdy`), including on GLSL ES paths. Check support on your target renderer and devices.
- **Performance:** EASU adds neighborhood texture reads and shader arithmetic. This repository does not include benchmarks or a cross-platform compatibility test suite.
- **Image quality:** Results depend on source art, scale, and texture sampling. Evaluate representative backgrounds, sprites, and UI at the resolutions your game supports.

## Troubleshooting

### I do not see a difference

Confirm the file is in `game/`, fully restart the game, and check that no other script overrides `renpy.texture`. Test an opaque image displayed larger than its source resolution. Near-1:1 rendering, minification, and transparent neighborhoods deliberately use native filtering.

Temporarily enable `EASU_DEBUG_MAGNIFICATION` to identify magnification paths, then disable it for normal use.

### I see colored seams or neighboring images

Check whether the affected image shares a texture atlas. The filter cannot determine atlas subrect bounds; use a dedicated texture or increase padding between atlas entries.

### The game fails to compile the shader

Check your Ren'Py version, renderer, derivative support, and conflicting shader overrides. Include those details and the shader error when reporting an issue.

### How do I uninstall it?

Remove `easu.rpy` and its generated `easu.rpyc` from `game/`, then fully restart the game. Alternatively, set `EASU_ENABLED = False` and restart.

## Implementation and attribution

The filter ports `FsrEasuSetF`, `FsrEasuTapF`, and `FsrEasuF` from AMD's [`ffx_fsr1.h`](https://github.com/GPUOpen-Effects/FidelityFX-FSR/blob/master/ffx-fsr/ffx_fsr1.h).

The Ren'Py adaptation uses explicit texel-center reads, reciprocal and inverse-square-root operations instead of the upstream approximations, UV-based positioning, derivative-based magnification detection, and a conservative alpha fallback. UV coordinates provide the input/output mapping, so a separate `FsrEasuCon` setup is not used.

This is an independent adaptation and is not an official AMD or Ren'Py project.

## License

Distributed under the [MIT License](LICENSE). The AMD copyright and permission notice are preserved in both `easu.rpy` and `LICENSE`.
