# Week 03 完成记录

署名：Liu Yixuan。

## 运行

从仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe .\lab_week03\student_document_scanner.py
.\.venv\Scripts\python.exe .\lab_week03\student_document_scanner.py --show-intermediate
```

如使用新环境，安装 `lab_week03/requirements.txt` 中的依赖。批处理只需要
OpenCV 和 NumPy，Matplotlib 用于中间结果显示。输入及输出路径相对于脚本定位。

## 实现和结果

- 高斯模糊：9×9，sigma=2.0。
- Canny：50/150；随后进行一次 5×5 矩形闭运算，连接短小边缘缺口。
- 轮廓：面积至少为图像的 5%，近似精度为周长的 2%，选取最大凸四边形。
- 透视矫正：四角统一排序，以较长的对边确定输出宽高。
- 修复调试显示的赋值顺序；创建输出目录；检查保存结果和退出状态。

| 输入 | 输出 | 尺寸（宽×高） |
| --- | --- | --- |
| asset/case1.png | output/result_1.png | 578×572 |
| asset/case2.png | output/result_2.png | 772×1247 |
| asset/case3.png | output/result_3.png | 698×989 |

第二张图选取的是木板的印刷内边框，外侧木边及底部网站标签不在输出中。
第一张图接近正方形，原因是保留了课程骨架的对边长度估计方法；该方法不恢复
真实纸张比例。报告明确讨论了这些限制，没有把成功运行等同于完整外轮廓定位。

## 检查

`test_document_scanner.py` 的 10 项检查全部通过。包括三张素材、PNG 无损保存、
24 种角点排列下的彩色角标矫正、菱形排序、退化点拒绝、空白图失败与状态清理、
调试显示、其他工作目录启动和保存失败退出状态。

```powershell
$env:MPLCONFIGDIR = "$PWD\tmp\lab03_mpl"
.\.venv\Scripts\python.exe -m pytest .\lab_week03\test_document_scanner.py -q --basetemp .\tmp\lab03_test_run -o cache_dir=tmp/lab03_pytest_cache
```

`--basetemp` 目录由 pytest 管理，应使用专用临时目录，不要指定已有重要文件的目录。

## 提交内容

`Lab3_Submission_LiuYixuan.zip` 内严格包含：

```text
Lab3_Submission/
  student_document_scanner.py
  Lab3_Report_LiuYixuan.pdf
```

课程要求只提交代码和报告，因此 ZIP 不重复包含课程素材。重新运行时将代码放回
课程素材目录旁。报告共六页，包含参数实验、三组原图与结果、边缘图、运行记录及限制。
运行图是实际标准输出的浏览器排版截图，报告中已明确说明其形式；原始文本保存在
`output/evidence/terminal_output.txt`。此提交包尚未上传 Canvas。

`output/evidence/metrics.json` 保存参数对比和测量数据；`tools/collect_evidence.py`
可重新生成这些数据；`tools/build_report.py` 使用 ReportLab/Pillow 生成报告。
课堂 Notebook 仍是原始参考材料，缺少硬币输入素材不影响本作业。
