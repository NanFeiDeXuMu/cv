import numpy as np

def my_imfilter(image, kernel):
    """
    Apply a 2D filter to an image using manual convolution.

    Args:
        image: A 2D (grayscale) or 3D (color) numpy array.
        kernel: A 2D numpy array representing the filter.

    Returns:
        output: Filtered image.
    """

    # Accumulate in floating point to avoid overflow and preserve fractions.
    kernel = np.asarray(kernel, dtype=np.float64)
    if image.ndim not in (2, 3) or kernel.ndim != 2:
        raise ValueError("Expected a grayscale/color image and a 2D kernel")
    if any(size == 0 or size % 2 == 0 for size in kernel.shape):
        raise ValueError("Kernel dimensions must be positive and odd")

    # Get image and kernel dimensions
    i_h, i_w = image.shape[:2]
    k_h, k_w = kernel.shape

    # Calculate padding size (assuming kernel is odd)
    pad_h = k_h // 2
    pad_w = k_w // 2

    # 1. Padding
    # We use 'reflect' padding as suggested in the lecture slides
    # to handle boundaries.
    working_image = image.astype(np.float64)
    if len(image.shape) == 2:
        padded_image = np.pad(
            working_image, ((pad_h, pad_h), (pad_w, pad_w)), mode='reflect'
        )
    else:
        padded_image = np.pad(
            working_image,
            ((pad_h, pad_h), (pad_w, pad_w), (0, 0)),
            mode='reflect',
        )
    output = np.zeros_like(working_image)

    # 2. Convolution Loop
    # Slide the kernel over the image and compute the weighted sum (dot product).
    for y in range(i_h):
        for x in range(i_w):
            if image.ndim == 2:
                region = padded_image[y:y + k_h, x:x + k_w]
                output[y, x] = np.sum(region * kernel)
            else:
                for channel in range(image.shape[2]):
                    region = padded_image[y:y + k_h, x:x + k_w, channel]
                    output[y, x, channel] = np.sum(region * kernel)

    # Preserve the input format; clip integer images before conversion.
    if np.issubdtype(image.dtype, np.integer):
        limits = np.iinfo(image.dtype)
        output = np.clip(output, limits.min, limits.max)
    return output.astype(image.dtype)
