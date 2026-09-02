# 实时滤镜首帧卡滞调试报告

## 1. 结论

- 事件编号：`RT-STREAM-001`
- 状态：第二轮代码修复和浏览器端到端回归已完成；等待手机真实摄像头验收。
- 公网状态：原 Gradio 隧道和本地 7860 服务均已关闭。
- 确定主因：Gradio 6.26 内置 `Image.stream()` 前端的采集定时器与 `streaming` 状态互锁。第一帧令事件进入 `streaming` 状态；组件又把该状态视为 `pending`，而定时器仅在 `pending == false` 时采集，因此第二帧不会产生。
- 次要问题：原程序没有限制手机采集尺寸，公网图片往返也可能产生严重延迟，但降低分辨率只能缓解带宽，不能解除上述首帧状态锁。第一次修复未解决根因。
- 非主因：OpenCV 滤镜。修复后的低延迟档中，即使输入为 1280×720，各滤镜“缩放 + 处理”的 P95 也只有约 0.7–1.3 ms。

最终方案不再使用有问题的内置 `Image.stream()` 状态机，而是采用浏览器自主管线：始终只允许一个请求在途，响应后才抓取摄像头的当前帧。网络变慢时会降低 FPS，而不会积压旧帧。默认目标为 320×240、8 FPS；若课程后续明确要求 20–30 FPS，应把传输适配器升级为 WebRTC，`FilterRegistry` 和 `RealtimeFrameProcessor` 可以原样复用。

## 2. 故障现象与数据路径

故障路径如下：

```text
手机摄像头或合成测试图案
    → 浏览器抓取“此刻最新帧”并编码 JPEG data URL
    → Gradio server_function（最多一个请求在途）
    → BrowserFrameGateway 校验、解码和尺寸保护
    → Python/OpenCV 滤镜
    → JPEG data URL 响应
    → 浏览器直接替换输出图像
```

左侧摄像头是浏览器在手机本地直接播放，因此可以保持流畅；右侧结果必须完成整个公网往返。两者看起来在同一个页面中，却不是同一条性能链路。

### 2.1 确定的帧切换错误

检查当前安装的 Gradio 6.26 前端 bundle 后，相关逻辑可还原为：

```javascript
pending = status === "pending" || status === "streaming";

setInterval(() => {
  if (video && !pending) captureAndDispatchFrame();
}, streamEvery);
```

首帧 dispatch 后，服务端流连接将状态设置为 `streaming`；于是 `pending` 一直为真，定时器不再调用 `captureAndDispatchFrame()`。这与手机端两次复测的“输出固定在第一帧、后续完全不变”一致。

最小配置实验同时确认：即使不显式给输入 `gr.Image` 设置 `streaming=True`，绑定 `.stream()` 事件后 Gradio 仍会把组件配置改为 streaming，因此简单删除该参数无法绕过问题。

### 2.2 次要性能问题

原代码还存在四个叠加问题：

1. 没有摄像头分辨率和帧率约束，部分手机可能选择 720p 或 1080p。
2. 固定 `stream_every=0.1`，即无论链路能否承受都尝试每秒发送 10 张图片。
3. 内置流事件依赖框架内部的 pending/streaming 状态，应用无法实现明确的“只保留最新帧”背压策略。
4. 监控只显示滤镜耗时和“理论 FPS”，没有显示服务端实际收到多少帧，因而帧切换停滞会被误判为算法问题。

Gradio 的[官方 Streaming Inputs 指南](https://gradio.app/guides/streaming-inputs)说明 `.stream()` 实际上是周期性拍照并发送到服务端，同时建议输出图像使用流式模式。Gradio 6 的[迁移指南](https://www.gradio.app/guides/gradio-6-migration-guide)提供了 `WebcamOptions.constraints`，可用于约束移动摄像头的分辨率、帧率和朝向。

## 3. 定量分析

### 3.1 传输负载

使用随机 RGB 图像和默认 JPEG 编码测得如下单帧大小。随机图像接近不利压缩情形，真实相机画面通常更小，但数量级仍可用于比较。

| 尺寸 | 单帧约大小 | 8 FPS 单方向带宽 |
|---|---:|---:|
| 320×240 | 46,791 B | 2.99 Mbps |
| 640×480 | 185,201 B | 11.85 Mbps |
| 1920×1080 | 1,248,180 B | 79.88 Mbps |

原配置 640×480、10 FPS 时，仅一个方向理论上约 14.82 Mbps；上传和下载合计约 29.64 Mbps，还未计入 HTTP、JSON/Base64、认证和公网中继开销。若手机实际选择 1080p，负载会再上升约 6.7 倍。

默认低延迟档将有效载荷限制到 320×240、8 FPS。与 640×480、8 FPS 相比，单方向图片数据约减少 74.7%；同时不再允许浏览器按高帧率产生无法及时消费的帧。

### 3.2 计算负载

测试输入为 1280×720；每次调用包含缩小到 320×180 和滤镜处理，共执行 100 次。结果如下：

| 滤镜 | P50 | P95 | 输出尺寸 |
|---|---:|---:|---:|
| Original | 0.607 ms | 0.747 ms | 320×180 |
| Vintage warm | 1.102 ms | 1.232 ms | 320×180 |
| Cool tone | 1.102 ms | 1.245 ms | 320×180 |
| High contrast | 0.998 ms | 1.264 ms | 320×180 |
| Faded | 0.951 ms | 1.236 ms | 320×180 |
| Grayscale | 0.611 ms | 0.685 ms | 320×180 |

8 FPS 的单帧周期是 125 ms，因此 P95 计算占周期约 0.5%–1.1%。这证明本次卡滞的主要矛盾是传输，而不是滤镜算力。

## 4. 修复内容与代码映射

### 4.1 可配置的流性能档

文件：`realtime/profiles.py`

- `StreamProfile`：统一管理最大宽高、目标 FPS、流生命周期、并发槽和队列容量。
- `webcam_constraints()`：生成浏览器摄像头约束，避免手机默认采集过大画面。
- `resize_to_fit()`：当浏览器忽略约束时在服务端再次等比例缩小；不会放大小图，也不会扭曲纵横比。
- `STREAM_PROFILES`：提供 `low-latency`、`balanced`、`quality` 三个档位，便于后续新增设备或网络策略。

| 档位 | 最大尺寸 | 目标帧率 | 适用场景 |
|---|---:|---:|---|
| `low-latency`（默认） | 320×240 | 8 FPS | 手机公网演示，优先响应 |
| `balanced` | 480×360 | 6 FPS | 网络较好，需要更多细节 |
| `quality` | 640×480 | 4 FPS | 静态构图、优先画质 |

### 4.2 浏览器最新帧组件

文件：`realtime/webcam_component.py`

- 使用 Gradio 6 官方 `gr.HTML(..., server_functions=[...])` 能力构建摄像头 UI，不再调用内置 `Image.stream()`。
- `requestAnimationFrame` 负责调度，但 `inFlight` 明确保证同一时刻最多存在一个服务端请求。
- 请求完成后才捕获摄像头当前画面；没有历史帧队列，不会追赶已经过时的帧。
- 摄像头分辨率、帧率和 JPEG 质量都在浏览器层控制。
- 滤镜下拉框每一帧读取当前值，切换滤镜不需要重启流。
- 提供 `Synthetic test pattern`，没有摄像头时也能测试连续帧编号、运动块和完整网络路径。
- 页面卸载或点击 Stop 时主动停止摄像头轨道、动画循环和后续输出更新。

### 4.3 浏览器帧网关

文件：`realtime/frame_gateway.py`

- `BrowserFrameGateway.process_frame()`：浏览器唯一后端入口；不保存上一帧。
- 只接受 JPEG、PNG 或 WebP data URL，并限制编码前后的载荷大小。
- 解码后调用尺寸保护和现有 `RealtimeFrameProcessor`，再以质量 70 的 JPEG 返回。
- 使用结构化结果返回帧序号、实际 FPS、完整服务端耗时、滤镜耗时和输出字节数。
- `server_functions` 多参数会由 Gradio 包成一个数组；普通函数适配器负责校验并解包，避免参数错位。

### 4.4 可观测性

文件：`realtime/telemetry.py`

- `FrameCadenceTracker`：线程安全地记录进入处理函数的帧序号。
- 使用滚动时间窗口计算服务端真实帧到达率，不保存图像，不形成新的帧缓存。
- 页面状态新增 `Frame #N | Received X FPS | Server Y ms | Filter Z ms`。序号持续增长表示传输正常；序号停止表示链路停滞；序号增长但 FPS 低且计算耗时很短，表示网络仍是瓶颈。

### 4.5 应用装配与保留的算法边界

文件：`realtime/webcam_app.py`、`realtime/processor.py` 与 `realtime/registry.py`

这两个模块没有因为 UI 修复而改变：

- `FilterRegistry` 仍负责发现和管理滤镜。
- `RealtimeFrameProcessor` 仍负责 RGB/BGR 适配、滤镜调用、输入输出契约检查和计算耗时。
- `create_app(..., profile=...)` 只负责装配性能档、网关和浏览器组件。
- `--stream-profile` 继续提供低延迟、均衡和画质三档启动方式。
- 将来换成 WebRTC、FastAPI 或原生移动端时，只需替换传输适配层，不需要重写滤镜核心。

## 5. 验证结果

### 自动测试

```text
项目完整回归：40 passed in 2.63s
Python 字节码编译：通过
命令行启动参数检查：通过
```

新增测试覆盖：

- 三种性能档参数和非法配置拒绝。
- 横屏、竖屏等比例缩小与小图零拷贝。
- 连续两张内容不同的 JPEG data URL 产生不同输出，帧号从 1 增长到 2。
- 非法 data URL、超限载荷和未知滤镜返回稳定错误，不中断循环。
- 帧序号和滚动 FPS 计算。
- Gradio 页面中不再存在内置 `stream` 事件依赖，并正确注册自定义 `process_frame` 服务函数。
- JavaScript 多参数数组适配器的解包与拒绝逻辑。

### 本地服务冒烟测试

- 首页：HTTP 200。
- 测试源：浏览器内 `Synthetic test pattern`，使用与真实摄像头相同的编码、请求、Python 处理和输出替换路径。
- 连续性：1.2 秒内 `Frame #322 → #332`；切换 Cool Tone 后继续到 `#342`。
- 实际到达率：7.9–8.0 FPS。
- 滤镜切换：Original → Cool Tone 后不中断，滤镜耗时从约 0.0 ms 变为 0.8 ms。
- 视觉检查：输入和输出显示相同的动态帧编号，Cool Tone 效果可见。
- 测试结束后已停止 7860 服务。

开发电脑没有摄像头，因此无法本地验证 `getUserMedia` 的真实硬件轨道；但合成源已覆盖浏览器调度、JPEG 编解码、Gradio server function、Python 滤镜和 DOM 输出替换。下一次公网测试只剩手机摄像头与隧道链路需要验收。

## 6. 手机端验收清单

重新获得明确公网传输授权后，可执行：

```powershell
.venv\Scripts\python.exe -m lab_week01.realtime.webcam_app --access mobile --stream-profile low-latency
```

手机端检查：

1. 登录后允许摄像头，开始流式采集。
2. 观察 `Frame #N` 至少连续增长 30 次，而不是停在 `#1`。
3. 移动物体或转动手机，右侧画面应持续更新；允许相对左侧原始预览存在公网往返延迟。
4. 切换全部滤镜，下一批返回帧应使用新滤镜。
5. 若 `X FPS` 低于 3，优先检查手机上行网络或 Gradio 中继质量；不要先优化 OpenCV 滤镜。

## 7. 已知限制与下一阶段建议

当前自定义管线仍是“最新图片快照 + 服务端处理”，不是连续视频编解码协议。它绕过了 Gradio 6.26 的首帧状态锁，并通过单请求背压保证低延迟；8 FPS 是当前公网演示的可解释目标，不应把页面左侧本地摄像头的 30 FPS 当作右侧服务端结果的承诺。

下一阶段若需要亮眼的 20–30 FPS Demo，建议新增 `WebRTCTransport`：

```text
WebRTC 视频轨（自带拥塞控制、丢弃旧帧）
    → Transport Adapter
    → RealtimeFrameProcessor
    → WebRTC 返回轨
```

验收指标应改为端到端延迟、P95 帧间隔、丢帧率和断线恢复时间，而不是只看滤镜函数的理论 FPS。
