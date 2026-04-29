import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# Reuse the PathTracerNRD graph but auto-load the dining-room scene.
exec(open(os.path.join(os.path.dirname(__file__), '..', 'PathTracerNRD.py')).read())

SCENE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
                                     'media', 'niv_scenes', 'dining_room', 'dining_room.pyscene'))
if os.path.exists(SCENE):
    m.loadScene(SCENE)
