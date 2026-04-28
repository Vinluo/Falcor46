#pragma once
#include "Falcor.h"
#include "RenderGraph/RenderPass.h"

using namespace Falcor;

/**
 * Neural Irradiance Volume composite pass.
 *
 * Consumes G-buffer channels and produces an indirect-illumination + direct
 * lighting composite using a hash-grid + small MLP (CoopVec) baked from offline
 * training. See plan: niv-viewer-falcor-twinkly-globe.md and the binary format
 * documented at the top of scripts/niv_export_weights.py.
 */
class NeuralIrradianceVolume : public RenderPass
{
public:
    FALCOR_PLUGIN_CLASS(NeuralIrradianceVolume, "NeuralIrradianceVolume", "Neural irradiance volume composite + direct lighting.");

    static ref<NeuralIrradianceVolume> create(ref<Device> pDevice, const Properties& props)
    {
        return make_ref<NeuralIrradianceVolume>(pDevice, props);
    }

    NeuralIrradianceVolume(ref<Device> pDevice, const Properties& props);

    virtual Properties getProperties() const override;
    virtual RenderPassReflection reflect(const CompileData& compileData) override;
    virtual void execute(RenderContext* pRenderContext, const RenderData& renderData) override;
    virtual void renderUI(Gui::Widgets& widget) override;
    virtual void setScene(RenderContext* pRenderContext, const ref<Scene>& pScene) override;

private:
    void parseProperties(const Properties& props);
    void loadWeights(const std::filesystem::path& path);
    void buildPass();

    ref<Scene> mpScene;
    ref<ComputePass> mpComposite;

    // Configuration.
    std::string mWeightsPath = "niv_weights/breakfast_room.bin";
    bool        mEnableDirect    = true;
    bool        mEnableIndirect  = true;
    float       mNivScale        = 1.f;
    float       mExposure        = 1.f;

    // Loaded weight binary fields (see scripts/niv_export_weights.py header layout).
    bool        mWeightsLoaded   = false;
    uint32_t    mNumLevels       = 0;
    uint32_t    mHashTableSize   = 0;
    uint32_t    mFeatureDim      = 0;
    uint32_t    mMlpLayers       = 0;
    uint32_t    mMlpHidden       = 0;
    uint32_t    mInputDim        = 0;
    uint32_t    mOutputDim       = 0;
    float3      mAabbMin         = float3(0);
    float3      mAabbMax         = float3(0);

    ref<Buffer> mpResolutionsBuf;   ///< StructuredBuffer<int>, length numLevels.
    ref<Buffer> mpHashTablesBuf;    ///< StructuredBuffer<uint>, packed fp16 pairs.
    ref<Buffer> mpMlpOffsetsBuf;    ///< StructuredBuffer<uint>, length 2*mlpLayers.
    ref<Buffer> mpMlpWeightsBuf;    ///< Raw byte buffer, ByteAddressBuffer-readable.
    ref<Buffer> mpMlpBiasesBuf;     ///< Raw byte buffer, ByteAddressBuffer-readable.
};
