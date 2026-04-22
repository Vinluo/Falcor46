# Falcor 使用文档:构建、Bistro 场景、ReSTIR 用例

面向首次使用本仓库的研究人员,覆盖三件事:
1. 把工程从零编译出来,跑起来 `Mogwai`。
2. 获取 Amazon Lumberyard Bistro 场景并在 Mogwai 中加载渲染。
3. 组织一个 ReSTIR 路径追踪相关的用例(含当前仓库内可用的 ReSTIR DI 最佳实践,以及真正意义上的 "ReSTIR PT" 的说明)。

> 文档基于当前分支 `08e9e8b3 Vs2026 build support, initial wiki add`,对应 Falcor 8.0 + VS2026 构建补丁。

---

## 1. 构建 Falcor

### 1.1 前置条件

- Windows 10 20H2 或更新(OS build ≥ .789)。
- **Visual Studio 2022**(推荐)或 **Visual Studio 2026**(仓库已加 preset)。
- Windows 10 SDK 10.0.19041.0。
- 支持 DXR 的 GPU(Titan V / GeForce RTX 系列)。
- NVIDIA 驱动 ≥ 466.11。
- 可选但建议:CUDA 11.6.2+ (用于 `CudaInterop` / `OptixDenoiser`)、OptiX SDK 7.3(解压到 `external/packman/optix`)、NVAPI R535(解压到 `external/packman/nvapi`)。

Linux 仅实验性支持 Ubuntu 22.04,此处不展开。

### 1.2 一键生成解决方案(VS2022)

```bat
:: 仓库根目录
setup_vs2022.bat
```

`setup_vs2022.bat` 会先调 `setup.bat` 拉依赖(通过 packman),然后执行 `cmake --preset windows-vs2022` 生成解决方案。产物位置:

- 解决方案:`build/windows-vs2022/Falcor.sln`
- 可执行:`build/windows-vs2022/bin/[Debug|Release]/Mogwai.exe`

用 VS 打开 `.sln`,默认启动项即 Mogwai。生成模式建议直接用 `Release` 或 `RelWithDebInfo`,`Debug` 仅在需要调试 C++ 侧代码时使用(shader 热重载 F5 与 debug build 是两回事)。

### 1.3 VS2026 / Ninja / CLI 构建

仓库的 `CMakePresets.json` 已新增 `windows-vs2026` / `windows-vs2026-ci` preset。当前 `setup_vs2026.bat` 为空壳,直接用 cmake 即可:

```bat
cmake --list-presets
cmake --preset windows-vs2026
cmake --build build/windows-vs2026 --config Release
```

如果你更偏好命令行 + Ninja:

```bat
cmake --preset windows-ninja-msvc
cmake --build build/windows-ninja-msvc
```

### 1.4 Shader 热重载

从 Visual Studio 里启动 Mogwai 时,`FALCOR_DEVMODE=1` 会自动设置,运行时按 **F5** 重载 shader,无需重启进程。直接双击 exe 启动不会自动开 devmode,要么手动 `set FALCOR_DEVMODE=1` 再启动,要么始终用 VS 调试启动。

### 1.5 构建产物目录结构(重要)

构建系统会把 `Source/*/Data/` 下的数据文件同步到 `build/<preset>/bin/<Config>/Data/`,shader 同步到 `Shaders/` 子目录。这意味着发布的可执行目录是**自包含**的,可以打包拷走。

`Source/Mogwai/` 下**没有** `Data/` 目录(README 里提到的路径是早期版本);当前仓库里所有示例 render graph 脚本都放在根目录的 `scripts/`:

```
scripts/
  PathTracer.py        # 标准路径追踪(可选启用 RTXDI)
  PathTracerNRD.py     # 带 NRD 实时降噪
  MinimalPathTracer.py # 最小参考实现
  RTXDI.py             # 纯 ReSTIR DI 管线
  WARDiffPathTracer.py # 可微分路径追踪
  BSDFViewer.py, SceneDebugger.py, ...
```

---

## 2. 运行 Mogwai 并加载 Bistro

### 2.1 Mogwai 命令行

```
Mogwai [-d d3d12|vulkan] [--gpu=<idx>] [--headless]
       [-s scripts/PathTracer.py] [-S <scene.pyscene|.fbx|.usd|.gltf>]
       [-c]                  # 使用 scene cache 加速加载
       [--rebuild-cache]     # 强制重建 cache
       [--width=] [--height=] [--debug-shaders] [--enable-debug-layer]
```

示例(Arcade 样例场景,仓库自带):

```bat
build\windows-vs2022\bin\Release\Mogwai.exe ^
  --script=scripts\PathTracer.py ^
  --scene=media\Arcade\Arcade.pyscene ^
  --use-cache
```

在 UI 内等价操作:`Ctrl+O` 选脚本,`Ctrl+Shift+O` 选场景,或直接拖拽文件进窗口。

常用快捷键:`F2` 隐藏 GUI,`` ` `` 打开 Python 控制台,`F5` 重载 shader(需 devmode),`F12` 截图,`Space` 暂停全局时钟。相机:`WASD` 平移 + 左键拖拽旋转,`Shift` 加速。

### 2.2 获取 Bistro 场景

仓库本体不带 Bistro 资产,通过 `tools/fetch_bistro.bat` 作为"外部依赖"拉取:

```bat
tools\fetch_bistro.bat
```

下载约 853 MB(zip),解压约 1.7 GB。产物落在:

```
external/assets/Bistro/
  Bistro_v5_2.zip                   # 原档,可删除也可留作重解压
  .extracted                        # 完成标记,避免重复解压
  Bistro_v5_2/
    BistroExterior.fbx              # 120 MB, 2.8M 三角面
    BistroExterior.pyscene          # ← 官方随档 pyscene,直接可用
    BistroInterior.fbx              # 42 MB, 1.05M 三角面
    BistroInterior_Wine.fbx         # 49 MB, 加了酒杯填充材质
    BistroInterior_Wine.pyscene     # ← 官方随档 pyscene
    san_giuseppe_bridge_4k.hdr      # 室外 HDRI
    Textures/                       # 全部 DDS,BaseColor/Specular/Normal/Emissive
    README.txt  LICENSE.txt  CHANGELOG.txt
```

整个 `external/assets/` 在 `.gitignore` 中屏蔽(例外:`README.md`)。即便落在仓库目录内,也不会进 git。

把这个目录加到 Falcor 的媒体搜索路径,`.pyscene` 里就能按相对名引用 FBX / HDRI:

```bat
setx FALCOR_MEDIA_FOLDERS "%CD%\external\assets\Bistro\Bistro_v5_2"
```

(重启 VS / Mogwai 生效。)

### 2.3 官方 `BistroExterior.pyscene` 的内容

随档的 `BistroExterior.pyscene` 本身就是最小可用版本:

```python
# Load scene
sceneBuilder.importScene("BistroExterior.fbx")

# Load environment map
sceneBuilder.envMap = EnvMap("san_giuseppe_bridge_4k.hdr")
sceneBuilder.envMap.intensity = 10
```

研究中通常会在其上加固定相机、改光源强度、材质调整等。参考写法:

```python
# external/assets/Bistro/Bistro_v5_2/BistroExterior_custom.pyscene
sceneBuilder.importScene("BistroExterior.fbx")

envMap = EnvMap("san_giuseppe_bridge_4k.hdr")
envMap.intensity = 5.0
sceneBuilder.envMap = envMap

sun = DirectionalLight("Sun")
sun.intensity = float3(3.0, 2.8, 2.5)
sun.direction = float3(-0.3, -1.0, -0.2)
sceneBuilder.addLight(sun)

cam = Camera("PT_Ref")
cam.position    = float3(-6.0, 2.0, 1.0)
cam.target      = float3( 0.0, 1.5, 0.0)
cam.up          = float3( 0.0, 1.0, 0.0)
cam.focalLength = 35.0
sceneBuilder.addCamera(cam)
sceneBuilder.selectedCamera = cam
```

### 2.4 启动 Bistro

命令行(绝对路径,无需 `FALCOR_MEDIA_FOLDERS`):

```bat
build\windows-vs2022\bin\Release\Mogwai.exe ^
  --script=scripts\PathTracer.py ^
  --scene=external\assets\Bistro\Bistro_v5_2\BistroExterior.pyscene ^
  --use-cache
```

或在 UI 里:`Ctrl+O` 加载 `scripts/PathTracer.py` → `Ctrl+Shift+O` 加载 `external/assets/Bistro/Bistro_v5_2/BistroExterior.pyscene`。首次加载会构建 scene cache(几十秒到一两分钟),后续带 `--use-cache` 秒开。

---

## 3. ReSTIR 路径追踪用例

### 3.1 先说清楚:这个仓库有什么、没有什么

在代码里搜 `ReSTIR`,只命中 5 个文件,集中在 `RTXDIPass` 和 `Source/Falcor/Rendering/RTXDI/`。**当前仓库(Falcor 8.0)提供的是 ReSTIR DI**——基于 RTXDI SDK 的重采样直接光照。**没有独立的 ReSTIR PT(全路径复用)render pass**。真正的 "ReSTIR PT"(Lin 等 2022)目前只能通过以下方式获取:

- 使用 NVIDIA 公开的 `ReSTIR_PT` 研究代码(基于旧版 Falcor,独立仓库);
- 或自行实现为新的 render pass。

本节给出**仓库内能直接跑通的 ReSTIR DI 用例**,并在最后给出升级到 ReSTIR PT 的起点。

### 3.2 用例 A:`RTXDI.py` —— 纯 ReSTIR DI(单跳直接光)

这条管线只做 vbuffer → RTXDI → accumulate → tonemap,不追二次路径,适合验证 RTXDI 本身、做光源采样对比。核心定义见 `scripts/RTXDI.py`:

```
VBufferRT.vbuffer → RTXDIPass.vbuffer
VBufferRT.mvec    → RTXDIPass.mvec
RTXDIPass.color   → AccumulatePass.input → ToneMapper.src → output
```

启动:

```bat
Mogwai.exe -s scripts\RTXDI.py -S D:\Assets\Bistro\BistroInterior.pyscene -c
```

适用场景:Bistro 里有大量发光材质(酒瓶标签、灯具),用于复现"数百到数千个重要光源"的 ReSTIR DI 典型效果。

参数建议(在 UI 的 `RTXDIPass` 分组内):
- **Initial candidates**:16–32,再多边际收益递减。
- **Temporal resampling**:开,`history length` 20。
- **Spatial resampling**:开,passes=1~2,radius=20px。
- **MIS with BRDF samples**:开,在高光/光泽表面能明显压噪。

### 3.3 用例 B:`PathTracer.py` + `useRTXDI=True` —— 全路径追踪中用 ReSTIR 处理 NEE

这是研究里最常用的组合:二次反弹及以上仍走标准 NEE+MIS,但每个顶点的直接光照采样换成 ReSTIR。`PathTracer` pass 内置了这个开关(见 `PathTracer.h:133`, `PathTracer.cpp:130` 附近的 `kUseRTXDI`)。

修改 `scripts/PathTracer.py` 里的 pass 构造:

```python
PathTracer = createPass("PathTracer", {
    'samplesPerPixel': 1,
    'useRTXDI': True,         # 打开 ReSTIR DI
    'useNEE': True,           # NEE 与 RTXDI 不冲突
    'useMIS': True,
    'maxSurfaceBounces': 10,
    'maxDiffuseBounces': 3,
    'maxSpecularBounces': 3,
    'maxTransmissionBounces': 10,
})
```

注意,`useRTXDI` 和 `samplesPerPixel>1` 叠加时只会生成 1 个 RTXDI 样本供所有 pixel sample 复用(见 `PathTracer.cpp:1059` 的 warning),想做 multi-spp 比对请改用外层 `AccumulatePass` 做时间累积。

### 3.4 用例 C:参考图对比(Reference vs ReSTIR)

用于论文/报告里做 quality 对比。思路:同一个相机、同一个场景,跑两条图,`ErrorMeasurePass` 输出 MSE/SSIM。

在 scripts 目录下新建 `BistroReSTIRCompare.py`:

```python
from falcor import *

def _common_tail(g, src_name):
    acc = createPass("AccumulatePass", {'enabled': True, 'precisionMode': 'Single'})
    tm  = createPass("ToneMapper",     {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(acc, "Accumulate"); g.addPass(tm, "ToneMap")
    g.addEdge(f"{src_name}.color", "Accumulate.input")
    g.addEdge("Accumulate.output", "ToneMap.src")
    g.markOutput("ToneMap.dst")

def make_reference():
    g = RenderGraph("Reference_PT")
    vb = createPass("VBufferRT", {'samplePattern': 'Stratified', 'sampleCount': 16})
    pt = createPass("PathTracer", {
        'samplesPerPixel': 1, 'useRTXDI': False,
        'useNEE': True, 'useMIS': True,
        'maxSurfaceBounces': 16,
        'maxDiffuseBounces': 8, 'maxSpecularBounces': 8, 'maxTransmissionBounces': 16,
    })
    g.addPass(vb, "VBufferRT"); g.addPass(pt, "PathTracer")
    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW",   "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec",    "PathTracer.mvec")
    _common_tail(g, "PathTracer")
    return g

def make_restir():
    g = RenderGraph("PT_ReSTIR_DI")
    vb = createPass("VBufferRT", {'samplePattern': 'Stratified', 'sampleCount': 16})
    pt = createPass("PathTracer", {
        'samplesPerPixel': 1, 'useRTXDI': True,
        'useNEE': True, 'useMIS': True,
        'maxSurfaceBounces': 8,
        'maxDiffuseBounces': 3, 'maxSpecularBounces': 3, 'maxTransmissionBounces': 8,
    })
    g.addPass(vb, "VBufferRT"); g.addPass(pt, "PathTracer")
    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW",   "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec",    "PathTracer.mvec")
    _common_tail(g, "PathTracer")
    return g

try:
    m.addGraph(make_reference())
    m.addGraph(make_restir())
except NameError:
    pass
```

启动后在 Mogwai 的 Graphs 下拉里切换 `Reference_PT` / `PT_ReSTIR_DI` 做并排截图对比。参考图跑够 spp(几千帧)后 `F12` 存盘,再切换到 ReSTIR 同视角截图即可。

### 3.5 真正的 ReSTIR PT(完整路径复用)

如果研究目标是完整路径重采样(而非仅直接光),当前仓库不够,建议路线:

1. **对齐参考实现**:阅读 NVIDIA 的 `ReSTIR_PT` 研究仓库(论文 "Generalized Resampled Importance Sampling",2022),它 fork 自较早版本的 Falcor。
2. **移植到 Falcor 8.0**:建一个新 render pass(`tools\make_new_render_pass.bat ReSTIRPTPass`),把其中的 reservoir 结构、shift mapping(hybrid / random replay / reconnection)移过来。瓶颈通常是 `PathState` / `GuideData` 里需要保留路径顶点信息,这部分 `Source/RenderPasses/PathTracer/PathState.slang` 可作为起点。
3. **复用现有 MIS / 光源采样**:Falcor 8.0 的 `LightHelpers`, `EmissiveLightSampler`, `EnvMapSampler` 可以直接用,不必重写。

在此之前,把 3.3 节的 `PathTracer + useRTXDI` 作为 baseline 即可覆盖"ReSTIR"相关的大部分课堂/开题演示需求。

---

## 4. 排错速查

| 症状 | 原因 / 解法 |
| --- | --- |
| `setup.bat` 拉依赖卡住 | packman 走的是 NVIDIA 内部 CDN,确认网络;重跑脚本即可断点续传 |
| `F5` 按了没反应 | 没开 `FALCOR_DEVMODE=1`,或者你从 Release exe 直接双击启动 |
| 加载 Bistro 很慢 | 首次加载要建 scene cache,加 `--use-cache`,后续秒开;改了 FBX 后加 `--rebuild-cache` |
| `BistroInterior.fbx not found` | 没设 `FALCOR_MEDIA_FOLDERS`,或者 `.pyscene` 里用了绝对路径但路径不对 |
| 启用 RTXDI 后出现 warning "samples/pixel != 1" | 把 `samplesPerPixel` 改成 1,用 `AccumulatePass` 做多帧累积 |
| `OptixDenoiser` 编译失败 | 没装 CUDA 或 OptiX SDK,或没放到 `external/packman/optix`(见 README §OptiX) |
| VS 报 `Windows SDK 10.0.19041.0 not found` | 安装对应版本 SDK 后 `cmake --preset windows-vs2022` 重新生成解决方案 |

---

## 5. 相关文件索引

- 构建脚本:`setup_vs2022.bat`, `setup_vs2026.bat`, `CMakePresets.json`
- 示例 Render Graph:`scripts/PathTracer.py`, `scripts/RTXDI.py`, `scripts/PathTracerNRD.py`, `scripts/MinimalPathTracer.py`
- Path Tracer 参数定义:`Source/RenderPasses/PathTracer/PathTracer.h` (StaticParams), `PathTracer.cpp` (properties 序列化)
- RTXDI 集成:`Source/RenderPasses/RTXDIPass/`, `Source/Falcor/Rendering/RTXDI/`
- Mogwai 使用教程:`docs/tutorials/01-mogwai-usage.md`
- 场景 Python DSL:`docs/usage/scene-formats.md`, `docs/usage/scripting.md`
- Path Tracer 原理与参数说明:`docs/usage/path-tracer.md`
