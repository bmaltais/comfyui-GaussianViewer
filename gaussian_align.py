# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 ComfyUI-GaussianViewer Contributors

import os
import json
import time
import numpy as np
import torch
import cv2
from PIL import Image
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R

from .render_gaussian import RenderGaussianNode
from .camera_params import set_camera_state

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

class GaussianSIFTAlignNode(RenderGaussianNode):
    """
    Iteratively align Gaussian Splat camera parameters to a reference image using SIFT.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ply_path": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Path to a Gaussian Splatting PLY file"
                }),
                "reference_image": ("IMAGE", {
                    "tooltip": "Reference image to align to"
                }),
                "max_iterations": ("INT", {"default": 20, "min": 1, "max": 100}),
            },
            "optional": {
                "initial_extrinsics": ("EXTRINSICS", {
                    "tooltip": "Initial camera extrinsics (optional, overrides cached state)"
                }),
                "initial_intrinsics": ("INTRINSICS", {
                    "tooltip": "Initial camera intrinsics"
                }),
                "learning_rate": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 10.0}),
            },
        }

    RETURN_TYPES = ("IMAGE", "EXTRINSICS", "INTRINSICS", "DICT")
    RETURN_NAMES = ("aligned_image", "extrinsics", "intrinsics", "camera_state")
    FUNCTION = "gaussian_sift_align"
    CATEGORY = "geompack/alignment"

    def gaussian_sift_align(self, ply_path, reference_image, max_iterations,
                            initial_extrinsics=None, initial_intrinsics=None, learning_rate=1.0):
        print(f"[GaussianSIFTAlign] Starting alignment with {max_iterations} iterations")

        # 1. Prepare reference image
        ref_np = (reference_image[0].cpu().numpy() * 255).astype(np.uint8)
        ref_bgr = cv2.cvtColor(ref_np, cv2.COLOR_RGB2BGR)

        # 2. Detect SIFT features in reference
        sift = cv2.SIFT_create()
        ref_kp, ref_des = sift.detectAndCompute(ref_bgr, None)

        if ref_des is None:
            print("[GaussianSIFTAlign] ERROR: No SIFT features found in reference image")
            return (reference_image, initial_extrinsics, initial_intrinsics, {})

        # 3. Initialize camera state
        filename = os.path.basename(ply_path)
        cached_state = self._lookup_camera_state(ply_path, filename, filename)

        initial_p = [0.0, 0.0, 0.0, 0.0, 0.0, 5.0, 0.0] # Default: target=0, spherical=0, radius=5, roll=0

        if initial_extrinsics is not None:
            print("[GaussianSIFTAlign] Using provided initial extrinsics")
            initial_p = self._extrinsics_to_p(initial_extrinsics)
        elif cached_state:
            print("[GaussianSIFTAlign] Using cached camera state")
            t = cached_state.get('target', {'x': 0, 'y': 0, 'z': 0})
            p = cached_state.get('position', {'x': 0, 'y': 0, 'z': 5})
            dx = t['x'] - p['x']
            dy = t['y'] - p['y']
            dz = t['z'] - p['z']
            radius = np.sqrt(dx*dx + dy*dy + dz*dz)
            beta = np.arctan2(dy, np.sqrt(dx*dx + dz*dz))
            alpha = -np.arctan2(dx, dz)
            roll = cached_state.get('roll', 0)
            initial_p = [t['x'], t['y'], t['z'], float(alpha), float(beta), float(radius), float(roll)]

        # 4. Optimization Loop
        current_state_dict = cached_state.copy() if cached_state else {}
        if initial_intrinsics:
            # Derive image dimensions and focal from intrinsics
            cx = initial_intrinsics[0][2]
            cy = initial_intrinsics[1][2]
            current_state_dict.update({
                "fx": initial_intrinsics[0][0],
                "fy": initial_intrinsics[1][1],
                "image_width": cx * 2,
                "image_height": cy * 2
            })

        def objective(p):
            # Check for stop flag
            from .render_gaussian import STOP_SIFT_ALIGNMENT
            if STOP_SIFT_ALIGNMENT:
                raise StopIteration

            # Convert p to camera state
            state = self._p_to_camera_state(p)
            # Merge with current state (for fx, fy, scale, etc.)
            full_state = current_state_dict.copy()
            full_state.update(state)

            # Render image using the new forced_camera_state argument
            try:
                rendered_tuple = super(GaussianSIFTAlignNode, self).render_gaussian(
                    ply_path,
                    forced_camera_state=full_state
                )
                rendered_img = rendered_tuple[0]

                loss = self._compute_sift_loss(rendered_img, ref_kp, ref_des, sift)
                print(f"[GaussianSIFTAlign] Loss: {loss:.4f} (p: {[f'{x:.3f}' for x in p]})")
                return loss
            except Exception as e:
                print(f"[GaussianSIFTAlign] Iteration error: {e}")
                return 1e6

        def on_iteration(xk):
            # Check for stop flag
            from .render_gaussian import STOP_SIFT_ALIGNMENT
            if STOP_SIFT_ALIGNMENT:
                raise StopIteration

            # Send current state to frontend for visual update
            if PromptServer:
                state = self._p_to_camera_state(xk)
                full_state = current_state_dict.copy()
                full_state.update(state)

                # We need to provide enough info for the frontend to apply it
                # PromptServer.instance.send works for all connected clients
                PromptServer.instance.send("geompack_sift_align_update", {
                    "ply_file": filename,
                    "camera_state": full_state
                })

        # Run optimization using Nelder-Mead (no gradients needed)
        res = minimize(objective, initial_p, method='Nelder-Mead',
                       callback=on_iteration,
                       options={'maxiter': max_iterations, 'xatol': 1e-3, 'fatol': 1e-3})

        final_p = res.x
        final_state = self._p_to_camera_state(final_p)
        full_final_state = current_state_dict.copy()
        full_final_state.update(final_state)

        # Compute final matrices
        final_extrinsics = self._p_to_extrinsics(final_p)
        final_intrinsics = initial_intrinsics
        if not final_intrinsics and 'fx' in full_final_state:
            fx = full_final_state['fx']
            fy = full_final_state['fy']
            w = full_final_state.get('image_width', 1024)
            h = full_final_state.get('image_height', 1024)
            final_intrinsics = [[fx, 0, w/2], [0, fy, h/2], [0, 0, 1]]

        # Update global cache with final result
        set_camera_state(filename, full_final_state)
        set_camera_state(ply_path, full_final_state)

        # Final render at full resolution
        final_rendered_tuple = super(GaussianSIFTAlignNode, self).render_gaussian(
            ply_path,
            forced_camera_state=full_final_state
        )

        return (final_rendered_tuple[0], final_extrinsics, final_intrinsics, full_final_state)

    def _p_to_camera_state(self, p):
        tx, ty, tz, alpha, beta, radius, roll = p
        # Compute position (Spherical around target)
        x = tx + radius * np.sin(alpha) * np.cos(beta)
        y = ty - radius * np.sin(beta)
        z = tz - radius * np.cos(alpha) * np.cos(beta)

        return {
            "position": {"x": float(x), "y": float(y), "z": float(z)},
            "target": {"x": float(tx), "y": float(ty), "z": float(tz)},
            "roll": float(roll)
        }

    def _p_to_extrinsics(self, p):
        state = self._p_to_camera_state(p)
        pos = np.array([state['position']['x'], state['position']['y'], state['position']['z']])
        # pitch = -beta, yaw = -alpha
        alpha, beta, roll = p[3], p[4], p[6]

        rot = R.from_euler('YXZ', [-alpha, -beta, roll], degrees=False)
        w2c_r = rot.as_matrix().T
        w2c_t = -w2c_r @ pos

        extrinsics = np.eye(4)
        extrinsics[:3, :3] = w2c_r
        extrinsics[:3, 3] = w2c_t
        return extrinsics.tolist()

    def _extrinsics_to_p(self, extrinsics):
        E = np.array(extrinsics)
        w2c_r = E[:3, :3]
        w2c_t = E[:3, 3]
        pos = -w2c_r.T @ w2c_t

        # Decompose R to get angles
        rot = R.from_matrix(w2c_r.T)
        angles = rot.as_euler('YXZ', degrees=False)
        yaw, pitch, roll = angles

        radius = 5.0
        alpha = -yaw
        beta = -pitch

        tx = pos[0] - radius * np.sin(alpha) * np.cos(beta)
        ty = pos[1] + radius * np.sin(beta)
        tz = pos[2] + radius * np.cos(alpha) * np.cos(beta)

        return [float(tx), float(ty), float(tz), float(alpha), float(beta), float(radius), float(roll)]

    def _compute_sift_loss(self, rendered_img, ref_kp, ref_des, sift):
        if rendered_img is None:
            return 1e6

        # Convert tensor to BGR
        rend_np = (rendered_img[0].cpu().numpy() * 255).astype(np.uint8)
        rend_bgr = cv2.cvtColor(rend_np, cv2.COLOR_RGB2BGR)

        rend_kp, rend_des = sift.detectAndCompute(rend_bgr, None)
        if rend_des is None:
            return 1e6

        bf = cv2.BFMatcher()
        try:
            matches = bf.knnMatch(ref_des, rend_des, k=2)
        except Exception as e:
            return 1e6

        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)

        if len(good_matches) < 4:
            return 1e6 - len(good_matches) * 100

        dist = 0
        for m in good_matches:
            p1 = ref_kp[m.queryIdx].pt
            p2 = rend_kp[m.trainIdx].pt
            dist += (p1[0] - p2[0])**2 + (p1[1] - p2[1])**2

        avg_dist = np.sqrt(dist / len(good_matches))
        loss = avg_dist + 500.0 / (len(good_matches) + 1)

        return loss
