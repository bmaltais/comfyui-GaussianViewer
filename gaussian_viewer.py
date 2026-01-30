# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 ComfyUI-GaussianViewer Contributors

"""
Combined Gaussian viewer node.

Merges preview and render into a single IMAGE-producing node.
"""

import os
import uuid
import numpy as np
import torch
from PIL import Image

from .render_gaussian import RenderGaussianNode, COMFYUI_OUTPUT_FOLDER


class GaussianViewerNode(RenderGaussianNode):
    """
    Preview + render Gaussian splatting PLY files in a single node.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ply_path": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Path to a Gaussian Splatting PLY file"
                }),
            },
            "optional": {
                "ply_path_b": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Optional second PLY file for 3D-3D alignment"
                }),
                "extrinsics": ("EXTRINSICS", {
                    "tooltip": "4x4 camera extrinsics matrix for initial view"
                }),
                "intrinsics": ("INTRINSICS", {
                    "tooltip": "3x3 camera intrinsics matrix for FOV"
                }),
                "image": ("IMAGE", {
                    "tooltip": "Reference image to show as overlay"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    OUTPUT_NODE = True
    FUNCTION = "gaussian_viewer"
    CATEGORY = "geompack/visualization"

    def gaussian_viewer(self, ply_path: str, ply_path_b: str = None, extrinsics=None, intrinsics=None, image=None):
        """
        Preview the PLY in the viewer and return the rendered IMAGE output.
        """
        print("=" * 80)
        print("[GaussianViewer] ===== VIEWER NODE EXECUTED =====")
        print("=" * 80)
        print("[GaussianViewer] Input parameters:")
        print(f"  ply_path: {ply_path}")
        print(f"  ply_path_b: {ply_path_b}")
        print(f"  extrinsics: {extrinsics is not None}")
        print(f"  intrinsics: {intrinsics is not None}")

        if not ply_path:
            print("[GaussianViewer] ERROR: No PLY path provided")
            image = self._create_placeholder_image(2048, 1.0)
            return {"ui": {"error": ["No PLY path provided"]}, "result": (image,)}

        if not os.path.exists(ply_path):
            print(f"[GaussianViewer] ERROR: PLY file not found: {ply_path}")
            image = self._create_placeholder_image(2048, 1.0)
            return {"ui": {"error": [f"File not found: {ply_path}"]}, "result": (image,)}

        filename = os.path.basename(ply_path)
        if COMFYUI_OUTPUT_FOLDER and ply_path.startswith(COMFYUI_OUTPUT_FOLDER):
            relative_path = os.path.relpath(ply_path, COMFYUI_OUTPUT_FOLDER)
        else:
            relative_path = filename

        file_size = os.path.getsize(ply_path)
        file_size_mb = file_size / (1024 * 1024)

        print("[GaussianViewer] File info:")
        print(f"  Full path: {ply_path}")
        print(f"  Relative path: {relative_path}")
        print(f"  Filename: {filename}")
        print(f"  File size: {file_size_mb:.2f} MB ({file_size:,} bytes)")

        ui_data = {
            "ply_file": [relative_path],
            "filename": [filename],
            "file_size_mb": [round(file_size_mb, 2)],
        }

        if ply_path_b and os.path.exists(ply_path_b):
            filename_b = os.path.basename(ply_path_b)
            if COMFYUI_OUTPUT_FOLDER and ply_path_b.startswith(COMFYUI_OUTPUT_FOLDER):
                rel_b = os.path.relpath(ply_path_b, COMFYUI_OUTPUT_FOLDER)
            else:
                rel_b = filename_b

            ui_data["ply_file_b"] = [rel_b]
            ui_data["filename_b"] = [filename_b]
            print(f"[GaussianViewer] Second PLY provided: {filename_b}")

        if extrinsics is not None:
            ui_data["extrinsics"] = [extrinsics]
            print(f"[GaussianViewer] Extrinsics provided: {len(extrinsics)}x{len(extrinsics[0])}")
        if intrinsics is not None:
            ui_data["intrinsics"] = [intrinsics]
            print(f"[GaussianViewer] Intrinsics provided: {len(intrinsics)}x{len(intrinsics[0])}")

        if image is not None:
            print(f"[GaussianViewer] Reference image provided: {image.shape}")
            try:
                # Save the first image in the batch as an overlay
                img_tensor = image[0]
                i = 255. * img_tensor.cpu().numpy()
                img = Image.fromarray(np.uint8(i))

                overlay_filename = f"gaussian_overlay_{uuid.uuid4().hex}.png"
                overlay_path = os.path.join(COMFYUI_OUTPUT_FOLDER, overlay_filename)
                img.save(overlay_path)

                ui_data["overlay_image"] = [overlay_filename]
                print(f"[GaussianViewer] Overlay image saved: {overlay_filename}")
            except Exception as e:
                print(f"[GaussianViewer] ERROR saving overlay image: {e}")

        print(f"[GaussianViewer] UI data keys: {list(ui_data.keys())}")
        print("[GaussianViewer] ===== VIEWER PREVIEW READY =====")
        print("=" * 80)

        image_tuple = super().render_gaussian(ply_path, extrinsics, intrinsics)
        return {"ui": ui_data, "result": image_tuple}


NODE_CLASS_MAPPINGS = {
    "GaussianViewer": GaussianViewerNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GaussianViewer": "GaussianViewer",
}
