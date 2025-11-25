# Falcor 学习计划

作为一个刚开始接触 Falcor 的研究人员，建议按照以下阶段进行学习：

## 阶段 1：环境搭建与运行 (1-2 天)
- **目标**: 成功编译项目，并运行内置示例。
- **任务**:
    1. 运行 `setup_vs2022.bat` (Windows) 或 `setup.sh` (Linux) 下载依赖。
    2. 编译 `Mogwai` 和所有 `RenderPasses`。
    3. 启动 `Mogwai`，加载一个简单的脚本（如 `LoadScene.py` 或手动加载 Render Graph）。
    4. 尝试加载不同的场景文件 (.gltf / .usd)。
    5. 在 UI 中尝试开启/关闭不同的 Render Pass，观察效果。

## 阶段 2：Render Graph 脚本编写 (2-3 天)
- **目标**: 理解如何通过 Python 组合现有的 Pass。
- **任务**:
    1. 阅读 `scripts/` 目录下的现有 Python 脚本。
    2. 编写一个新的 Python 脚本，构建一个包含 `GBuffer` -> `ToneMapper` 的简单管线。
    3. 尝试加入 `AccumulatePass` 来实现抗锯齿效果（通过多帧累积）。
    4. 学习如何在 Python 中修改 Pass 的参数（例如修改 ToneMapper 的曝光度）。

## 阶段 3：代码阅读与调试 (1 周)
- **目标**: 理解 C++ 层面的执行流程。
- **任务**:
    1. 使用 Visual Studio 或 VS Code 调试器附加到 Mogwai。
    2. 断点 `Source/Falcor/Core/Window.cpp` 或 `SampleApp.cpp`，理解启动流程。
    3. 重点阅读 `Source/RenderPasses/MinimalPathTracer` 的代码。这是学习光线追踪实现的最佳入口。
    4. 理解 `execute()` 函数的数据流：如何获取 Input Texture，如何写入 Output Texture。

## 阶段 4：编写自定义 Render Pass (1-2 周)
- **目标**: 实现自己的渲染算法。
- **任务**:
    1. 使用 `tools/make_new_render_pass.py` 脚本创建一个新的 Pass 模板（例如 `MyFirstPass`）。
    2. 在该 Pass 中实现一个简单的图像处理效果（例如反色、灰度化）。
    3. **进阶**: 尝试修改 `MinimalPathTracer`，例如修改其 BRDF 或添加一种新的光源类型。
    4. 学习如何编写 `.slang` shader 并在 C++ 中绑定变量。

## 阶段 5：深入研究 (长期)
- **目标**: 利用 Falcor 进行前沿研究。
- **方向**:
    - **Neural Rendering**: 探索如何将 PyTorch/TensorFlow 与 Falcor 结合（Falcor 支持 CUDA/Python 互操作）。
    - **Advanced Ray Tracing**: 研究 `RTXDIPass` 或 `ReSTIR` 等高级采样算法的实现。
    - **Differentiable Rendering**: 查看 `DiffRendering` 目录。

## 推荐资源
- `docs/index.md`: 官方文档入口。
- `Source/Samples/`: 简单的独立示例，如果觉得 Mogwai 太复杂，可以先看这里。
- `Source/RenderPasses/RenderPassTemplate`: 官方提供的 Pass 模板代码。
