"""Build the six-page submission PDF from verified local execution evidence."""
import json
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

BASE = Path(__file__).resolve().parents[1]
EVIDENCE = BASE / "output" / "evidence"
TARGET = BASE / "Lab3_Submission" / "Lab3_Report_LiuYixuan.pdf"
TARGET.parent.mkdir(parents=True, exist_ok=True)
METRICS = json.loads((EVIDENCE / "metrics.json").read_text(encoding="utf-8"))
W, H = A4
M = 46
BODY = W - 2 * M
pdf = canvas.Canvas(str(TARGET), pagesize=A4)
pdf.setTitle("Document Scanner Implementation - Week 03 Lab Report")
pdf.setAuthor("Liu Yixuan")
body = ParagraphStyle("Body", fontName="Helvetica", fontSize=10.2, leading=14.3,
                      textColor=colors.black, alignment=TA_LEFT)
small = ParagraphStyle("Small", parent=body, fontSize=8.7, leading=11.5)
cell = ParagraphStyle("Cell", parent=body, fontSize=9.1, leading=12.4)


def para(text, y, style=body, x=M, width=BODY, after=9):
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, H)
    if y - height < 48:
        raise ValueError(f"Page overflow: {text[:80]}")
    paragraph.drawOn(pdf, x, y - height)
    return y - height - after


def heading(text, y, size=14):
    pdf.setFont("Helvetica-Bold", size)
    pdf.setFillColor(colors.black)
    pdf.drawString(M, y, text)
    return y - 22


def start(page, title):
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(colors.HexColor("#4b5563"))
    pdf.drawString(M, H - 28, "WEEK 03 LABORATORY REPORT")
    pdf.drawRightString(W - M, H - 28, "Liu Yixuan")
    pdf.drawString(M, 27, "Document Scanner Implementation")
    pdf.drawRightString(W - M, 27, f"{page} / 6")
    return heading(title, H - 68, 20)


def table(rows, widths, y):
    data = [[Paragraph(str(value), cell) for value in row] for row in rows]
    obj = Table(data, colWidths=widths)
    obj.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf2")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d9d9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    _, height = obj.wrap(BODY, H)
    if y - height < 48:
        raise ValueError("Table overflow")
    obj.drawOn(pdf, M, y - height)
    return y - height - 13


def picture(path, x, top, maxw, maxh):
    with PILImage.open(path) as image:
        iw, ih = image.size
    ratio = min(maxw / iw, maxh / ih)
    width, height = iw * ratio, ih * ratio
    pdf.drawImage(str(path), x + (maxw - width) / 2, top - height,
                  width=width, height=height)
    return top - height


y = start(1, "Document Scanner Implementation")
y = para("Week 03 laboratory report<br/><b>Liu Yixuan</b> | 23 September 2026", y - 4)
y = heading("Introduction", y - 10)
y = para(
    "The objective is to locate a document in a photograph and transform its four corners "
    "into an axis-aligned rectangle. The four required stages are implemented using OpenCV: "
    "Gaussian denoising, Canny edge detection, quadrilateral selection and perspective warping. "
    "One shared parameter set processes all three supplied images successfully. The second "
    "image is rectified using its printed inner border; its full wooden outline is not recovered.", y)
y = heading("Implementation", y - 8)
for text in [
    "<b>1 Preprocessing.</b> Convert the original BGR image to grayscale, then call "
    "<font name='Courier'>cv2.GaussianBlur</font>. The original color image is retained for "
    "the final warp, so smoothing affects detection without directly blurring the saved document.",
    "<b>2 Edge detection.</b> Apply <font name='Courier'>cv2.Canny</font>, then one "
    "5 x 5 morphological closing operation. The added closing step repairs short interruptions "
    "in a rectangular border before contour extraction.",
    "<b>3 Contour filtering.</b> Use external contours with chain approximation. Reject "
    "contours smaller than 5% of the image, compute each perimeter, and approximate polygons "
    "with a tolerance of 2% of that perimeter. Keep convex quadrilaterals and select the "
    "largest by original contour area. Return the four vertices as a 4 x 2 array.",
    "<b>4 Perspective correction.</b> Order corners as top-left, top-right, bottom-right and "
    "bottom-left. Compute the output width and height from the longer opposing edges, then "
    "call <font name='Courier'>cv2.getPerspectiveTransform</font> and "
    "<font name='Courier'>cv2.warpPerspective</font> using matching float32 point arrays.",
]:
    y = para(text, y)
y = heading("Final parameters", y - 8)
y = table([
    ["<b>Stage</b>", "<b>Setting used for every image</b>"],
    ["Gaussian smoothing", "9 x 9 kernel; sigma = 2.0"],
    ["Canny and gap repair", "Low/high thresholds = 50/150; one 5 x 5 rectangular closing"],
    ["Contour selection", "Area at least 0.05 x image area; epsilon = 0.02 x perimeter; convex; four vertices"],
    ["Perspective warp", "Four point homography; OpenCV default linear interpolation"],
], [145, BODY - 145], y)
pdf.showPage()

y = start(2, "Parameter Evaluation and Validation")
y = para("The following runs use the supplied images at their original resolutions. Canny "
         "thresholds (50/150), minimum area (5%) and approximation tolerance (2%) are fixed. "
         "A pass means a valid quadrilateral was found and warped; it is not a ground-truth "
         "accuracy measurement.", y)
rows = [["<b>Run</b>", "<b>Gaussian</b>", "<b>Closing</b>", "<b>Case 1</b>", "<b>Case 2</b>", "<b>Case 3</b>"]]
for experiment in METRICS["experiments"]:
    k = experiment["gaussian_kernel"]
    close = experiment["closing_kernel"]
    rows.append([experiment["id"] + (" selected" if experiment["id"] == "D" else ""),
                 f"{k} x {k}<br/>sigma {experiment['sigma']}",
                 "None" if close == 1 else f"{close} x {close}",
                 *["Pass" if case["found"] else "Fail" for case in experiment["cases"]]])
y = table(rows, [74, 103, 80, 82, 82, BODY - 421], y)
y = para("<b>Observed tradeoff.</b> Moderate smoothing recovers Case 1, but Case 2 also "
         "needs gap repair. With 3 x 3 closing its contour covers 39.46% of the image; "
         "5 x 5 closing selects the outside edge of the printed frame and covers 40.35%. "
         "The stronger 15 x 15, sigma 3.0 blur again loses a valid Case 2 quadrilateral. "
         "Run D therefore provides the preferred result across these three images.", y)
y = para("<b>Threshold reasoning.</b> Canny rejects weak responses and retains intermediate "
         "responses connected to strong edges. Lower thresholds admit noise; higher thresholds "
         "can break boundaries. The 1:3 ratio is a starting point. A small polygon tolerance "
         "retains extra vertices; a large tolerance can misclassify unrelated shapes as quads.", y)
y = heading("Verification and corrections", y - 6)
y = para("All <b>10 checks passed</b>: three supplied-image PNG round trips; a colored-corner "
         "warp under all 24 vertex permutations; diamond ordering; degenerate-point rejection; "
         "blank-image failure and state reset; debug display; execution from another working "
         "directory; and unsuccessful-save exit status.", y)
y = para("The result is now assigned before debug display. Paths are relative to the script, "
         "the output directory is created automatically, and failed saves produce a nonzero "
         "exit status. Detection uses no case-specific coordinates or parameter overrides.", y)
y = heading("Limitations", y - 6)
y = para("The largest-quadrilateral rule can select an internal frame or a background object. "
         "Case 2 demonstrates this explicitly. Fixed thresholds and a 5% minimum area "
         "may fail for dim scenes, small documents or broken boundaries. The longer-edge "
         "sizing rule removes perspective skew but does not recover physical paper "
         "proportions, especially for Case 1. No OCR, lighting correction, lens calibration "
         "or curved-page flattening is performed.", y)
pdf.showPage()

titles = ["Case 1 Desktop Document", "Case 2 Wooden Message Board", "Case 3 Book Back Cover"]
analyses = [
    "The selected contour follows the paper boundary and removes the surrounding desk, "
    "pen and other objects. The text and signature are preserved, and the page edges are "
    "aligned with the output axes. A narrow dark strip remains near the top edge. The "
    "output is nearly square because its dimensions follow projected edge lengths; "
    "the physical page aspect ratio cannot be established from this rule.",
    "Hands, wood texture and background structures make the outside silhouette difficult "
    "to close. The selected quadrilateral follows the printed inner frame. The message "
    "and decorative motifs remain visible after correction, while the outer wooden "
    "margin and the small website label below the frame are excluded. This is a useful "
    "content crop, but it is not a complete recovery of the board's physical boundary.",
    "The selected contour tracks the book's outer cover rather than the text blocks or "
    "barcode. The black background is largely removed, and the cover becomes a "
    "rectangular frontal view. Slight edge curvature and a narrow background sliver "
    "remain because a single homography models a plane and four straight edges.",
]
for index, record in enumerate(METRICS["cases"]):
    case = index + 1
    y = start(case + 2, titles[index])
    ih, iw, _ = record["input_shape"]
    oh, ow, _ = record["output_shape"]
    y = para(f"<b>Input</b> asset/case{case}.png ({iw} x {ih} pixels) &nbsp; "
             f"<b>Output</b> output/result_{case}.png ({ow} x {oh} pixels)", y, small)
    leftw, rightw = 225, BODY - 243
    rightx = M + 243
    para("<b>Original with detected contour</b>", y, small, M, leftw)
    para("<b>Saved rectified output</b>", y, small, rightx, rightw)
    top = y - 21
    bottom_left = picture(EVIDENCE / f"case{case}_contour.png", M, top, leftw, 300)
    bottom_right = picture(BASE / "output" / f"result_{case}.png", rightx, top, rightw, 450)
    edge_top = bottom_left - 30
    for offset, suffix, label in [(0, "canny", "Canny edges"), (118, "closed", "After closing")]:
        para(label, edge_top, small, M + offset, 107)
        bottom_edge = picture(EVIDENCE / f"case{case}_{suffix}.png", M + offset,
                              edge_top - 17, 107, 140)
    y = min(bottom_edge, bottom_right) - 22
    y = para(f"<b>Figure {case}.</b> Green markers 1-4 indicate the ordered corners "
             "(top-left, top-right, bottom-right, bottom-left). The right panel displays "
             "the saved PNG without additional image enhancement.", y, small)
    y = heading("Result analysis", y - 9, 13)
    y = para(analyses[index], y)
    corners = "; ".join(f"({x}, {v})" for x, v in record["corners"])
    y = para(f"<b>Detected corners</b> {corners}<br/>"
             f"<b>Contour area</b> {record['contour_area']:,.1f} pixels squared "
             f"({record['contour_area_ratio'] * 100:.2f}% of the input image).", y, small)
    pdf.showPage()

y = start(6, "Execution Evidence and Reproduction")
y = para("The program completed all three test cases with exit code 0. The full standard "
         "output, including saved filenames, dimensions and ordered corners, is reproduced "
         "in the screenshot below. This is a browser-rendered transcript of the actual "
         "process output, rather than a native terminal-window capture.", y)
y = picture(EVIDENCE / "terminal_capture.png", M - 6, y, BODY + 12, 425) - 15
y = heading("Reproducing the run", y, 13)
y = para("Place the submitted script beside the course-provided <font name='Courier'>asset/</font> "
         "directory. Install OpenCV, NumPy and Matplotlib, then run "
         "<font name='Courier'>python student_document_scanner.py</font>. The script creates "
         "<font name='Courier'>output/</font> automatically. Use "
         "<font name='Courier'>--show-intermediate</font> to display the five processing stages.", y)
y = para(f"<b>Verified environment</b> Python {METRICS['python']}; OpenCV {METRICS['opencv']}; "
         f"NumPy {METRICS['numpy']}; Matplotlib {METRICS['matplotlib']}. "
         "The environment uses opencv-python-headless; visualization is provided by Matplotlib.", y, small)
y = heading("Conclusion", y - 3, 13)
y = para("The completed pipeline produces three readable, rectangular document views. "
         "The experiments show that edge continuity and contour selection govern success: "
         "moderate denoising and a small closing operation allow one parameter set to "
         "handle the supplied scenes. Recovering the complete board outline and true "
         "document proportions would require additional geometric or segmentation cues.", y)
y = para("<b>Course sources</b> LAB_README.md; Submission.md; edge_detection_tutorial.ipynb. "
         "Experiments and figures were generated from the supplied assets and the completed script.", y, small)
pdf.save()
print(TARGET)
