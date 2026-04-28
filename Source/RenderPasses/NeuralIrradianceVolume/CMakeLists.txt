add_plugin(NeuralIrradianceVolume)

target_sources(NeuralIrradianceVolume PRIVATE
    NeuralIrradianceVolume.cpp
    NeuralIrradianceVolume.h
    NeuralIrradianceVolume.cs.slang
)

target_copy_shaders(NeuralIrradianceVolume RenderPasses/NeuralIrradianceVolume)

target_source_group(NeuralIrradianceVolume "RenderPasses")
