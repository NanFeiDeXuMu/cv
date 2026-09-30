"""Week 03 document scanner. Author: Liu Yixuan.

Run: python student_document_scanner.py [--show-intermediate]
"""
import argparse
from pathlib import Path
import cv2
import numpy as np


class DocumentScanner:
    """Locate the largest document-like quadrilateral and rectify its perspective."""

    def __init__(self, gaussian_kernel=9, sigma=2.0, canny_low=50,
                 canny_high=150, min_area_ratio=0.05,
                 epsilon_ratio=0.02, closing_kernel=5):
        self.original_image = None
        self.processed_image = None
        self.document_points = None
        self.document_area = None
        self.gaussian_kernel = gaussian_kernel
        self.sigma = sigma
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.min_area_ratio = min_area_ratio
        self.epsilon_ratio = epsilon_ratio
        self.closing_kernel = closing_kernel

    def load_image(self, image_path):
        """Read a BGR image and reject missing or undecodable inputs."""
        self.original_image = cv2.imread(str(image_path))
        if self.original_image is None:
            raise ValueError(f"Unable to load image: {image_path}")
        return self.original_image

    def preprocess_image(self, image):
        """Task 1: grayscale conversion and Gaussian denoising."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Sigma=2 with a 9x9 kernel suppresses print/wood texture while retaining
        # the document boundary. Excessive smoothing would erase weak edges.
        return cv2.GaussianBlur(
            gray, (self.gaussian_kernel, self.gaussian_kernel), self.sigma
        )

    def detect_edges(self, image):
        """Task 2: Canny extraction followed by small-gap repair."""
        # Hysteresis retains weak edges connected to strong edges (50/150).
        edges = cv2.Canny(image, self.canny_low, self.canny_high)
        # Case2's printed border has short breaks. Closing connects them;
        # a large kernel can incorrectly merge the border with nearby hands.
        if self.closing_kernel > 1:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (self.closing_kernel, self.closing_kernel)
            )
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        return edges

    def find_document_contour(self, edges):
        """Task 3: select the largest sufficiently large convex four-sided contour."""
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        document_contour, max_area = None, 0
        # Relative area filtering accommodates the different input resolutions.
        min_area = edges.shape[0] * edges.shape[1] * self.min_area_ratio
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, self.epsilon_ratio * perimeter, True)
            if len(approx) == 4 and cv2.isContourConvex(approx) and area > max_area:
                document_contour, max_area = approx, area
        if document_contour is None:
            raise ValueError("Document contour not found; adjust parameters or check image quality")
        self.document_area = max_area
        return document_contour.reshape(4, 2)

    def order_points(self, pts):
        """Order corners: top-left, top-right, bottom-right, bottom-left."""
        pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
        sums = pts.sum(axis=1)
        differences = np.diff(pts, axis=1)  # y-x, not x-y
        rect = pts[[np.argmin(sums), np.argmin(differences),
                    np.argmax(sums), np.argmax(differences)]]
        # Ties (e.g. a diamond) must not select the same vertex twice.
        if len(np.unique(rect, axis=0)) != 4:
            center = pts.mean(axis=0)
            angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
            rect = pts[np.argsort(angles)]
            rect = np.roll(rect, -np.argmin(rect.sum(axis=1)), axis=0)
        if len(np.unique(rect, axis=0)) != 4 or not cv2.isContourConvex(rect):
            raise ValueError("Document vertices must form a non-degenerate convex quadrilateral")
        return rect

    def perspective_correction(self, image, pts):
        """Task 4: map the detected quadrilateral to an axis-aligned rectangle."""
        ordered_pts = self.order_points(pts)
        tl, tr, br, bl = ordered_pts
        # Keep the lab's longer-opposing-edge sizing rule. It estimates output
        # resolution, not the unknown physical aspect ratio of the document.
        width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        if min(width, height) < 2:
            raise ValueError("Document dimensions are too small for perspective correction")
        dst = np.array([[0, 0], [width - 1, 0],
                        [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
        # Both arrays are float32 and use the same TL, TR, BR, BL ordering.
        matrix = cv2.getPerspectiveTransform(ordered_pts, dst)
        return cv2.warpPerspective(image, matrix, (width, height))

    def scan_document(self, image_path, show_intermediate=False):
        """Run the complete pipeline and return the rectified BGR image."""
        self.processed_image = self.document_points = self.document_area = None
        original = self.load_image(image_path)
        preprocessed = self.preprocess_image(original)
        edges = self.detect_edges(preprocessed)
        points = self.find_document_contour(edges)
        result = self.perspective_correction(original, points)
        self.document_points = self.order_points(points)
        # Store before displaying; the starter displayed an uninitialized value.
        self.processed_image = result
        if show_intermediate:
            self.show_intermediate_results(original, preprocessed, edges, points)
        return result

    def show_intermediate_results(self, original, preprocessed, edges, document_pts):
        """Display the input, preprocessing, edges, contour and rectified result."""
        import matplotlib.pyplot as plt  # Optional for batch-only usage.
        contour_image = original.copy()
        cv2.drawContours(contour_image, [document_pts.astype(np.int32)], -1, (0, 255, 0), 3)
        panels = [(original, 'Original Image'),
                  (preprocessed, 'Grayscale + Gaussian Blur'),
                  (edges, 'Canny Edges + Morphological Closing'),
                  (contour_image, 'Detected Document Contour'),
                  (self.processed_image, 'Perspective Correction Result')]
        figure, axes = plt.subplots(2, 3, figsize=(15, 10))
        for axis, (panel, title) in zip(axes.flat, panels):
            display = cv2.cvtColor(panel, cv2.COLOR_BGR2RGB) if panel.ndim == 3 else panel
            axis.imshow(display, cmap='gray')
            axis.set_title(title)
            axis.axis('off')
        axes.flat[-1].axis('off')
        figure.tight_layout()
        plt.show()
        plt.close(figure)


def main():
    """Process all supplied cases and return a meaningful exit status."""
    parser = argparse.ArgumentParser(description="Scan the three Week 03 test images.")
    parser.add_argument('--show-intermediate', action='store_true',
                        help="Display the processing stages with Matplotlib")
    args = parser.parse_args()
    base_dir = Path(__file__).resolve().parent
    (base_dir / 'output').mkdir(parents=True, exist_ok=True)
    test_cases = [f'asset/case{i}.png' for i in range(1, 4)]
    successes = 0
    print("Document Scanner Test")
    print("=" * 40)
    print("Gaussian: 9x9, sigma=2.0 | Canny: 50/150")
    print("Closing: 5x5 | Min area: 5% | Epsilon: 2%")
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case}")
        try:
            scanner = DocumentScanner()
            result = scanner.scan_document(base_dir / test_case, args.show_intermediate)
            output_path = f'output/result_{i}.png'
            if not cv2.imwrite(str(base_dir / output_path), result):
                raise OSError(f"Unable to save result: {output_path}")
            successes += 1
            print(f"[OK] Processing successful, result saved to: {output_path}")
            print(f"  Output dimensions: {result.shape}")
            print(f"  Corners (TL/TR/BR/BL): {scanner.document_points.astype(int).tolist()}")
        except Exception as error:
            print(f"[FAIL] Processing failed: {error}")
            import traceback
            traceback.print_exc()
    print("\n" + "=" * 40)
    print(f"Completed: {successes}/{len(test_cases)} test cases passed.")
    return 0 if successes == len(test_cases) else 1


if __name__ == '__main__':
    raise SystemExit(main())
