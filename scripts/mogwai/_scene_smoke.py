# Smoke check: load the converted dining_room.pyscene and exit.
# Pure scene-load verification; no NIV pass involved.
import os
SCENE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                     "media", "niv_scenes", "dining_room", "dining_room.pyscene"))
print("[SCENE-SMOKE] loading:", SCENE)
m.loadScene(SCENE)
print("[SCENE-SMOKE] loaded OK; exiting.")
exit()
