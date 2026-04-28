# Step-2 smoke check: instantiate the NeuralIrradianceVolume pass to confirm the
# plugin loads, the FALCOR_PLUGIN_CLASS is registered, and constructor + reflect()
# don't crash. We do NOT compile the render graph here (no scene/inputs); compilation
# verification belongs to Step 6 once the full graph wiring is in place.

g = RenderGraph("NIVSmoke")
niv = g.create_pass("NIV", "NeuralIrradianceVolume", {})
print("[NIV-SMOKE] pass instantiated:", niv)
m.addGraph(g)
print("[NIV-SMOKE] graph added; exiting.")
exit()
