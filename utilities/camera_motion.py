#!/usr/bin/env python3
"""
Camera Motion Compensation Module
Handles camera pan, tilt, zoom to improve tracking accuracy
Uses optical flow and homography estimation
"""

import cv2
import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)


class CameraMotionCompensator:
    """
    Compensate for camera motion (pan/tilt/zoom) to improve object tracking

    Methods:
    - Optical Flow (Farneback): Dense flow estimation
    - Feature-based: SIFT/ORB + homography
    - EMA smoothing: Reduce jitter
    """

    def __init__(self, method='optical_flow', buffer_size=5):
        """
        Initialize camera motion compensator

        Args:
            method: 'optical_flow' or 'feature_based'
            buffer_size: Number of frames for smoothing
        """
        self.method = method
        self.prev_gray = None
        self.prev_features = None
        self.homography_buffer = deque(maxlen=buffer_size)

        # Feature detector for feature-based method
        if method == 'feature_based':
            try:
                # Try SIFT (best quality)
                self.feature_detector = cv2.SIFT_create(nfeatures=500)
                self.matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
                logger.info("✅ Camera motion: SIFT-based")
            except:
                # Fallback to ORB (free, faster)
                self.feature_detector = cv2.ORB_create(nfeatures=500)
                self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
                logger.info("✅ Camera motion: ORB-based")
        else:
            logger.info("✅ Camera motion: Optical flow")

        # Motion statistics
        self.camera_motion = np.zeros(2)  # [dx, dy]
        self.is_moving = False
        self.motion_threshold = 2.0  # pixels

    def estimate_optical_flow(self, frame):
        """
        Estimate camera motion using Farneback optical flow

        Returns:
            homography: 3x3 transformation matrix (or None)
            is_camera_moving: bool
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.prev_gray is None:
            self.prev_gray = gray
            return None, False

        # Compute dense optical flow
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0
        )

        # Calculate median flow (robust to object motion)
        # Sample grid points to avoid computational cost
        h, w = flow.shape[:2]
        grid_step = 20
        y_coords = np.arange(0, h, grid_step)
        x_coords = np.arange(0, w, grid_step)

        flow_samples = flow[np.ix_(y_coords, x_coords)]
        median_flow = np.median(flow_samples.reshape(-1, 2), axis=0)

        self.camera_motion = median_flow
        self.is_moving = np.linalg.norm(median_flow) > self.motion_threshold

        # Create homography from translation
        if self.is_moving:
            H = np.array([
                [1, 0, -median_flow[0]],
                [0, 1, -median_flow[1]],
                [0, 0, 1]
            ], dtype=np.float32)
        else:
            H = np.eye(3, dtype=np.float32)

        self.prev_gray = gray
        return H, self.is_moving

    def estimate_feature_based(self, frame):
        """
        Estimate camera motion using feature matching + homography

        Returns:
            homography: 3x3 transformation matrix (or None)
            is_camera_moving: bool
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect features
        keypoints, descriptors = self.feature_detector.detectAndCompute(gray, None)

        if self.prev_features is None or descriptors is None:
            self.prev_features = (keypoints, descriptors)
            self.prev_gray = gray
            return None, False

        prev_kp, prev_desc = self.prev_features

        if prev_desc is None or len(keypoints) < 10 or len(prev_kp) < 10:
            self.prev_features = (keypoints, descriptors)
            self.prev_gray = gray
            return None, False

        # Match features
        matches = self.matcher.knnMatch(prev_desc, descriptors, k=2)

        # Apply ratio test (Lowe's)
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)

        if len(good_matches) < 10:
            self.prev_features = (keypoints, descriptors)
            self.prev_gray = gray
            return None, False

        # Extract matched points
        src_pts = np.float32([prev_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Find homography using RANSAC
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if H is None:
            self.prev_features = (keypoints, descriptors)
            self.prev_gray = gray
            return None, False

        # Check if camera is moving (translation component)
        translation = np.array([H[0, 2], H[1, 2]])
        self.camera_motion = translation
        self.is_moving = np.linalg.norm(translation) > self.motion_threshold

        # Smooth homography with EMA
        self.homography_buffer.append(H)
        H_smooth = np.mean(self.homography_buffer, axis=0)

        self.prev_features = (keypoints, descriptors)
        self.prev_gray = gray

        return H_smooth, self.is_moving

    def compensate(self, frame):
        """
        Estimate camera motion and return homography

        Returns:
            homography: 3x3 matrix or None
            is_camera_moving: bool
        """
        if self.method == 'optical_flow':
            return self.estimate_optical_flow(frame)
        else:
            return self.estimate_feature_based(frame)

    def transform_bbox(self, bbox, homography):
        """
        Transform bounding box coordinates using homography

        Args:
            bbox: [x1, y1, x2, y2]
            homography: 3x3 transformation matrix

        Returns:
            transformed_bbox: [x1, y1, x2, y2]
        """
        if homography is None:
            return bbox

        # Get bbox corners
        x1, y1, x2, y2 = bbox
        corners = np.array([
            [x1, y1],
            [x2, y1],
            [x2, y2],
            [x1, y2]
        ], dtype=np.float32).reshape(-1, 1, 2)

        # Transform corners
        transformed = cv2.perspectiveTransform(corners, homography)

        # Get new bounding box
        x_coords = transformed[:, 0, 0]
        y_coords = transformed[:, 0, 1]

        new_bbox = [
            np.min(x_coords),
            np.min(y_coords),
            np.max(x_coords),
            np.max(y_coords)
        ]

        return new_bbox

    def get_motion_info(self):
        """
        Get current camera motion information

        Returns:
            dict with motion statistics
        """
        return {
            'dx': float(self.camera_motion[0]),
            'dy': float(self.camera_motion[1]),
            'magnitude': float(np.linalg.norm(self.camera_motion)),
            'is_moving': self.is_moving,
            'method': self.method
        }


if __name__ == "__main__":
    # Test camera motion compensation
    logging.basicConfig(level=logging.INFO)

    print("Testing Camera Motion Compensation...")

    # Test optical flow
    compensator_flow = CameraMotionCompensator(method='optical_flow')

    # Test feature-based
    compensator_feat = CameraMotionCompensator(method='feature_based')

    # Create dummy frames
    frame1 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    frame2 = np.roll(frame1, shift=10, axis=1)  # Simulate camera pan

    # Test
    H1, moving1 = compensator_flow.compensate(frame1)
    H2, moving2 = compensator_flow.compensate(frame2)

    print(f"✅ Optical flow: {'Camera moving' if moving2 else 'Camera static'}")
    print(f"   Motion: {compensator_flow.get_motion_info()}")

    print("✅ Camera motion compensation ready!")

