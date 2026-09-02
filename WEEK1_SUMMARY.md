# VisionTrace 第一周项目小结

| 项目 | 内容 |
|---|---|
| 周期 | Week 1 |
| 日期 | 2026-09-02 |
| 版本 | `week1-v1` |
| 状态 | 已完成并通过测试 |

## 1. 本周目标

根据 PRD 的 Week 1 计划，本周不提前实现最终缺陷检测模型，而是完成所有后续算法都要依赖的基础数据链路：

1. 建立可维护的项目目录和配置方式；
2. 统一读取视频文件和摄像头；
3. 理解并记录图像矩阵、BGR、灰度和 HSV 信息；
4. 将归一化检测区域 ROI 映射为实际像素坐标；
5. 建立一个简单、可解释的 ROI 活动检测基线；
6. 生成不依赖外部数据的模拟生产线视频；
7. 输出可供后续分析和审计的数据文件；
8. 使用自动化测试验证关键组件和端到端链路。

## 2. 本周交付结果

### 2.1 可运行的软件组件

- `VideoSource`：统一视频文件和摄像头读取；
- `FrameAnalyzer`：逐帧图像矩阵与颜色空间统计；
- `RoiOccupancyDetector`：ROI 背景标定、活动比例和状态转换；
- `generate_demo_video`：生成确定性的模拟生产线测试视频；
- `run_week1_pipeline`：串联读取、分析、标注和结果落盘；
- YAML 配置：视频源、ROI、活动阈值和输出策略集中管理；
- CLI 脚本：一条命令生成视频，一条命令运行处理链路。

### 2.2 实际生成的产物

| 产物 | 路径 | 用途 |
|---|---|---|
| 原始模拟产线视频 | `assets/videos/week1_line_demo.mp4` | 可重复的输入数据 |
| 标注演示视频 | `outputs/week1/annotated_demo.mp4` | 展示 ROI 和实时状态 |
| 逐帧统计 | `outputs/week1/frame_statistics.csv` | 后续分析和画图 |
| ROI 事件流 | `outputs/week1/roi_events.jsonl` | 事件驱动架构的第一版接口 |
| 运行摘要 | `outputs/week1/run_summary.json` | 记录输入、配置、规模和产物 |
| 抽样帧 | `outputs/week1/samples/` | 快速视觉检查 |

## 3. 系统工作流程

```text
MP4 文件或摄像头
        ↓
OpenCV VideoCapture 解码
        ↓
FramePacket(index, timestamp, BGR matrix)
        ↓
图像矩阵与 BGR / Gray / HSV 统计
        ↓
归一化 ROI → 像素坐标 → ROI 图像裁剪
        ↓
背景差分 → 变化像素比例 → 连续帧确认
        ↓
CLEAR / CALIBRATING / OCCUPIED 状态
        ↓
CSV + JSONL + JSON + JPG + 标注 MP4
```

这一结构把“图像输入”“视觉分析”“状态判断”和“结果存储”拆开。第二周更换或新增滤波算法时，不需要修改视频读取和输出层；第八周加入 YOLO、分割和跟踪时，也可以复用相同的帧和事件接口。

## 4. 关键组件如何实现

### 4.1 视频源组件

实现文件：`src/visiontrace/video_source.py`

组件使用 OpenCV `VideoCapture` 统一处理两种输入：

- 字符串或 `Path`：本地视频文件；
- 整数：摄像头索引，例如 `0`。

打开视频源后读取宽度、高度、FPS 和总帧数。每次迭代返回一个 `FramePacket`，包含：

```text
frame.index         帧编号
frame.timestamp_ms  时间戳
frame.image         H × W × 3 的 BGR NumPy 矩阵
```

组件使用上下文管理器保证视频句柄最终释放，并对无法打开的视频源、无效分辨率等情况抛出明确异常。

### 4.2 图像矩阵与颜色分析

实现文件：`src/visiontrace/frame_analysis.py`

OpenCV 读取的彩色帧是形状为 `H × W × 3` 的 NumPy 数组，通道顺序为 BGR。组件对每一帧记录：

- 高度、宽度、通道数和数据类型；
- B、G、R 三个通道的均值；
- 灰度图平均值，作为整体亮度近似；
- 灰度标准差，作为全局对比度近似；
- HSV 的平均色相和平均饱和度。

核心转换如下：

```python
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
```

这些指标不是最终质量特征，但为第二周的图像滤波、光照归一化和不同预处理方案对比建立了可量化基线。

### 4.3 ROI 配置与像素映射

实现文件：`src/visiontrace/config.py` 和 `src/visiontrace/frame_analysis.py`

ROI 在 YAML 中使用 0–1 的归一化坐标：

```yaml
roi:
  x: 0.34375
  y: 0.27778
  width: 0.31250
  height: 0.50000
```

运行时根据实际视频宽高转换为 `(x1, y1, x2, y2)`。这样更换 640×360、1280×720 或其他分辨率时，检测区域仍位于画面中的相同比例位置。配置加载时会验证 ROI 是否超出画面，防止错误配置静默产生空图像。

### 4.4 ROI 活动检测基线

实现文件：`src/visiontrace/frame_analysis.py`

当前版本的目标不是识别工件类别，而是验证“工件进入检测区域后能产生事件”的最小闭环。算法分四步：

1. **背景标定**：取前 10 帧 ROI 灰度图并计算均值，得到空产线背景；
2. **像素差分**：当前 ROI 与背景进行绝对值差分；
3. **变化比例**：统计差异超过阈值的像素占 ROI 的比例；
4. **状态确认**：连续 3 帧满足条件才进入 `OCCUPIED`，连续 3 帧恢复才回到 `CLEAR`。

变化比例可表示为：

```text
change_ratio = changed_pixels / total_roi_pixels
```

连续帧确认属于简单的时间迟滞机制，可以避免压缩噪声或单帧亮度变化产生虚假 ENTER/EXIT 事件。该组件是 Week 1 的可解释基线，后续会被目标检测和多目标跟踪替代，而不是被误认为最终的工业检测算法。

### 4.5 事件与审计输出

实现文件：`src/visiontrace/pipeline.py`

处理管线没有只生成一个“看起来有效”的视频，而是同时保存机器可读的结果：

- CSV：逐帧统计，可直接用于数据分析；
- JSONL：每行一个 ENTER/EXIT 事件，便于流式消费；
- JSON：一次运行的输入元数据、处理规模、事件和产物路径；
- JPG：固定间隔抽样，便于人工视觉检查；
- MP4：带 ROI、时间、状态和统计信息的完整结果视频。

这种设计为后续 `trace_id`、缺陷事件、规则版本和模型版本的审计链路预留了接口。

### 4.6 模拟生产线视频

实现文件：`src/visiontrace/demo_video.py`

视频由 NumPy 和 OpenCV 程序化生成，因此不依赖网络、摄像头或第三方数据。默认参数为：

- 分辨率：640×360；
- 帧率：15 FPS；
- 时长：15 秒；
- 总帧数：225；
- 工件数：3。

三个工件分别模拟正常标签、表面划痕和标签缺失。第一周管线只检测它们是否经过 ROI；这些外观差异将在后续颜色、边缘、检测和分割阶段使用。

## 5. 验证结果

### 5.1 实际运行结果

| 指标 | 结果 |
|---|---:|
| 输入分辨率 | 640 × 360 |
| 输入帧率 | 15 FPS |
| 处理帧数 | 225 |
| 处理时长 | 15 秒 |
| 模拟工件数 | 3 |
| ENTER 事件 | 3 |
| EXIT 事件 | 3 |
| 自动化测试 | 5 passed |

三个模拟工件均产生且只产生一次 ENTER 和一次 EXIT，基础事件链路与预期一致。

### 5.2 自动化测试覆盖

- 配置路径解析和 ROI 合法性；
- 已知 BGR 矩阵的统计结果；
- ROI 连续帧 ENTER/EXIT 状态转换；
- 生成视频的帧数、尺寸和可解码性；
- 从模拟视频到 CSV、JSONL、JSON 和标注视频的端到端链路。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 6. 如何运行

### 6.1 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 6.2 生成输入视频

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_demo.py
```

### 6.3 运行处理管线

```powershell
.\.venv\Scripts\python.exe .\scripts\run_week1.py
```

使用实际摄像头时可运行：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_week1.py --source 0
```

## 7. 当前限制

1. ROI 活动检测无法区分工件类别，也不能为多个工件分配独立 `trace_id`；
2. 背景标定要求最开始若干帧中 ROI 为空；
3. 大幅光照变化可能被误认为工件活动；
4. 当前没有 GUI 实时预览，只生成标注视频和数据文件；
5. 模拟工件外观简单，不能代表真实工业缺陷难度；
6. 当前指标只验证数据链路，不能用于宣称系统具备量产质检能力。

## 8. 与下一周的接口

Week 2 将在不破坏现有输入输出接口的前提下加入图像滤波模块：

- 高斯滤波和中值滤波；
- CLAHE 或其他对比度增强；
- BGR、HSV 和灰度变换；
- 原图与预处理图的并排对比；
- 亮度、对比度、噪声和运行时间指标；
- 验证预处理对 ROI 活动稳定性的影响。

后续模型应继续接收 `FramePacket`，并将结构化结果写入事件管线，而不是直接耦合到视频读取代码中。

## 9. 第一周结论

第一周已经完成一个可复现、可测试、可扩展的工业视觉基础链路。项目当前能够从视频输入中稳定读取图像矩阵、提取颜色信息、监控检测区域、生成状态事件，并同时输出人类可见证据与机器可读数据。

这意味着后续课程中学习到的滤波、边缘、特征、检测、分割、跟踪和 ViT 模型，都可以逐步接入现有系统，而不需要重新搭建底层工程。
