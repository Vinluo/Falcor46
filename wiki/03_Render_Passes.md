# Render Passes 库概览

Falcor 在 `Source/RenderPasses` 中提供了大量的预置渲染通道，这是进行研究的宝贵资源。

## 基础光栅化 (Rasterization)
- **GBuffer**: 生成几何缓冲区（Albedo, Normal, Depth, Motion Vectors 等）。这是大多数延迟渲染和混合渲染管线的基础。
- **BlitPass**:简单的纹理拷贝。
- **SkyBox**: 渲染环境贴图或程序化天空。

## 光线追踪 (Ray Tracing)
- **PathTracer**: 全功能的路径追踪器参考实现。支持多重重要性采样（MIS）、Next Event Estimation (NEE) 等。
- **MinimalPathTracer**: 简化版的路径追踪器，适合学习和作为修改的起点。
- **WhittedRayTracer**: 经典的 Whitted 风格光线追踪。
- **RTXDIPass**: 实现了 RTXDI (Direct Illumination) 算法，用于处理大量光源的高效采样。

## 降噪与后处理 (Denoising & Post-Process)
- **SVGFPass**: Spatiotemporal Variance-Guided Filtering，一种流行的实时光追降噪算法。
- **NRDPass**: NVIDIA Real-Time Denoiser 集成。
- **OptixDenoiser**: 集成 OptiX AI 降噪器。
- **ToneMapper**: 色调映射，将 HDR 转换为 LDR。
- **TAA**: 时间抗锯齿。
- **DLSSPass**: Deep Learning Super Sampling 集成。

## 调试与工具 (Debug & Utils)
- **SceneDebugger**: 允许在视口中可视化场景的各种属性（法线、UV、材质ID等）。
- **PixelInspectorPass**: 检查特定像素的值。
- **ErrorMeasurePass**: 用于比较两张图像（例如 Ground Truth 和 渲染结果）的误差（MSE, PSNR 等）。
- **AccumulatePass**: 用于累积多帧结果，常用于生成 Ground Truth 图像。

## 其它
- **DiffRendering**: 包含一些可微渲染相关的实验性 Pass。
