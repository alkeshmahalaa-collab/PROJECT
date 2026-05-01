from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from scipy import ndimage


class TextureGenerator:

    def __init__(self):
        self.source: Image.Image | None = None
        self.width = 0
        self.height = 0

    def load(self, path: str) -> Image.Image:
        self.source = Image.open(path).convert('RGB')
        self.width, self.height = self.source.size
        return self.source

    @staticmethod
    def _to_arr(img: Image.Image) -> np.ndarray:
        return np.array(img.convert('RGB'), dtype=np.float32) / 255.0

    @staticmethod
    def _to_img(arr: np.ndarray) -> Image.Image:
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=2)
        return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), 'RGB')

    # ── map generators ──────────────────────────────────────────────────────

    def diffuse(self, saturation: float = 1.0, remove_specular: bool = True,
                spec_threshold: float = 0.88) -> Image.Image:
        arr = self._to_arr(self.source)

        if remove_specular:
            r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            mx = np.maximum(np.maximum(r, g), b)
            mn = np.minimum(np.minimum(r, g), b)
            sat_ch = np.where(mx > 0.01, (mx - mn) / mx, 0.0)

            spec_mask = ((lum > spec_threshold) & (sat_ch < 0.12)).astype(np.float32)
            spec_mask = ndimage.gaussian_filter(spec_mask, sigma=3)[..., np.newaxis]

            valid = lum < spec_threshold
            avg = np.array([
                float(np.mean(r[valid])) if valid.any() else 0.5,
                float(np.mean(g[valid])) if valid.any() else 0.5,
                float(np.mean(b[valid])) if valid.any() else 0.5,
            ])
            arr = arr * (1.0 - spec_mask) + avg * spec_mask

        result = self._to_img(arr)
        if saturation != 1.0:
            result = ImageEnhance.Color(result).enhance(saturation)
        return result

    def height(self, blur: float = 0.0, contrast: float = 1.0,
               invert: bool = False) -> Image.Image:
        gray = self.source.convert('L')
        if blur > 0:
            gray = gray.filter(ImageFilter.GaussianBlur(blur))
        if contrast != 1.0:
            gray = ImageEnhance.Contrast(gray).enhance(contrast)
        if invert:
            gray = ImageOps.invert(gray)
        return gray.convert('RGB')

    def normal(self, strength: float = 3.0, blur: float = 1.0) -> Image.Image:
        gray = self.source.convert('L')
        if blur > 0:
            gray = gray.filter(ImageFilter.GaussianBlur(blur))
        arr = np.array(gray, dtype=np.float32) / 255.0

        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32) / 8.0
        ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32) / 8.0

        dx = ndimage.convolve(arr, kx) * strength
        dy = ndimage.convolve(arr, ky) * strength
        dz = np.ones_like(arr)

        length = np.sqrt(dx ** 2 + dy ** 2 + dz ** 2) + 1e-8
        nx = (dx / length + 1.0) / 2.0
        ny = (dy / length + 1.0) / 2.0
        nz = dz / length

        return self._to_img(np.stack([nx, ny, nz], axis=2))

    def reflection(self, intensity: float = 0.8, gamma: float = 1.0,
                   contrast: float = 1.0) -> Image.Image:
        arr = self._to_arr(self.source)
        lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]

        if gamma != 1.0:
            lum = np.clip(lum, 1e-8, 1.0) ** (1.0 / gamma)
        if contrast != 1.0:
            lum = np.clip((lum - 0.5) * contrast + 0.5, 0, 1)

        lum = np.clip(lum * intensity, 0, 1)
        return self._to_img(np.stack([lum, lum, lum], axis=2))

    def glossiness(self, base: float = 0.8, variance_scale: float = 5.0) -> Image.Image:
        gray = np.array(self.source.convert('L'), dtype=np.float32) / 255.0
        mean = ndimage.uniform_filter(gray, size=7)
        mean_sq = ndimage.uniform_filter(gray ** 2, size=7)
        var = np.sqrt(np.clip(mean_sq - mean ** 2, 0, 1))
        gloss = np.clip((1.0 - var * variance_scale) * base, 0, 1)
        return self._to_img(np.stack([gloss, gloss, gloss], axis=2))

    def ao(self, radius: int = 15, intensity: float = 0.8,
           blur: float = 2.0) -> Image.Image:
        gray = np.array(self.source.convert('L'), dtype=np.float32) / 255.0
        local_min = ndimage.minimum_filter(gray, size=max(3, radius))
        ao_map = np.clip(1.0 - (gray - local_min) * intensity, 0, 1)
        if blur > 0:
            ao_map = ndimage.gaussian_filter(ao_map, sigma=blur)
        ao_map = np.clip(ao_map, 0, 1)
        return self._to_img(np.stack([ao_map, ao_map, ao_map], axis=2))

    def metallic(self, invert: bool = False, blur: float = 2.0) -> Image.Image:
        arr = self._to_arr(self.source)
        mx = np.maximum(np.maximum(arr[..., 0], arr[..., 1]), arr[..., 2])
        mn = np.minimum(np.minimum(arr[..., 0], arr[..., 1]), arr[..., 2])
        sat_ch = np.where(mx > 0.01, (mx - mn) / mx, 0.0)
        metal = 1.0 - sat_ch
        if blur > 0:
            metal = ndimage.gaussian_filter(metal, sigma=blur)
        if invert:
            metal = 1.0 - metal
        metal = np.clip(metal, 0, 1)
        return self._to_img(np.stack([metal, metal, metal], axis=2))
