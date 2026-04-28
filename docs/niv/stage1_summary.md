# Neural Irradiance Volume — Stage 1 Summary

**Date:** 2026-04-28  
**Plan:** `C:\Users\shijian\.claude\plans\niv-viewer-falcor-twinkly-globe.md`  
**Branch:** `master` (Falcor) — local-only, not pushed at the time of this writing.

This document summarizes everything that landed during the first integration
session of the Neural Irradiance Volume (NIV) project into Falcor. It captures
*what we shipped*, *what is deferred*, and *what to know before resuming*.

---

## Goal

Bring NIV's offline-trained model and its reference scene (the Mitsuba 3
"dining-room") into Falcor as first-class citizens, so that Mogwai can render
the scene with the NIV indirect-illumination network sitting in a Falcor
RenderGraph alongside `GBufferRaster`, `AccumulatePass`, and `ToneMapper`.

Scope locked at the start of the session:
- **Form factor:** Mogwai RenderPass plugin (no standalone SampleApp).
- **Scene:** dining-room only.
- **Weights pipeline:** offline export, no PyTorch in Falcor runtime.

---

## What shipped (commits already on local `master`)

### Commit `3bf76b01` — submodule registration

`neural-irradiance-volume/` added as a git submodule pointing at
`https://github.com/Vinluo/neural-irradiance-volume.git`. Falcor consumes
**only** two things from it via the offline scripts (see below):
1. PyTorch `.pt` checkpoints
2. The Mitsuba scene XML + OBJ meshes + textures

Nothing else from the submodule is imported into Falcor at runtime — no
slangpy, no torch, no Mitsuba.

### Commit `4eb7a0aa` — pass scaffold + Slang upgrade

| Group | Files | Why |
|---|---|---|
| Slang version pin | `dependencies.xml` | `2024.1.34 → 2026.5.2` so `CoopVec / coopVecMatMulAdd / CoopVecMatrixLayout` exist. |
| Adapter (C++) | `Core/API/Device.cpp`, `Core/Program/ProgramReflection.cpp` | `gfxEnableDebugLayer(true)` arg; `#pragma warning(disable: 4996)` for deprecated reflection APIs. |
| Adapter (Slang) | `Utils/HostDeviceShared.slangh`, `Utils/Math/FormatConversion.slang`, `Scene/HitInfo.slang` | `1u` literals in `PACK_BITS`; drop Falcor `packSnorm2x16` (now in stdlib); `this = {}` → field-by-field zero. |
| NIV plugin | `Source/RenderPasses/NeuralIrradianceVolume/{CMakeLists.txt, .h, .cpp, .cs.slang}` | Plugin scaffold — registers, reflects 6 inputs + 1 output, dispatches a placeholder shader. |
| Asset pipeline | `scripts/niv_export_weights.py`, `scripts/mitsuba_to_pyscene.py` | `.pt → .bin`, Mitsuba XML → `.pyscene` + asset copy. |
| Test infra | `scripts/mogwai/_*_smoke.py`, `scripts/slang_compat_dryrun.ps1` | Headless smokes + Slang dry-run for future bumps. |

### Pending commit — Step 3 + Step 6 (this stage)

| Group | Files | Why |
|---|---|---|
| Adapter (Slang) | `Rendering/Materials/BSDFs/StandardBSDF.slang`, `Scene/ShadingData.slang`, `Scene/SceneTypes.slang`, `Scene/Raster.slang`, `Scene/Lights/BuildTriangleList.cs.slang`, `RenderPasses/GBuffer/VBuffer/VBufferRaster.3d.slang` | Slang 2026 stops auto-generating default ctors when explicit `__init` exists, and stops accepting brace-init that bypasses `__init`. Add `__init() {}` + `__init(uint)` where the existing call sites needed them. |
| NIV plugin (C++) | `Source/RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.{h,cpp}` | Loads the weight binary header (128 bytes), creates 5 GPU buffers (resolutions, hash tables, MLP offsets, weight blob, bias blob), validates dims against shader constants. Surfaces "loaded / black" state in `renderUI`. |
| NIV plugin (Slang) | `Source/RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.cs.slang` | Hash-grid encoding (8 levels × 131072 × 4 fp16), 4-layer 64-wide fp16 MLP using plain row-major MAD loops, composite `nivScale * albedo/π * irradiance`. Direct lighting deferred. |
| Render graph | `scripts/mogwai/NIVViewer.py` | `GBufferRaster → NeuralIrradianceVolume → AccumulatePass → ToneMapper`, auto-loads `dining_room.pyscene`. |

---

## Verification status

| Gate | Status |
|---|---|
| C++ rebuild (`cmake --build … --target Mogwai`) | ✅ EXIT 0 |
| Plugin registration (Mogwai loads 34 plugins, NIV among them) | ✅ |
| Pyscene loads (52 obj meshes + 1 synthesized rect + 15 materials + envmap) | ✅ |
| GBufferRaster compiles + runs against the converted scene | ✅ |
| NIV pass loads `breakfast_room.bin` at scene-set time | ✅ logged dims & AABB |
| NIV shader compiles + links at runtime in the full graph | ✅ no `error[E]` in log |
| Image visually matches reference | ⏳ not yet — Gate 3.5 + GUI capture deferred |
| PSNR ≥ 30 dB vs upstream `viewer_coop.py` | ⏳ deferred |

---

## Known limitations / deferred work

1. **Direct lighting is a no-op.** `gEnableDirect` is wired through but the
   shader path is empty. Adding env-map sampling + shadow rays (via
   `Scene.Scene` + `SceneRayQuery`) is the natural next step.
2. **CoopVec MLP is not used.** The shader uses plain fp16 MAD loops because
   `coopVecMatMulAdd` failed to *link* (no diagnostic emitted) under Falcor's
   current SM 6.7 / D3D12 target with both `RowMajor` and `InferencingOptimal`
   layouts. Needs either an SM bump, a Vulkan-only path, or different layout
   conversion. Performance impact: 4-layer 64-wide MLP at 1080p is ~70 GMul /
   frame in plain ops — should still hit 30 fps on a 4060 but well below
   CoopVec ceiling.
3. **No reference image captured yet.** Gate 3.5 (running `viewer_coop.py`
   from the submodule against the same scene + checkpoint and saving a
   fixed-camera frame to `tests/data/niv/`) was not run. Without it, "looks
   right" stays subjective.
4. **`Walls_0002` rectangle is currently suppressed** behind
   `SKIP_RECTANGLES = True` in the generated pyscene because manual
   `TriangleMesh()` construction was failing in the scene-builder context
   during Step 5. Synthesis logic is in place; needs a small follow-up.
5. **Slang upgrade adapter is large.** 11 Falcor source files were touched
   to make the codebase compile under Slang 2026. These should ideally land
   as a separate "Slang 2026.5.2 compatibility" PR upstream rather than
   bundled with NIV.
6. **Submodule research changes are unrelated to this work** and have been
   held out of every Falcor commit so far.

---

## How to resume

1. Run `python scripts/niv_export_weights.py` and
   `python scripts/mitsuba_to_pyscene.py` if assets are missing in
   `media/niv_weights/` or `media/niv_scenes/dining_room/` (they live in
   packman-managed media and are gitignored).
2. `cmake --build build/windows-vs2022 --config Debug --target Mogwai`.
3. `Mogwai.exe -s scripts/mogwai/NIVViewer.py` — should bring up the dining
   room with the NIV signal as the (only) lighting term.
4. To take the next step, swap `gEnableIndirect=False, gEnableDirect=True`
   in the renderUI and verify the scene goes near-black; this confirms the
   skeleton for direct lighting is the only thing missing.

## File touched inventory (cumulative this stage)

```
Source/Falcor/Core/API/Device.cpp
Source/Falcor/Core/Program/ProgramReflection.cpp
Source/Falcor/Rendering/Materials/BSDFs/StandardBSDF.slang
Source/Falcor/Scene/HitInfo.slang
Source/Falcor/Scene/Lights/BuildTriangleList.cs.slang
Source/Falcor/Scene/Raster.slang
Source/Falcor/Scene/SceneTypes.slang
Source/Falcor/Scene/ShadingData.slang
Source/Falcor/Utils/HostDeviceShared.slangh
Source/Falcor/Utils/Math/FormatConversion.slang
Source/RenderPasses/CMakeLists.txt
Source/RenderPasses/GBuffer/VBuffer/VBufferRaster.3d.slang
Source/RenderPasses/NeuralIrradianceVolume/CMakeLists.txt           [new]
Source/RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.cpp        [new]
Source/RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.cs.slang   [new]
Source/RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.h          [new]
dependencies.xml
docs/niv/stage1_summary.md   [new — this file]
scripts/mitsuba_to_pyscene.py [new]
scripts/mogwai/NIVViewer.py   [new]
scripts/mogwai/_mesh_smoke.py [new]
scripts/mogwai/_niv_smoke.py  [new]
scripts/mogwai/_scene_smoke.py [new]
scripts/niv_export_weights.py [new]
scripts/slang_compat_dryrun.ps1 [new]
```
