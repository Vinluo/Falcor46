# Mogwai render-graph for the Neural Irradiance Volume viewer.
#
# Pipeline:
#   GBufferRaster ─┬─▶ RTXDIPass.color ──────────┐
#                  └─▶ NeuralIrradianceVolume.color (indirect only)
#                                                 │
#       ModulateIllumination(emission=direct,     ▼
#                            residualRadiance=indirect) ─▶ AccumulatePass ─▶ ToneMapper
#
# NIV pass is indirect-only (nivScale * albedo/π * irradianceMLP). RTXDIPass
# (ReSTIR DI) provides the direct illumination. ModulateIllumination is reused
# as a generic add: emission + residualRadiance == direct + indirect.

import os

g = RenderGraph("NIVViewer")
g.create_pass("GBuffer", "GBufferRaster",          {"samplePattern": "Center",
                                                    # All dining-room materials are doubleSided, but Falcor's Scene::rasterize
                                                    # ignores per-mesh doubleSided when applying the global cull mode. Force
                                                    # cull=None so back-facing triangles aren't dropped at the rasterizer.
                                                    "forceCullMode": True,
                                                    "cull":          "None"})
g.create_pass("RTXDI",   "RTXDIPass",              {})
g.create_pass("NIV",     "NeuralIrradianceVolume", {"weightsPath": "niv_weights/breakfast_room.bin",
                                                    "nivScale":     1.0})
g.create_pass("Add",     "ModulateIllumination",   {})
g.create_pass("Accum",   "AccumulatePass",         {"enabled": True})
g.create_pass("Tonemap", "ToneMapper",             {"autoExposure": False})

# RTXDI consumes vbuffer (+ optional motion vectors for temporal reuse).
g.add_edge("GBuffer.vbuffer", "RTXDI.vbuffer")
g.add_edge("GBuffer.mvec",    "RTXDI.mvec")

# NIV consumes G-buffer geometry/material channels.
for ch in ["posW", "normW", "faceNormalW", "diffuseOpacity", "mtlData", "vbuffer"]:
    g.add_edge(f"GBuffer.{ch}", f"NIV.{ch}")

# Composite direct + indirect via ModulateIllumination's pure-add slots.
g.add_edge("RTXDI.color", "Add.emission")
g.add_edge("NIV.color",   "Add.residualRadiance")

g.add_edge("Add.output",   "Accum.input")
g.add_edge("Accum.output", "Tonemap.src")
g.mark_output("Tonemap.dst")

m.addGraph(g)

# Default scene; users can override by calling m.loadScene(...) themselves before this script.
SCENE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                     "media", "niv_scenes", "dining_room", "dining_room.pyscene"))
if os.path.exists(SCENE):
    m.loadScene(SCENE)
