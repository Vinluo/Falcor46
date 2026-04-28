#pragma once
#include "Falcor.h"
#include "RenderGraph/RenderPass.h"

using namespace Falcor;

/**
 * Neural Irradiance Volume composite pass.
 *
 * Consumes G-buffer channels and produces an indirect-illumination + direct
 * lighting composite using a hash-grid + small MLP (CoopVec) baked from offline
 * training. See plan: niv-viewer-falcor-twinkly-globe.md.
 *
 * Step 1/2 scaffold: pass registers, reflects channels, dispatches a
 * placeholder compute shader. Real evalNIV/evalDirect comes in Step 3.
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

    ref<Scene> mpScene;
    ref<ComputePass> mpComposite;

    // Configuration (placeholder values; will be filled out in Step 3+).
    std::string mWeightsPath = "niv_weights/breakfast_room.bin";
    bool mEnableDirect = true;
    bool mEnableIndirect = true;
    float mNivScale = 1.f;
    float mExposure = 1.f;
};
