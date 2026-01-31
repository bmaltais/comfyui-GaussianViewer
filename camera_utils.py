# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 ComfyUI-GaussianViewer Contributors

import json
import numpy as np

class GaussianCameraState:
    """
    Generate camera state, extrinsics, and intrinsics from position and rotation.
    Useful for specifying camera poses from COLMAP or other external tools.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "x": ("FLOAT", {"default": 0.0, "step": 0.001}),
                "y": ("FLOAT", {"default": 0.0, "step": 0.001}),
                "z": ("FLOAT", {"default": 0.0, "step": 0.001}),
                "pitch": ("FLOAT", {"default": 0.0, "step": 0.1}),
                "yaw": ("FLOAT", {"default": 0.0, "step": 0.1}),
                "roll": ("FLOAT", {"default": 0.0, "step": 0.1}),
                "fx": ("FLOAT", {"default": 1000.0, "step": 1.0}),
                "fy": ("FLOAT", {"default": 1000.0, "step": 1.0}),
                "width": ("INT", {"default": 2048, "min": 64, "max": 8192}),
                "height": ("INT", {"default": 2048, "min": 64, "max": 8192}),
                "coordinate_system": (["viewer", "colmap"], {"default": "viewer"}),
            },
            "optional": {
                "json_string": ("STRING", {"default": "", "multiline": True, "placeholder": '{"x": 0.0, "y": 0.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0, "roll": 0.0}'}),
            }
        }

    RETURN_TYPES = ("STRING", "EXTRINSICS", "INTRINSICS")
    RETURN_NAMES = ("camera_state", "extrinsics", "intrinsics")
    FUNCTION = "generate_camera_state"
    CATEGORY = "geompack/visualization"

    def generate_camera_state(self, x, y, z, pitch, yaw, roll, fx, fy, width, height, coordinate_system, json_string=""):
        # 1. Start with provided float values
        params = {
            "x": x, "y": y, "z": z,
            "pitch": pitch, "yaw": yaw, "roll": roll,
            "fx": fx, "fy": fy,
            "width": width, "height": height
        }

        # 2. Override with JSON if provided
        if json_string and json_string.strip():
            try:
                # Handle potential single quotes or other common JSON-like formatting issues
                clean_json = json_string.strip().replace("'", '"')
                json_data = json.loads(clean_json)

                # Update params with JSON values
                param_keys = ["x", "y", "z", "pitch", "yaw", "roll", "fx", "fy", "width", "height"]
                for k in param_keys:
                    if k in json_data:
                        params[k] = float(json_data[k])

                # Also handle 'image_width' / 'image_height' aliases
                if "image_width" in json_data: params["width"] = int(json_data["image_width"])
                if "image_height" in json_data: params["height"] = int(json_data["image_height"])

            except Exception as e:
                print(f"[GaussianCameraState] Warning: Failed to parse JSON string: {e}")

        # 3. Handle coordinate system conversion
        # COLMAP is Y-down, Viewer is Y-up.
        # Flipping Y also requires flipping Pitch (rotation around X).
        if coordinate_system == "colmap":
            params["y"] = -params["y"]
            params["pitch"] = -params["pitch"]

        # 4. Create camera_state dict for viewer
        camera_state = {
            "position": {"x": params["x"], "y": params["y"], "z": params["z"]},
            "pitch": params["pitch"],
            "yaw": params["yaw"],
            "roll": params["roll"],
            "fx": params["fx"],
            "fy": params["fy"],
            "image_width": int(params["width"]),
            "image_height": int(params["height"]),
            "scale": 1.0
        }

        # 5. Generate matrices
        extrinsics = self._get_extrinsics(params)
        intrinsics = [
            [params["fx"], 0.0, params["width"] / 2.0],
            [0.0, params["fy"], params["height"] / 2.0],
            [0.0, 0.0, 1.0]
        ]

        return (json.dumps(camera_state), extrinsics, intrinsics)

    def _get_extrinsics(self, params):
        """
        Convert position and rotation to World-to-Camera matrix [R | t].
        Rotation follows intrinsic YXZ (Yaw-Pitch-Roll) convention.
        """
        y = np.radians(params["yaw"])
        p = np.radians(params["pitch"])
        r = np.radians(params["roll"])

        # R_y (Yaw)
        Ry = np.array([
            [np.cos(y), 0, np.sin(y)],
            [0, 1, 0],
            [-np.sin(y), 0, np.cos(y)]
        ])

        # R_x (Pitch)
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(p), -np.sin(p)],
            [0, np.sin(p), np.cos(p)]
        ])

        # R_z (Roll)
        Rz = np.array([
            [np.cos(r), -np.sin(r), 0],
            [np.sin(r), np.cos(r), 0],
            [0, 0, 1]
        ])

        # R_cam_to_world = Ry * Rx * Rz
        R_cam_to_world = Ry @ Rx @ Rz

        # Extrinsics R is World-to-Camera (R_cam_to_world.T)
        R = R_cam_to_world.T

        pos = np.array([params["x"], params["y"], params["z"]])
        t = -R @ pos

        m = np.eye(4)
        m[:3, :3] = R
        m[:3, 3] = t
        return m.tolist()
