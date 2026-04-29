/***************************************************************************
 # Copyright (c) 2015-24, NVIDIA CORPORATION. All rights reserved.
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
import Scene.Material.MaterialData;
import Utils.Geometry.GeometryHelpers;
import Utils.Math.ShadingFrame;

/** This struct holds information needed for shading a hit point.

    This includes:
    - Geometric properties of the surface.
    - View direction.
    - Texture coordinates.
    - Material ID and header.
    - Index of refraction of the surrounding medium.

    Based on a ShadingData struct, the material system can be queried
    for a material instance at the hit using `gScene.materials.getMaterialInstance()`.
    The material instance has interfaces for sampling and evaluation, as well as for
    querying its properties at the hit.
*/
struct ShadingData : IDifferentiable
{
    // Geometry data
    float3  posW = float3(0);            ///< Shading hit position in world space.
    float3  V = float3(0);              ///< View direction, -incident direction (-ray.dir)
    float2  uv = float2(0);            ///< Texture mapping coordinates.

    ShadingFrame frame;                 ///< Smooth interpolated shading frame in world space at the shading point.
    no_diff float3  faceN = float3(0);  ///< Face normal in world space, always on the front-facing side.
    no_diff float4  tangentW = float4(0); ///< Geometric tangent (xyz) and sign (w) in world space.
    bool            frontFacing = false;///< True if primitive seen from the front-facing side.
    no_diff float   curveRadius = 0.f;  ///< Curve cross-sectional radius. Valid only for geometry generated from curves.

    // Material data
    MaterialHeader mtl;                 ///< Material header data.
    uint    materialID = 0;             ///< Material ID at shading location.
    float   IoR = 0.f;                  ///< Index of refraction for the medium on the front-facing side.

    uint materialGradOffset = 0;        ///< Offset to the material gradient in the gradient buffer.
    uint geometryGradOffset = 0;        ///< Offset to the geometry gradient in the gradient buffer.
    uint threadID = 0;                  ///< Thread ID for gradient aggregation with a hash grid.

    __init()
    {
        posW = float3(0); V = float3(0); uv = float2(0);
        faceN = float3(0); tangentW = float4(0); frontFacing = false; curveRadius = 0.f;
        materialID = 0; IoR = 0.f;
        materialGradOffset = 0; geometryGradOffset = 0; threadID = 0;
    }

    // Utility functions

    /** Computes new ray origin based on the hit point to avoid self-intersection.
        The method is described in Ray Tracing Gems, Chapter 6, "A Fast and Robust
        Method for Avoiding Self-Intersection" by Carsten Wächter and Nikolaus Binder.
        \param[in] viewside True if the origin should be on the view side (reflection) or false otherwise (transmission).
        \return Ray origin of the new ray.
    */
    float3 computeRayOrigin(bool viewside = true)
    {
        return computeRayOrigin(posW, (frontFacing == viewside) ? faceN : -faceN);
    }

    /** Returns the oriented face normal.
        \return Face normal flipped to the same side as the view vector.
    */
    float3 getOrientedFaceNormal()
    {
        return frontFacing ? faceN : -faceN;
    }
};
