import os

scene_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "media", "niv_scenes", "dining_room", "dining_room.pyscene")
)

print("[DINING-LIGHT] loading:", scene_path)
m.loadScene(scene_path)

scene = m.scene
print("[DINING-LIGHT] lights_count:", len(scene.lights))
print("[DINING-LIGHT] render_settings:", scene.renderSettings)
print("[DINING-LIGHT] envMap_is_none:", scene.envMap is None)

if scene.envMap is not None:
    print("[DINING-LIGHT] envMap_path:", scene.envMap.path)
    print("[DINING-LIGHT] envMap_rotation:", scene.envMap.rotation)
    print("[DINING-LIGHT] envMap_intensity:", scene.envMap.intensity)
    print("[DINING-LIGHT] envMap_tint:", scene.envMap.tint)

exit()
