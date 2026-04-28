#include "NeuralIrradianceVolume.h"
#include "RenderGraph/RenderPassHelpers.h"

extern "C" FALCOR_API_EXPORT void registerPlugin(Falcor::PluginRegistry& registry)
{
    registry.registerClass<RenderPass, NeuralIrradianceVolume>();
}

namespace
{
const char kShaderFile[] = "RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.cs.slang";

const ChannelList kInputChannels = {
    // clang-format off
    { "posW",            "gPosW",            "World-space position",                       true /* optional */, ResourceFormat::RGBA32Float },
    { "normW",           "gNormW",           "World-space shading normal",                 true,                ResourceFormat::RGBA32Float },
    { "faceNormalW",     "gFaceNormalW",     "World-space face normal",                    true,                ResourceFormat::RGBA32Float },
    { "diffuseOpacity",  "gDiffuseOpacity",  "Diffuse albedo + opacity",                   true,                ResourceFormat::RGBA32Float },
    { "mtlData",         "gMtlData",         "Material data (header + lobes)",             true,                ResourceFormat::RGBA32Uint  },
    { "vbuffer",         "gVBuffer",         "Visibility buffer (packed)",                 true                                                  },
    // clang-format on
};

const ChannelList kOutputChannels = {
    // clang-format off
    { "color",           "gOutputColor",     "Composite (direct + indirect)",              false, ResourceFormat::RGBA32Float },
    // clang-format on
};

const char kWeightsPath[]    = "weightsPath";
const char kEnableDirect[]   = "enableDirect";
const char kEnableIndirect[] = "enableIndirect";
const char kNivScale[]       = "nivScale";
const char kExposure[]       = "exposure";
} // namespace

NeuralIrradianceVolume::NeuralIrradianceVolume(ref<Device> pDevice, const Properties& props) : RenderPass(pDevice)
{
    parseProperties(props);

    // Placeholder compute pass: a single .cs.slang that fills the output with a debug color.
    // Real evaluation pipeline (hash-grid encoding + CoopVec MLP + direct light) lands in Step 3.
    mpComposite = ComputePass::create(mpDevice, kShaderFile, "main");
}

void NeuralIrradianceVolume::parseProperties(const Properties& props)
{
    for (const auto& [key, value] : props)
    {
        if (key == kWeightsPath)
            mWeightsPath = value.operator std::string();
        else if (key == kEnableDirect)
            mEnableDirect = value;
        else if (key == kEnableIndirect)
            mEnableIndirect = value;
        else if (key == kNivScale)
            mNivScale = value;
        else if (key == kExposure)
            mExposure = value;
        else
            logWarning("Unknown property '{}' in NeuralIrradianceVolume properties.", key);
    }
}

Properties NeuralIrradianceVolume::getProperties() const
{
    Properties props;
    props[kWeightsPath]    = mWeightsPath;
    props[kEnableDirect]   = mEnableDirect;
    props[kEnableIndirect] = mEnableIndirect;
    props[kNivScale]       = mNivScale;
    props[kExposure]       = mExposure;
    return props;
}

RenderPassReflection NeuralIrradianceVolume::reflect(const CompileData& compileData)
{
    RenderPassReflection reflector;
    addRenderPassInputs(reflector, kInputChannels);
    addRenderPassOutputs(reflector, kOutputChannels);
    return reflector;
}

void NeuralIrradianceVolume::execute(RenderContext* pRenderContext, const RenderData& renderData)
{
    auto pOutput = renderData.getTexture("color");
    if (!pOutput)
        return;

    const uint2 dim = uint2(pOutput->getWidth(), pOutput->getHeight());

    auto var = mpComposite->getRootVar();
    var["CB"]["gResolution"]      = dim;
    var["CB"]["gEnableDirect"]    = mEnableDirect ? 1u : 0u;
    var["CB"]["gEnableIndirect"]  = mEnableIndirect ? 1u : 0u;
    var["CB"]["gNivScale"]        = mNivScale;
    var["CB"]["gExposure"]        = mExposure;
    var["gOutputColor"]           = pOutput;

    mpComposite->execute(pRenderContext, dim.x, dim.y, 1);
}

void NeuralIrradianceVolume::renderUI(Gui::Widgets& widget)
{
    widget.text("Step 1/2 scaffold (placeholder shader).");
    widget.textbox("Weights path", mWeightsPath);
    widget.checkbox("Enable direct", mEnableDirect);
    widget.checkbox("Enable indirect (NIV)", mEnableIndirect);
    widget.var("NIV scale", mNivScale, 0.f, 16.f, 0.01f);
    widget.var("Exposure", mExposure, 0.f, 16.f, 0.01f);
}

void NeuralIrradianceVolume::setScene(RenderContext* pRenderContext, const ref<Scene>& pScene)
{
    mpScene = pScene;
    // Step 3 will (re)compile the program here against scene defines and load the weight binary.
}
