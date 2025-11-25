# 关键组件与抽象

## 场景系统 (Scene System)
位于 `Source/Falcor/Scene`。
- **Scene 类**: 是场景图的根节点，包含所有的几何体、材质、灯光和相机。
- **Importer**: 支持多种格式，最常用且支持最好的是 USD 和 glTF。
- **Animation**: 内置支持骨骼动画和关键帧动画。
- **Ray Tracing**: Scene 类会自动维护用于光线追踪的加速结构（TLAS/BLAS），当场景物体移动时自动更新。

## 材质系统 (Material System)
Falcor 拥有一个强大的材质系统，紧密集成 Slang 语言。
- **Standard Material**: 基于物理的渲染（PBR）标准材质模型。
- **Material System**: 负责管理着色器代码的生成和宏定义的组合，以支持不同的材质类型。

## 着色器系统 (Shader System & Slang)
Falcor 使用 **Slang** 作为其主要的着色语言。
- **Slang**: 由 NVIDIA 开发，向后兼容 HLSL，但增加了模块化、泛型和接口等现代编程语言特性。
- **Hot Reload**: Falcor 支持着色器的热重载。修改 `.slang` 文件后，引擎会自动检测并重新编译，无需重启程序。
- **Shader Reflection**: 自动反射 C++ 和 Slang 之间的数据结构，简化了 Constant Buffer 和资源绑定的管理。

## 资源管理 (Resource Management)
- **Fbo (Frame Buffer Object)**: 封装了 Render Target 和 Depth Stencil。
- **Texture & Buffer**: 提供了高层的创建和视图（SRV/UAV/RTV）管理接口。
- **Resource Views**: 自动处理资源视图的创建，开发者通常只需传递资源对象本身。
