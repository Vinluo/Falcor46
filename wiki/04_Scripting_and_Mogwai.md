# 脚本与 Mogwai 使用

Falcor 最大的特色之一是其脚本能力。通过 Python，你可以定义渲染管线、控制场景参数和执行自动化测试。

## Mogwai 脚本接口
Mogwai 启动时可以加载一个 Python 脚本。该脚本主要用于构建 Render Graph。

### 基本结构示例
```python
from falcor import *

def render_graph_DefaultRenderGraph():
    g = RenderGraph('MyGraph')
    
    # 添加 Passes
    loadRenderPassLibrary('GBuffer.dll')
    loadRenderPassLibrary('AccumulatePass.dll')
    loadRenderPassLibrary('ToneMapper.dll')
    
    g.addPass(createPass('GBufferRaster'), 'GBuffer')
    g.addPass(createPass('AccumulatePass'), 'Accumulate')
    g.addPass(createPass('ToneMapper', {'autoExposure': True}), 'ToneMapping')
    
    # 连接 Edges
    g.addEdge('GBuffer.vbuffer', 'Accumulate.input')
    g.addEdge('Accumulate.output', 'ToneMapping.src')
    
    # 标记输出到屏幕
    g.markOutput('ToneMapping.dst')
    
    return g

# Mogwai 会自动调用这个函数来加载图
m.addGraph(render_graph_DefaultRenderGraph())
```

## 常用功能
- **loadRenderPassLibrary(name)**: 加载 C++ 编译好的 Render Pass DLL。
- **createPass(className, dictionary)**: 创建 Pass 实例，可以通过字典传递初始参数。
- **addEdge(src, dst)**: 连接 Pass。格式为 `'PassName.OutputName', 'PassName.InputName'`。
- **Scene Control**: 可以通过 `scene.camera` 等对象在脚本中控制相机位置、光照强度等，非常适合制作动画或批量生成数据集。

## 自动化
你可以编写脚本来：
1. 加载场景。
2. 设置特定的相机视角。
3. 渲染 N 帧。
4. 将结果保存到磁盘。
5. 退出程序。
这使得 Falcor 成为生成机器学习训练数据的绝佳工具。
