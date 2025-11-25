# Falcor 架构概览

Falcor 是 NVIDIA 开发的一个用于实时渲染研究的开源框架。它旨在提供高效、灵活且易于使用的 API，支持 DX12、Vulkan 和 DXR/Ray Tracing。

## 核心组件层次

Falcor 的架构可以大致分为以下三个层次：

### 1. Core (Source/Falcor)
这是引擎的基础库，提供了渲染所需的底层抽象和工具。
- **API Abstraction**: 封装了 DirectX 12 和 Vulkan 的差异，提供统一的 `Device`, `Buffer`, `Texture`, `Program` 等接口。
- **Scene System (`Source/Falcor/Scene`)**: 处理 3D 场景的加载（支持 glTF, FBX 等）、材质系统、灯光和摄像机管理。
- **Render Graph (`Source/Falcor/RenderGraph`)**: 核心执行模型。允许用户将渲染算法分解为独立的 "Pass"（节点），并通过有向无环图（DAG）连接它们的数据流。
- **Python Bindings**: 整个框架深度集成了 Python，允许在运行时控制场景和渲染管线。

### 2. Mogwai (Source/Mogwai)
Mogwai 是基于 Falcor 构建的主要 **应用程序宿主 (Application Host)**。
- 它是一个通用的渲染器外壳，负责加载渲染脚本、创建窗口、处理输入以及运行 Render Graph。
- 研究人员通常不需要修改 Mogwai 的 C++ 代码，而是通过编写 Python 脚本或使用 GUI 来配置渲染管线。
- 它支持加载 `.py` 脚本来定义渲染图（Render Graph）。

### 3. Render Passes (Source/RenderPasses)
这是具体的渲染算法库。每个 Render Pass 都是一个独立的 C++ 类，继承自 `RenderPass` 基类。
- 它们编译为独立的 DLL/Shared Library。
- 可以在运行时动态加载。
- 包含从简单的 `GBuffer` 生成到复杂的 `PathTracer` 和 `DLSS` 集成。

## 渲染图 (Render Graph) 执行模型

Falcor 的核心理念是 **Render Graph**。
1. **定义**: 用户定义一系列节点（Passes）和它们之间的边（Edges）。边代表纹理或缓冲区的数据流。
2. **资源管理**: Render Graph 自动处理资源的生命周期和屏障（Barriers），确保读写同步正确，极大地减轻了开发者的负担。
3. **复用性**: 比如 `GBuffer` Pass 可以被光栅化管线使用，也可以被光追管线使用，提高了代码复用率。

## 目录结构映射

- `Source/Falcor`: 核心引擎代码。
- `Source/Mogwai`: 脚本运行器和 GUI 前端。
- `Source/RenderPasses`: 渲染算法插件集合。
- `Source/Samples`: 独立的 C++ 示例程序（不使用 Mogwai/RenderGraph 的简单示例）。
