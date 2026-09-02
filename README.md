# VisionTrace

VisionTrace 是一个面向课程项目的工业视觉质检与生产追溯原型。第一周版本聚焦可复现的视频输入、图像矩阵分析、颜色空间统计和检测区域活动监控，为后续工件检测、缺陷分割、跨帧跟踪和质量追溯建立稳定的数据链路。

完整产品定义见 [PRD.md](PRD.md)，第一周交付说明见 [WEEK1_SUMMARY.md](WEEK1_SUMMARY.md)。课程原始滤镜实验及其实时扩展位于 [lab_week01](lab_week01/README.md)，实时帧停滞问题的定位过程见 [调试报告](lab_week01/DEBUG_REPORT.md)。

## 仓库结构

```text
cv/
├── src/visiontrace/       # 工业视觉数据链路核心包
├── configs/               # 可版本化的运行配置
├── scripts/               # Demo 生成与 Week 1 管线入口
├── tests/                 # VisionTrace 单元与集成测试
├── lab_week01/            # 图像滤镜实验与手机实时预览扩展
│   ├── realtime/          # 可替换的实时传输、处理与访问层
│   └── tests/             # 实时组件测试
├── assets/                # 可复现输入资产（生成视频不入库）
├── data/                  # 原始及处理数据占位目录
└── outputs/               # 运行结果目录（生成内容不入库）
```

本地虚拟环境、缓存、Gradio 证书、生成视频和处理结果均由 `.gitignore` 排除，仓库只保存重建 Demo 所需的代码、配置与小型示例输入。

## Week 1 已实现

- 摄像头索引或视频文件的统一读取接口；
- 视频分辨率、帧率、总帧数和时间戳读取；
- BGR、灰度和 HSV 图像矩阵统计；
- 归一化 ROI 配置与像素坐标转换；
- 基于背景差分和连续帧确认的 ROI 占用状态；
- 可重复生成的模拟生产线视频；
- 标注视频、抽样帧、逐帧 CSV、事件 JSONL 和运行摘要；
- 单元测试和端到端集成测试。

## 环境准备

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 运行

生成模拟生产线视频：

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_demo.py
```

运行第一周处理管线：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_week1.py
```

处理指定视频：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_week1.py --source .\path\to\video.mp4
```

连接摄像头 0：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_week1.py --source 0
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 第一周输出

运行结果默认写入 `outputs/week1/`：

- `annotated_demo.mp4`：带 ROI、状态和图像统计的演示视频；
- `frame_statistics.csv`：逐帧矩阵和颜色统计；
- `roi_events.jsonl`：ROI 的 ENTER/EXIT 事件流；
- `run_summary.json`：视频元数据、处理规模和输出索引；
- `samples/`：用于快速检查的抽样帧。

第一周的 ROI 活动检测只用于验证数据链路，不等同于最终的工件识别或 `trace_id` 跟踪。后续版本会用目标检测和多目标跟踪替换该基线。
