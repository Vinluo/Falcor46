# External Assets

This directory holds **large scene / texture assets** that are treated as
out-of-band dependencies, similar to the packages under `external/packman/`.

The contents (everything except this `README.md`) are git-ignored — see the
`/external/assets/*` rule in the repository root `.gitignore`.

## Layout

```
external/assets/
  README.md                           (tracked — this file)
  Bistro/                             (ignored — Amazon Lumberyard Bistro)
    Bistro_v5_2.zip                   (original archive, ~853 MB — kept for re-extract)
    .extracted                        (marker, prevents re-extract on re-run)
    Bistro_v5_2/                      (unpacked, ~1.7 GB)
      BistroExterior.fbx              (120 MB)
      BistroExterior.pyscene          (official, ships with the archive)
      BistroInterior.fbx              (42 MB)
      BistroInterior_Wine.fbx         (49 MB, with filled wine glasses)
      BistroInterior_Wine.pyscene
      san_giuseppe_bridge_4k.hdr      (24 MB HDRI for the exterior)
      Textures/                       (DDS, BaseColor/Specular/Normal/Emissive)
      README.txt  LICENSE.txt  CHANGELOG.txt
```

## Fetching assets

### Bistro (Amazon Lumberyard, CC-BY 4.0, ~853 MB zip → ~1.7 GB unpacked)

```bat
tools\fetch_bistro.bat
```

This downloads `Bistro_v5_2.zip` from NVIDIA's ORCA CDN into
`external/assets/Bistro/` and unpacks it. Safe to re-run — it skips the
download if the zip is present and skips extraction once `.extracted` exists.

If the CDN feels slow (DNS / routing can steer the request at a distant
Akamai edge), set a proxy before running — `curl` honors `HTTPS_PROXY`
natively, no code change needed:

```bat
set HTTPS_PROXY=http://127.0.0.1:7897
tools\fetch_bistro.bat
```

Alternatively, download manually from
<https://developer.nvidia.com/orca/amazon-lumberyard-bistro> and extract the
archive into `external/assets/Bistro/` so the final `Bistro_v5_2/` folder
ends up at `external/assets/Bistro/Bistro_v5_2/`.

## Wiring assets into Mogwai

Either put the directory on Falcor's media search path so the bundled
`.pyscene` files can resolve `BistroExterior.fbx` and
`san_giuseppe_bridge_4k.hdr` by relative name:

```bat
setx FALCOR_MEDIA_FOLDERS "%CD%\external\assets\Bistro\Bistro_v5_2"
```

…or load a `.pyscene` by absolute path directly in Mogwai (`Ctrl+Shift+O`).
The archive ships with official `BistroExterior.pyscene` and
`BistroInterior_Wine.pyscene` scene files — use those as the starting point.
See `wiki/07_Build_Bistro_ReSTIR.md` for full usage and ReSTIR setup.
