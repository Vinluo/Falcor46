// NeuralIrradianceVolume composite pass.
//
// Consumes Falcor GBufferRaster outputs (posW, normW, diffuseOpacity) and
// produces an NIV-evaluated indirect-illumination color. Indirect light is
// computed as `(albedo / pi) * irradiance(pos, normal)` where the irradiance
// network is a hash-grid encoder (Mueller et al. multi-resolution hash) feeding
// a 4-layer 64-wide MLP.
//
// First-pass implementation uses plain row-major fp16 MADs rather than Slang's
// cooperative-vector intrinsics. CoopVec is the long-term optimization: in this
// integration the intrinsics linked silently (no diagnostic), so we ship the
// portable variant first and revisit CoopVec with the right SM / Vulkan profile
// once a baseline image is verified.
//
// Direct lighting and emissive contribution are deferred to a follow-up step
// (will reintroduce `import Scene.Scene` + SceneRayQuery). The toggle is wired
// through to keep the UI live.

cbuffer NIV_CB
{
    uint2  gResolution;
    uint   gEnableDirect;
    uint   gEnableIndirect;
    float  gNivScale;
    float  gExposure;
    float  _pad0;
    float  _pad1;
    float3 gAabbMin;
    float  _pad2;
    float3 gAabbMax;
    float  _pad3;
};

// G-buffer inputs from GBufferRaster.
Texture2D<float4> gPosW;
Texture2D<float4> gNormW;
Texture2D<float4> gDiffuseOpacity;

// NIV weight buffers loaded from media/niv_weights/<scene>.bin.
StructuredBuffer<int>  gResolutions;        ///< Per-level grid resolution (numLevels ints).
StructuredBuffer<uint> gMlpOffsets;         ///< 4 weight + 4 bias byte offsets, packed.
StructuredBuffer<uint> gHashTables;         ///< Two fp16 features packed per uint, length numLevels*hashTableSize*featureDim/2.
ByteAddressBuffer      gMlpWeights;         ///< Row-major fp16 MLP weight blob, layer-aligned.
ByteAddressBuffer      gMlpBiases;          ///< Row-major fp16 MLP bias blob, layer-aligned.

RWTexture2D<float4> gOutputColor;

// ---- Network constants (must match scripts/niv_export_weights.py header) ----
static const uint HASH_TABLE_SIZE = 131072;
static const uint NUM_LEVELS      = 8;
static const uint FEATURE_DIM     = 4;
static const uint POS_ENC_DIM     = NUM_LEVELS * FEATURE_DIM;  // 32
static const uint MLP_INPUT       = POS_ENC_DIM + 3;           // 35
static const uint MLP_W           = 64;
static const uint MLP_OUT         = 3;

// Mix-hash matching the upstream encoder (Mueller et al.).
uint hashCoords(int3 c)
{
    uint r = uint(c.x);
    r ^= uint(c.y) * 2654435761u;
    r ^= uint(c.z) * 805459861u;
    return r & (HASH_TABLE_SIZE - 1);
}

// Read an fp16 element from a ByteAddressBuffer (offset in bytes, must be 2-aligned).
float loadHalf(ByteAddressBuffer buf, uint byteOffset)
{
    // Load the 32-bit dword that contains our 16-bit element.
    uint word = buf.Load(byteOffset & ~3u);
    uint shift = (byteOffset & 2u) * 8u;     // 0 if low half, 16 if high half
    return f16tof32((word >> shift) & 0xFFFFu);
}

// ----- Hash-grid encoding into a 35-element fp16 input vector ---------------

void encodeInput(float3 hit_pos, float3 hit_normal, out float input_vec[MLP_INPUT])
{
    [unroll]
    for (uint k = 0; k < MLP_INPUT; ++k) input_vec[k] = 0.0f;

    float3 pn = clamp((hit_pos - gAabbMin) / (gAabbMax - gAabbMin), 0.0f, 1.0f - 1e-6f);

    [unroll]
    for (uint level = 0; level < NUM_LEVELS; level++)
    {
        int    resolution = gResolutions[level];
        float3 scaled = pn * float(resolution);
        int3   fc = int3(floor(scaled));
        float3 fr = scaled - float3(fc);

        float4 feat = float4(0);
        for (uint corner = 0; corner < 8; corner++)
        {
            int3 off = int3(corner & 1, (corner >> 1) & 1, (corner >> 2) & 1);
            uint hi = hashCoords(fc + off);
            uint packed0 = gHashTables[(level * HASH_TABLE_SIZE + hi) * 2 + 0];
            uint packed1 = gHashTables[(level * HASH_TABLE_SIZE + hi) * 2 + 1];
            float4 cf = float4(
                f16tof32(packed0),
                f16tof32(packed0 >> 16),
                f16tof32(packed1),
                f16tof32(packed1 >> 16));
            float w = ((off.x == 1) ? fr.x : (1.0f - fr.x))
                    * ((off.y == 1) ? fr.y : (1.0f - fr.y))
                    * ((off.z == 1) ? fr.z : (1.0f - fr.z));
            feat += w * cf;
        }
        uint b = level * FEATURE_DIM;
        input_vec[b + 0] = feat.x;
        input_vec[b + 1] = feat.y;
        input_vec[b + 2] = feat.z;
        input_vec[b + 3] = feat.w;
    }

    input_vec[POS_ENC_DIM + 0] = hit_normal.x;
    input_vec[POS_ENC_DIM + 1] = hit_normal.y;
    input_vec[POS_ENC_DIM + 2] = hit_normal.z;
}

// ----- One Linear+ReLU layer using row-major fp16 weights -------------------
//
// Weights are stored as `rows x cols` row-major fp16, base offset `weightByteOff`.
// Element (r, c) sits at `weightByteOff + (r * cols + c) * 2`.

void linearReLU(uint rows, uint cols,
                uint weightByteOff, uint biasByteOff,
                float src[64], out float dst[64])
{
    for (uint r = 0; r < rows; ++r)
    {
        float acc = loadHalf(gMlpBiases, biasByteOff + r * 2u);
        uint rowBase = weightByteOff + r * cols * 2u;
        for (uint c = 0; c < cols; ++c)
            acc += loadHalf(gMlpWeights, rowBase + c * 2u) * src[c];
        dst[r] = max(acc, 0.0f);
    }
}

// Final layer: 3 outputs from 64 inputs, no ReLU on output.
float3 linearOut3(uint weightByteOff, uint biasByteOff, float src[64])
{
    float3 y;
    [unroll]
    for (uint r = 0; r < 3u; ++r)
    {
        float acc = loadHalf(gMlpBiases, biasByteOff + r * 2u);
        uint rowBase = weightByteOff + r * MLP_W * 2u;
        for (uint c = 0; c < MLP_W; ++c)
            acc += loadHalf(gMlpWeights, rowBase + c * 2u) * src[c];
        y[r] = acc;
    }
    return y;
}

float3 evalNIV(float3 hit_pos, float3 hit_normal)
{
    float input_vec[MLP_INPUT];
    encodeInput(hit_pos, hit_normal, input_vec);

    uint w0 = gMlpOffsets[0]; uint w1 = gMlpOffsets[1]; uint w2 = gMlpOffsets[2]; uint w3 = gMlpOffsets[3];
    uint b0 = gMlpOffsets[4]; uint b1 = gMlpOffsets[5]; uint b2 = gMlpOffsets[6]; uint b3 = gMlpOffsets[7];

    // Layer 0: 64 x 35
    float h0[64];
    for (uint r = 0; r < MLP_W; ++r)
    {
        float acc = loadHalf(gMlpBiases, b0 + r * 2u);
        uint rowBase = w0 + r * MLP_INPUT * 2u;
        for (uint c = 0; c < MLP_INPUT; ++c)
            acc += loadHalf(gMlpWeights, rowBase + c * 2u) * input_vec[c];
        h0[r] = max(acc, 0.0f);
    }

    // Layers 1, 2: 64 x 64 with ReLU.
    float h1[64];
    linearReLU(MLP_W, MLP_W, w1, b1, h0, h1);
    float h2[64];
    linearReLU(MLP_W, MLP_W, w2, b2, h1, h2);

    // Layer 3: 3 x 64, no ReLU but clamp >= 0 (irradiance).
    float3 y = linearOut3(w3, b3, h2);
    return float3(max(y.x, 0.0f), max(y.y, 0.0f), max(y.z, 0.0f));
}

[shader("compute")]
[numthreads(16, 16, 1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    if (any(tid.xy >= gResolution))
        return;

    int2   ipix   = int2(tid.xy);
    float4 pos4   = gPosW.Load(int3(ipix, 0));
    bool   isHit  = pos4.w >= 0.5f;
    float3 hitPos = pos4.xyz;
    float3 hitN   = normalize(gNormW.Load(int3(ipix, 0)).xyz);
    float3 albedo = gDiffuseOpacity.Load(int3(ipix, 0)).xyz;

    float3 color = float3(0);

    if (isHit && gEnableIndirect != 0)
    {
        float3 irradiance = evalNIV(hitPos, hitN);
        color += gNivScale * albedo * (irradiance / 3.14159265f);
    }

    // Direct lighting deferred — kept as a UI toggle for the follow-up step.
    if (gEnableDirect != 0)
    {
        // intentionally empty for now
    }

    color *= gExposure;
    gOutputColor[ipix] = float4(color, 1.0f);
}
