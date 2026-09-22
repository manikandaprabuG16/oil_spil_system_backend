"""
SAR & Optical Oil Spill Detection Pipeline
-------------------------------------------
Implements Synthetic Aperture Radar (SAR) dark-spot detection:
1. Speckle noise reduction (Lee / Bilateral filter)
2. Radiometric intensity normalization and contrast enhancement
3. Adaptive thresholding for low-backscatter dampening slick detection
4. Morphological filtering (opening/closing) to isolate slick bodies
5. Geo-referencing: transforms pixel contours into GeoJSON lat/lon coordinates
6. Feature extraction: Area (km^2), centroid (lat, lon), perimeter, compactness, confidence
"""

import math
import numpy as np
import cv2
from typing import Dict, Any, List, Tuple, Optional


class SARSpillDetector:
    def __init__(self, pixel_resolution_meters: float = 10.0):
        """
        :param pixel_resolution_meters: Ground Sampling Distance (GSD), e.g., 10m for Sentinel-1 IW GRD mode.
        """
        self.pixel_resolution = pixel_resolution_meters

    def preprocess_sar(self, image_gray: np.ndarray) -> np.ndarray:
        """
        Reduces SAR speckle noise and normalizes dynamic range.
        """
        # 1. Bilateral filter preserves sharp slick boundaries while smoothing speckle noise
        filtered = cv2.bilateralFilter(image_gray, d=7, sigmaColor=50, sigmaSpace=50)
        # 2. Contrast Limited Adaptive Histogram Equalization (CLAHE) for maritime contrast
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(filtered)
        return enhanced

    def detect_spill(
        self,
        image_bytes_or_array: Any,
        geo_bounds: Dict[str, float],
        min_area_km2: float = 0.05
    ) -> Dict[str, Any]:
        """
        Detects oil spill candidates from SAR or Optical imagery.
        
        :param image_bytes_or_array: File bytes, filepath, or np.ndarray
        :param geo_bounds: {"north": float, "south": float, "east": float, "west": float}
        :param min_area_km2: Minimum threshold area to reject spurious noise
        :return: Detection report with polygon coordinates, centroid, area_km2, and confidence.
        """
        if isinstance(image_bytes_or_array, (bytes, bytearray)):
            nparr = np.frombuffer(image_bytes_or_array, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        elif isinstance(image_bytes_or_array, str):
            img = cv2.imread(image_bytes_or_array, cv2.IMREAD_GRAYSCALE)
        else:
            img = image_bytes_or_array
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = img.shape
        enhanced = self.preprocess_sar(img)

        # In SAR imagery, oil spills appear as dark patches (low backscatter due to capillary wave dampening)
        thresh = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 41, 7
        )

        # Morphological operations to merge fragmented slick segments and remove single pixel noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        morph = cv2.morphologyEx(morph, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        spills = []
        sq_meters_per_pixel = self.pixel_resolution * self.pixel_resolution
        sq_km_per_pixel = sq_meters_per_pixel / 1_000_000.0

        for cnt in contours:
            pixel_area = cv2.contourArea(cnt)
            area_km2 = pixel_area * sq_km_per_pixel
            if area_km2 < min_area_km2:
                continue

            # Compute image moments for centroid
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
            else:
                x, y, cw, ch = cv2.boundingRect(cnt)
                cx = x + cw / 2.0
                cy = y + ch / 2.0

            # Geo-reference pixel coordinates to lat/lon
            centroid_lat, centroid_lon = self._pixel_to_latlon(cx, cy, w, h, geo_bounds)

            # Simplify contour polygon for web GIS rendering
            epsilon = 0.008 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            geo_polygon = []
            for pt in approx:
                px, py = pt[0]
                lat, lon = self._pixel_to_latlon(px, py, w, h, geo_bounds)
                geo_polygon.append([lon, lat])

            if len(geo_polygon) > 2 and geo_polygon[0] != geo_polygon[-1]:
                geo_polygon.append(geo_polygon[0])  # Close ring

            # Compute Confidence Score
            mask = np.zeros(img.shape, dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_slick_intensity = cv2.mean(img, mask=mask)[0]
            mean_bg_intensity = cv2.mean(img)[0]
            contrast_ratio = max(0.0, (mean_bg_intensity - mean_slick_intensity) / (mean_bg_intensity + 1e-5))

            perimeter = cv2.arcLength(cnt, True)
            circularity = 4 * math.pi * (pixel_area / (perimeter * perimeter + 1e-5))
            shape_score = 0.85 if circularity < 0.5 else 0.70

            confidence = min(0.98, max(0.40, 0.45 + contrast_ratio * 0.4 + shape_score * 0.15))

            perimeter_km = round((perimeter * self.pixel_resolution) / 1000.0, 2)
            # Default heavy crude thickness based on SAR radiometric contrast (0.15 - 0.35 mm)
            thickness_mm = round(0.18 + min(0.17, contrast_ratio * 0.25), 2)
            volume_m3 = round(area_km2 * thickness_mm * 1000.0, 2)
            volume_bbl = round(volume_m3 * 6.28981, 1)
            volume_tons = round(volume_m3 * 0.88, 2)
            # 48h recovery window with 40 m3/h skimmers @ 25% EDRC = 480 m3 per skimmer
            skimmers_needed = max(1, math.ceil(volume_m3 / 480.0))
            # 1,500 m3 tanker capacity with 35% emulsion water cut
            tankers_needed = max(1, math.ceil((volume_m3 * 1.35) / 1500.0))
            boom_length_km = round(perimeter_km * 1.25, 2)

            spills.append({
                "area_km2": round(area_km2, 3),
                "centroid": {"lat": round(centroid_lat, 5), "lon": round(centroid_lon, 5)},
                "polygon": geo_polygon,
                "confidence": round(confidence, 2),
                "contrast_ratio": round(contrast_ratio, 3),
                "perimeter_km": perimeter_km,
                "thickness_mm": thickness_mm,
                "volume_m3": volume_m3,
                "volume_bbl": volume_bbl,
                "volume_tons": volume_tons,
                "skimmers_needed": skimmers_needed,
                "tankers_needed": tankers_needed,
                "boom_length_km": boom_length_km
            })

        # Sort spills by area descending
        spills.sort(key=lambda s: s["area_km2"], reverse=True)

        primary_spill = spills[0] if spills else None
        return {
            "spill_detected": primary_spill is not None,
            "total_patches_detected": len(spills),
            "primary_spill": primary_spill,
            "all_spills": spills
        }

    def _pixel_to_latlon(
        self, px: float, py: float, img_w: int, img_h: int, bounds: Dict[str, float]
    ) -> Tuple[float, float]:
        """
        Linearly interpolates pixel coordinates into WGS84 Geographic coordinates (Lat, Lon).
        """
        lon = bounds["west"] + (px / img_w) * (bounds["east"] - bounds["west"])
        lat = bounds["north"] - (py / img_h) * (bounds["north"] - bounds["south"])
        return lat, lon

    def generate_synthetic_sar_patch(
        self,
        width: int = 512,
        height: int = 512,
        spill_center_ratio: Tuple[float, float] = (0.55, 0.48),
        spill_radius: int = 70
    ) -> np.ndarray:
        """
        Generates a realistic synthetic Sentinel-1 SAR marine image patch.
        """
        ocean_base = np.random.rayleigh(scale=55, size=(height, width)).astype(np.float32)
        ocean_base = np.clip(ocean_base, 0, 255).astype(np.uint8)
        ocean = cv2.GaussianBlur(ocean_base, (5, 5), 0)

        slick_mask = np.zeros((height, width), dtype=np.uint8)
        cx = int(width * spill_center_ratio[0])
        cy = int(height * spill_center_ratio[1])

        cv2.ellipse(slick_mask, (cx, cy), (spill_radius * 2, int(spill_radius * 1.1)), 35, 0, 360, 255, -1)

        noise = np.random.normal(0, 25, (height, width)).astype(np.float32)
        noise_blurred = cv2.GaussianBlur(noise, (21, 21), 0)
        distorted_mask = np.clip(slick_mask.astype(np.float32) + noise_blurred * 2.5, 0, 255).astype(np.uint8)
        _, final_mask = cv2.threshold(distorted_mask, 120, 255, cv2.THRESH_BINARY)

        sar_result = ocean.copy().astype(np.float32)
        slick_indices = final_mask > 0
        sar_result[slick_indices] = sar_result[slick_indices] * 0.28 + np.random.normal(15, 4, np.sum(slick_indices))

        return np.clip(sar_result, 0, 255).astype(np.uint8)
