# Mogwai render-graph for the Neural Irradiance Volume viewer.
#
# Pipeline: GBufferRaster -> NeuralIrradianceVolume -> AccumulatePass -> ToneMapper -> output.
# Scene: media/niv_scenes/dining_room/dining_room.pyscene (converted by scripts/mitsuba_to_pyscene.py).
# Weights: media/niv_weights/breakfast_room.bin (exported by scripts/niv_export_weights.py).
#
# Direct lighting in the NIV pass is currently a no-op; this graph still composites
# the indirect/NIV signal into the final tonemapped output so we can verify the
# shader compiles and the inference path produces non-zero, non-NaN values.

import os

g = RenderGraph("NIVViewer")
g.create_pass("GBuffer", "GBufferRaster", {"samplePattern": "Center"})
g.create_pass("NIV",     "NeuralIrradianceVolume",
              {"weightsPath": "niv_weights/breakfast_room.bin",
               "enableIndirect": True,
               "enableDirect":   False,
               "nivScale": 1.0,
               "exposure": 1.0})
g.create_pass("Accum",   "AccumulatePass",  {"enabled": True})
g.create_pass("Tonemap", "ToneMapper",      {"autoExposure": False})

for ch in ["posW", "normW", "faceNormalW", "diffuseOpacity", "mtlData", "vbuffer"]:
    g.add_edge(f"GBuffer.{ch}", f"NIV.{ch}")
g.add_edge("NIV.color",    "Accum.input")
g.add_edge("Accum.output", "Tonemap.src")
g.mark_output("Tonemap.dst")

m.addGraph(g)

# Default scene; users can override by calling m.loadScene(...) themselves before this script.
SCENE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                     "media", "niv_scenes", "dining_room", "dining_room.pyscene"))
if os.path.exists(SCENE):
    m.loadScene(SCENE)
