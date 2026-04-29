/***************************************************************************
 # Copyright (c) 2015-23, NVIDIA CORPORATION. All rights reserved.
 #
 # Redistribution and use in source and binary forms, with or without
 # modification, are permitted provided that the following conditions
 # are met:
 #  * Redistributions of source code must retain the above copyright
 #    notice, this list of conditions and the following disclaimer.
 #  * Redistributions in binary form must reproduce the above copyright
 #    notice, this list of conditions and the following disclaimer in the
 #    documentation and/or other materials provided with the distribution.
 #  * Neither the name of NVIDIA CORPORATION nor the names of its
 #    contributors may be used to endorse or promote products derived
 #    from this software without specific prior written permission.
 #
 # THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS "AS IS" AND ANY
 # EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 # IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 # PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 # CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 # EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 # PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 # PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 # OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 # (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 # OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 **************************************************************************/
#pragma once
#include "Utils/HostDeviceShared.slangh"

#ifdef HOST_CODE
#include "Scene/HitInfoType.slang"
#else
__exported import Scene.HitInfoType;
#endif

BEGIN_NAMESPACE_FALCOR

/**
 * Pixel data read out by the PixelInspectorPass.
 */
struct PixelData
{
    static const uint kInvalidIndex = 0xffffffff;

    // Geometry data
    float3 posW = float3(0);
    float3 normal = float3(0);
    float3 tangent = float3(0);
    float3 bitangent = float3(0);
    float3 faceNormal = float3(0);
    float3 view = float3(0);
    float2 texCoord = float2(0);
    int frontFacing = 0;

    // Material data
    uint materialID = 0;
    int doubleSided = 0;
    float opacity = 0.f;
    float IoR = 0.f;

    // Material instance properties
    float3 emission = float3(0);
    float roughness = 0.f;
    float3 guideNormal = float3(0);
    float3 diffuseReflectionAlbedo = float3(0);
    float3 diffuseTransmissionAlbedo = float3(0);
    float3 specularReflectionAlbedo = float3(0);
    float3 specularTransmissionAlbedo = float3(0);
    float3 specularReflectance = float3(0);
    int isTransmissive = 0;

    // Output data
    float4 linearColor = float4(0);
    float4 outputColor = float4(0);
    float luminance = 0.f;

    // Visibility data
    uint hitType = 0;
    uint instanceID = kInvalidIndex;
    uint primitiveIndex = kInvalidIndex;
    float2 barycentrics = float2(0);
};

END_NAMESPACE_FALCOR
