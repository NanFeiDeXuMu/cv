import cv2
import numpy as np
import os

def align_and_stitch(img_path_a, img_path_b, output_dir):
    """
    Lab Task 3: Full pipeline from SIFT matching to RANSAC homography and image warping.
    """
    print(f"--- Running Task 3: Alignment & Stitching on {img_path_a} and {img_path_b} ---")
    img1 = cv2.imread(img_path_a)
    img2 = cv2.imread(img_path_b)
    
    if img1 is None or img2 is None:
        print("Error: Could not read input images for Task 3.")
        return

    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(gray1, None)
    kp2, des2 = sift.detectAndCompute(gray2, None)
    if des1 is None or des2 is None or len(des2) < 2:
        print("Not enough descriptors for two-neighbor matching in Task 3.")
        return
    print(f"SIFT keypoints: A={len(kp1)}, B={len(kp2)}; finding two nearest neighbors...")
    
    bf = cv2.BFMatcher(cv2.NORM_L2)
    knn_matches = bf.knnMatch(des1, des2, k=2)
    
    good = []
    for pair in knn_matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.75 * n.distance:
            good.append(m)

    if len(good) < 4:
        print("Not enough matches found to compute homography.")
        return

    # queryIdx refers to Image A; trainIdx refers to Image B.
    # H therefore maps A's coordinates into B's coordinate frame.
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    cv2.setRNGSeed(0)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

    if H is None or mask is None or not np.isfinite(H).all():
        print("Homography computation failed.")
        return
    inliers = mask.ravel().astype(bool)
    inlier_count = int(inliers.sum())
    if inlier_count < 4:
        print("Not enough RANSAC inliers to align the images.")
        return
    os.makedirs(output_dir, exist_ok=True)

    # Draw purely the inlier matches
    matchesMask = mask.ravel().tolist()
    draw_params = dict(matchColor=(0, 255, 0), singlePointColor=None, matchesMask=matchesMask, flags=2)
    img_inliers = cv2.drawMatches(img1, kp1, img2, kp2, good, None, **draw_params)
    # Output is cropped to B's canvas, as required by the lab.
    h, w = img2.shape[:2]
    img1_warped = cv2.warpPerspective(img1, H, (w, h))
    overlay = cv2.addWeighted(img1_warped, 0.5, img2, 0.5, 0)

    # Do not darken areas where the warped source has no valid pixels.
    # Use a geometric mask so genuinely black pixels remain valid data.
    coverage = cv2.warpPerspective(
        np.full(gray1.shape, 255, dtype=np.uint8), H, (w, h),
        flags=cv2.INTER_NEAREST,
    )
    overlay[coverage == 0] = img2[coverage == 0]

    for filename, result in (
        ("task3_inlier_matches.jpg", img_inliers),
        ("task3_warped_img1.jpg", img1_warped),
        ("task3_final_overlay.jpg", overlay),
    ):
        out_name = os.path.join(output_dir, filename)
        if not cv2.imwrite(out_name, result):
            raise OSError(f"Could not save {out_name}")

    projected = cv2.perspectiveTransform(src_pts[inliers], H)
    errors = np.linalg.norm((projected - dst_pts[inliers]).reshape(-1, 2), axis=1)
    stats = {
        "keypoints_a": len(kp1),
        "keypoints_b": len(kp2),
        "ratio_threshold": 0.75,
        "ransac_threshold_px": 5.0,
        "rng_seed": 0,
        "good_matches": len(good),
        "inlier_count": inlier_count,
        "outlier_count": len(good) - inlier_count,
        "inlier_ratio": inlier_count / len(good),
        "inlier_reprojection_mean_px": float(errors.mean()),
        "inlier_reprojection_median_px": float(np.median(errors)),
        "inlier_reprojection_max_px": float(errors.max()),
        "homography_a_to_b": H.tolist(),
    }
    print(f"RANSAC: {inlier_count}/{len(good)} inliers "
          f"({stats['inlier_ratio']:.1%}); "
          f"mean reprojection error: {stats['inlier_reprojection_mean_px']:.3f} px")
    print(f"Alignment complete. Results saved in {output_dir}")
    return stats
