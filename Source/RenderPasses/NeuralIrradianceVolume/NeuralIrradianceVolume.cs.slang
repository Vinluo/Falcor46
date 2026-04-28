// Step 1/2 placeholder compute shader.
// Writes a debug color to the output to validate that:
//   * the pass plugin registers,
//   * RenderPassReflection wires the output channel,
//   * the ComputePass dispatches and binds correctly.
// Real evalNIV (hash-grid + CoopVec MLP) and evalDirect land in Step 3.

cbuffer CB
{
    uint2 gResolution;
    uint  gEnableDirect;
    uint  gEnableIndirect;
    float gNivScale;
    float gExposure;
};

RWTexture2D<float4> gOutputColor;

[shader("compute")]
[numthreads(16, 16, 1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    if (any(tid.xy >= gResolution))
        return;

    // Diagonal magenta/teal gradient so we can see the pass is alive.
    float2 uv = float2(tid.xy) / float2(gResolution);
    float3 color = lerp(float3(0.1, 0.6, 0.6), float3(0.6, 0.1, 0.6), saturate((uv.x + uv.y) * 0.5));
    color *= gExposure;
    gOutputColor[tid.xy] = float4(color, 1.0);
}
