#include "NeuralIrradianceVolume.h"
#include "RenderGraph/RenderPassHelpers.h"
#include "Core/AssetResolver.h"

#include <fstream>
#include <vector>
#include <cstring>

extern "C" FALCOR_API_EXPORT void registerPlugin(Falcor::PluginRegistry& registry)
{
    registry.registerClass<RenderPass, NeuralIrradianceVolume>();
}

namespace
{
const char kShaderFile[] = "RenderPasses/NeuralIrradianceVolume/NeuralIrradianceVolume.cs.slang";

const ChannelList kInputChannels = {
    // clang-format off
    { "posW",            "gPosW",            "World-space position (.w = 1 if hit, 0 if miss)", true /* optional */, ResourceFormat::RGBA32Float },
    { "normW",           "gNormW",           "World-space shading normal",                       true,                ResourceFormat::RGBA32Float },
    { "faceNormalW",     "gFaceNormalW",     "World-space face normal",                          true,                ResourceFormat::RGBA32Float },
    { "diffuseOpacity",  "gDiffuseOpacity",  "Diffuse albedo + opacity",                         true,                ResourceFormat::RGBA32Float },
    { "mtlData",         "gMtlData",         "Material data (header + lobes)",                   true,                ResourceFormat::RGBA32Uint  },
    { "vbuffer",         "gVBuffer",         "Visibility buffer (packed)",                       true                                                  },
    // clang-format on
};

const ChannelList kOutputChannels = {
    // clang-format off
    { "color",           "gOutputColor",     "Composite (direct + indirect)",                    false, ResourceFormat::RGBA32Float },
    // clang-format on
};

const char kWeightsPath[]    = "weightsPath";
const char kEnableDirect[]   = "enableDirect";
const char kEnableIndirect[] = "enableIndirect";
const char kNivScale[]       = "nivScale";
const char kExposure[]       = "exposure";

// Mirrored from scripts/niv_export_weights.py — keep in sync if header is bumped.
struct NivBinHeader
{
    uint32_t magic;          // 'NIVW' = 0x5747494E
    uint32_t version;        // 1
    uint32_t numLevels;
    uint32_t hashTableSize;
    uint32_t featureDim;
    uint32_t mlpLayers;
    uint32_t mlpHidden;
    uint32_t inputDim;
    uint32_t outputDim;
    uint32_t weightLayout;   // 0 = RowMajor (currently the only value the exporter writes)
    float    aabbMin[3];
    float    aabbMax[3];
    uint32_t weightBytes;
    uint32_t biasBytes;
    uint32_t reserved[14];
};
static_assert(sizeof(NivBinHeader) == 128, "NIV binary header must be 128 bytes");

constexpr uint32_t kNivMagic = 0x5747494Eu; // 'NIVW' little-endian
} // namespace

NeuralIrradianceVolume::NeuralIrradianceVolume(ref<Device> pDevice, const Properties& props) : RenderPass(pDevice)
{
    parseProperties(props);
    buildPass();
}

void NeuralIrradianceVolume::buildPass()
{
    // Currently the shader does NOT import Scene.Scene, so it can be compiled
    // without scene defines. When direct lighting is added we'll need to gate
    // this on `mpScene != nullptr` and pass `mpScene->getSceneDefines()`.
    mpComposite = ComputePass::create(mpDevice, kShaderFile, "main", DefineList());
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

void NeuralIrradianceVolume::loadWeights(const std::filesystem::path& path)
{
    mWeightsLoaded = false;
    mpResolutionsBuf = nullptr;
    mpHashTablesBuf = nullptr;
    mpMlpOffsetsBuf = nullptr;
    mpMlpWeightsBuf = nullptr;
    mpMlpBiasesBuf = nullptr;

    auto resolved = AssetResolver::getDefaultResolver().resolvePath(path);
    if (resolved.empty())
    {
        logWarning("NeuralIrradianceVolume: weight binary '{}' not found in asset search paths; pass will output black.", path.string());
        return;
    }

    std::ifstream f(resolved, std::ios::binary);
    if (!f.good())
    {
        logWarning("NeuralIrradianceVolume: failed to open weight binary '{}'.", resolved.string());
        return;
    }

    NivBinHeader hdr{};
    f.read(reinterpret_cast<char*>(&hdr), sizeof(hdr));
    if (!f.good() || hdr.magic != kNivMagic || hdr.version != 1)
    {
        logWarning("NeuralIrradianceVolume: bad header in '{}' (magic={:#x}, version={}).",
                   resolved.string(), hdr.magic, hdr.version);
        return;
    }

    // Minimal compatibility check against shader-side static constants.
    if (hdr.numLevels != 8 || hdr.hashTableSize != 131072 || hdr.featureDim != 4 ||
        hdr.mlpLayers != 4 || hdr.mlpHidden != 64 || hdr.inputDim != 35 || hdr.outputDim != 3)
    {
        logWarning("NeuralIrradianceVolume: '{}' has dims that do not match the shader's hardcoded constants "
                   "(numLevels={}, hashTableSize={}, featureDim={}, mlpLayers={}, mlpHidden={}, inputDim={}, outputDim={}).",
                   resolved.string(), hdr.numLevels, hdr.hashTableSize, hdr.featureDim,
                   hdr.mlpLayers, hdr.mlpHidden, hdr.inputDim, hdr.outputDim);
        return;
    }

    // Resolutions (numLevels int32).
    std::vector<int32_t> resolutions(hdr.numLevels);
    f.read(reinterpret_cast<char*>(resolutions.data()), resolutions.size() * sizeof(int32_t));

    // Hash tables: numLevels * hashTableSize entries, each entry is featureDim fp16, packed two
    // fp16 per uint32. Size in uints = numLevels * hashTableSize * (featureDim / 2).
    const uint32_t hashU32Count = hdr.numLevels * hdr.hashTableSize * (hdr.featureDim / 2);
    std::vector<uint32_t> hashTables(hashU32Count);
    f.read(reinterpret_cast<char*>(hashTables.data()), hashTables.size() * sizeof(uint32_t));

    // MLP offsets: 4 weight + 4 bias, each uint32.
    std::vector<uint32_t> mlpOffsets(2 * hdr.mlpLayers);
    f.read(reinterpret_cast<char*>(mlpOffsets.data()), mlpOffsets.size() * sizeof(uint32_t));

    // Weight blob and bias blob.
    std::vector<uint8_t> weightBlob(hdr.weightBytes);
    f.read(reinterpret_cast<char*>(weightBlob.data()), weightBlob.size());
    std::vector<uint8_t> biasBlob(hdr.biasBytes);
    f.read(reinterpret_cast<char*>(biasBlob.data()), biasBlob.size());

    if (!f.good())
    {
        logWarning("NeuralIrradianceVolume: short read on '{}'.", resolved.string());
        return;
    }

    mNumLevels      = hdr.numLevels;
    mHashTableSize  = hdr.hashTableSize;
    mFeatureDim     = hdr.featureDim;
    mMlpLayers      = hdr.mlpLayers;
    mMlpHidden      = hdr.mlpHidden;
    mInputDim       = hdr.inputDim;
    mOutputDim      = hdr.outputDim;
    mAabbMin        = float3(hdr.aabbMin[0], hdr.aabbMin[1], hdr.aabbMin[2]);
    mAabbMax        = float3(hdr.aabbMax[0], hdr.aabbMax[1], hdr.aabbMax[2]);

    const auto srvFlags = ResourceBindFlags::ShaderResource;

    mpResolutionsBuf = mpDevice->createStructuredBuffer(
        sizeof(int32_t), (uint32_t)resolutions.size(), srvFlags, MemoryType::DeviceLocal, resolutions.data());
    mpHashTablesBuf = mpDevice->createStructuredBuffer(
        sizeof(uint32_t), (uint32_t)hashTables.size(), srvFlags, MemoryType::DeviceLocal, hashTables.data());
    mpMlpOffsetsBuf = mpDevice->createStructuredBuffer(
        sizeof(uint32_t), (uint32_t)mlpOffsets.size(), srvFlags, MemoryType::DeviceLocal, mlpOffsets.data());
    mpMlpWeightsBuf = mpDevice->createBuffer(
        weightBlob.size(), srvFlags, MemoryType::DeviceLocal, weightBlob.data());
    mpMlpBiasesBuf = mpDevice->createBuffer(
        biasBlob.size(), srvFlags, MemoryType::DeviceLocal, biasBlob.data());

    mWeightsLoaded = true;
    logInfo("NeuralIrradianceVolume: loaded '{}' "
            "(levels={}, hashTableSize={}, featureDim={}, mlp={}x{}, in={}, out={}, "
            "weight={} B, bias={} B, AABB=[{},{},{}]..[{},{},{}])",
            resolved.string(), mNumLevels, mHashTableSize, mFeatureDim,
            mMlpLayers, mMlpHidden, mInputDim, mOutputDim,
            hdr.weightBytes, hdr.biasBytes,
            mAabbMin.x, mAabbMin.y, mAabbMin.z, mAabbMax.x, mAabbMax.y, mAabbMax.z);
}

void NeuralIrradianceVolume::execute(RenderContext* pRenderContext, const RenderData& renderData)
{
    auto pOutput = renderData.getTexture("color");
    if (!pOutput)
        return;

    const uint2 dim = uint2(pOutput->getWidth(), pOutput->getHeight());

    if (!mpComposite)
        buildPass();

    // If the weight binary failed to load (e.g. fresh checkout, asset not yet exported), clear and return.
    if (!mWeightsLoaded)
    {
        pRenderContext->clearTexture(pOutput.get());
        return;
    }

    auto var = mpComposite->getRootVar();
    var["NIV_CB"]["gResolution"]      = dim;
    var["NIV_CB"]["gEnableDirect"]    = mEnableDirect ? 1u : 0u;
    var["NIV_CB"]["gEnableIndirect"]  = mEnableIndirect ? 1u : 0u;
    var["NIV_CB"]["gNivScale"]        = mNivScale;
    var["NIV_CB"]["gExposure"]        = mExposure;
    var["NIV_CB"]["gAabbMin"]         = mAabbMin;
    var["NIV_CB"]["gAabbMax"]         = mAabbMax;

    // G-buffer inputs (texture binds; tolerate missing optional channels).
    var["gPosW"]            = renderData.getTexture("posW");
    var["gNormW"]           = renderData.getTexture("normW");
    var["gDiffuseOpacity"]  = renderData.getTexture("diffuseOpacity");

    var["gResolutions"]     = mpResolutionsBuf;
    var["gHashTables"]      = mpHashTablesBuf;
    var["gMlpOffsets"]      = mpMlpOffsetsBuf;
    var["gMlpWeights"]      = mpMlpWeightsBuf;
    var["gMlpBiases"]       = mpMlpBiasesBuf;

    var["gOutputColor"]     = pOutput;

    mpComposite->execute(pRenderContext, dim.x, dim.y, 1);
}

void NeuralIrradianceVolume::renderUI(Gui::Widgets& widget)
{
    widget.text(mWeightsLoaded ? "Weights loaded." : "No weights loaded - output is black.");
    widget.textbox("Weights path", mWeightsPath);
    if (widget.button("Reload weights"))
        loadWeights(mWeightsPath);
    widget.checkbox("Enable direct (currently no-op)", mEnableDirect);
    widget.checkbox("Enable indirect (NIV)", mEnableIndirect);
    widget.var("NIV scale", mNivScale, 0.f, 16.f, 0.01f);
    widget.var("Exposure", mExposure, 0.f, 16.f, 0.01f);
}

void NeuralIrradianceVolume::setScene(RenderContext* pRenderContext, const ref<Scene>& pScene)
{
    mpScene = pScene;
    // Load (or reload) the weight binary on scene change.
    loadWeights(mWeightsPath);
}
