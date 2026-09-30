"""Reproduce the scanner outputs, intermediate figures and parameter comparison."""
import html
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

import cv2
import matplotlib
import numpy as np

BASE = Path(__file__).resolve().parents[1]
EVIDENCE = BASE / "output" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("scanner", BASE / "student_document_scanner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def save(name, img):
    if not cv2.imwrite(str(EVIDENCE / name), img):
        raise OSError(name)


run = subprocess.run(
    [sys.executable, "-B", "student_document_scanner.py"],
    cwd=BASE, capture_output=True, text=True, check=True,
)
transcript = "PS lab_week03> python student_document_scanner.py\n" + run.stdout
if run.stderr:
    transcript += "\nSTDERR\n" + run.stderr
transcript += f"\nProcess exit code: {run.returncode}\n"
(EVIDENCE / "terminal_output.txt").write_text(transcript, encoding="utf-8")

records = []
for case in (1, 2, 3):
    scanner = module.DocumentScanner()
    output = scanner.scan_document(BASE / "asset" / f"case{case}.png")
    original = scanner.original_image
    blur = scanner.preprocess_image(original)
    canny = cv2.Canny(blur, scanner.canny_low, scanner.canny_high)
    closed = scanner.detect_edges(blur)
    overlay = original.copy()
    points = scanner.document_points.astype(np.int32)
    cv2.polylines(overlay, [points], True, (30, 235, 60), 4)
    for i, point in enumerate(points):
        cv2.circle(overlay, tuple(point), 7, (30, 235, 60), -1)
        cv2.putText(overlay, str(i + 1), tuple(point + [10, 20]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(overlay, str(i + 1), tuple(point + [10, 20]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 235, 60), 2)
    save(f"case{case}_contour.png", overlay)
    save(f"case{case}_blur.png", blur)
    save(f"case{case}_canny.png", canny)
    save(f"case{case}_closed.png", closed)
    records.append({
        "case": case, "input_shape": list(original.shape),
        "output_shape": list(output.shape), "corners": points.tolist(),
        "contour_area": scanner.document_area,
        "contour_area_ratio": scanner.document_area / np.prod(original.shape[:2]),
        "canny_pixels": int(np.count_nonzero(canny)),
        "closed_pixels": int(np.count_nonzero(closed)),
    })

comparisons = []
for label, kernel, sigma, closing in [
    ("A", 5, 1.4, 1), ("B", 9, 2.0, 1),
    ("C", 9, 2.0, 3), ("D", 9, 2.0, 5), ("E", 15, 3.0, 5),
]:
    outcomes = []
    for case in (1, 2, 3):
        scanner = module.DocumentScanner(
            gaussian_kernel=kernel, sigma=sigma, closing_kernel=closing
        )
        try:
            scanner.scan_document(BASE / "asset" / f"case{case}.png")
            outcomes.append({"found": True, "area_ratio": scanner.document_area /
                             np.prod(scanner.original_image.shape[:2])})
        except ValueError as error:
            outcomes.append({"found": False, "error": str(error)})
    comparisons.append({"id": label, "gaussian_kernel": kernel, "sigma": sigma,
                        "closing_kernel": closing, "cases": outcomes})

metadata = {
    "python": platform.python_version(), "opencv": cv2.__version__,
    "numpy": np.__version__, "matplotlib": matplotlib.__version__,
    "cases": records, "experiments": comparisons, "exit_code": run.returncode,
}
(EVIDENCE / "metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

# A screenshot of this page preserves the actual captured stdout. It is labelled
# as a transcript viewer and is not represented as a native terminal window.
page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Week 03 execution transcript</title><style>
*{box-sizing:border-box}body{margin:0;background:#fff;color:#18232d;font-family:Arial,sans-serif}
main{width:1180px;padding:32px}h1{font-size:25px;margin:0 0 8px}
p{font-size:15px;color:#475569;margin:0 0 20px}
pre{background:#17212b;color:#edf3fa;padding:22px;font:17px/1.55 Consolas,monospace;
margin:0;white-space:pre;overflow:visible;border-radius:4px}
small{display:block;margin-top:14px;color:#475569;font-size:14px}
</style><main><h1>Week 03 execution transcript</h1>
<p>Captured directly from the scanner process, with all three cases and the exit status.</p>
<pre>''' + html.escape(transcript) + '''</pre>
<small>Browser-rendered transcript of the actual run; original text retained in terminal_output.txt.</small>
</main></html>'''
(EVIDENCE / "terminal.html").write_text(page, encoding="utf-8")
print(json.dumps(metadata, indent=2))
