import cv2
import os

# Keep Matplotlib's writable cache alongside the lab's generated output.
os.environ.setdefault(
    "MPLCONFIGDIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", ".matplotlib")
)
import matplotlib

# This lab saves plots to disk and also runs without a desktop display.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def experiment_ratio_test(img_path_a, img_path_b, output_dir):
    """
    Lab Task 2: Implement Lowe's Ratio Test and observe how the threshold affects matches.
    """
    print(f"--- Running Task 2: Lowe's Ratio Test on {img_path_a} and {img_path_b} ---")
    img1 = cv2.imread(img_path_a, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(img_path_b, cv2.IMREAD_GRAYSCALE)
    if img1 is None or img2 is None:
        print("Error: Could not read input images for Task 2.")
        return

    # Initialize SIFT detector and find keypoints/descriptors
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)
    if des1 is None or des2 is None or len(des2) < 2:
        print("Not enough descriptors for two-neighbor matching in Task 2.")
        return
    os.makedirs(output_dir, exist_ok=True)
    print(f"SIFT keypoints: A={len(kp1)}, B={len(kp2)}; finding two nearest neighbors...")
    
    # Get 2 nearest neighbors for the ratio test
    bf = cv2.BFMatcher(cv2.NORM_L2)
    knn_matches = bf.knnMatch(des1, des2, k=2)
    
    thresholds = [0.60, 0.75, 0.90]
    match_counts = []
    
    for thresh in thresholds:
        good_matches = []
        for pair in knn_matches:
            if len(pair) < 2:
                continue
            m, n = pair
            # A distinctive match is much closer than its second neighbor.
            if m.distance < thresh * n.distance:
                good_matches.append(m)

        match_counts.append(len(good_matches))
        
        # Draw matches for visual inspection
        img_matches = cv2.drawMatches(img1, kp1, img2, kp2, good_matches, None, 
                                      flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        out_name = os.path.join(output_dir, f"task2_ratio_{thresh}.jpg")
        if not cv2.imwrite(out_name, img_matches):
            raise OSError(f"Could not save {out_name}")
        print(f"Threshold: {thresh} -> Good Matches: {len(good_matches)}")

    # Plot the threshold vs matches curve
    plt.figure()
    plt.plot(thresholds, match_counts, marker='o', linestyle='-')
    for threshold, count in zip(thresholds, match_counts):
        plt.annotate(str(count), (threshold, count), xytext=(0, 8),
                     textcoords="offset points", ha="center")
    plt.title("Ratio Threshold vs # Good Matches")
    plt.xlabel("Ratio Threshold")
    plt.ylabel("# Good Matches")
    plt.grid(True)
    plt.margins(y=0.15)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "task2_ratio_curve.png"))
    plt.close()

    return {
        "keypoints_a": len(kp1),
        "keypoints_b": len(kp2),
        "two_neighbor_pairs": sum(len(pair) == 2 for pair in knn_matches),
        "thresholds": thresholds,
        "match_counts": match_counts,
    }
