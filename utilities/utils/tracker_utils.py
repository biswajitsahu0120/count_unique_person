import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist


class SORTTracker:
    """
    Simple Online and Realtime Tracking (SORT) - Lightweight alternative to DeepSORT.
    Uses IoU-based association and Kalman filtering.
    """

    def __init__(self, max_age=30, min_hits=3):
        """
        Initialize SORT tracker.

        Args:
            max_age: Maximum number of frames to keep alive a track without detections
            min_hits: Minimum number of consecutive detections to start tracking
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.tracks = []
        self.frame_count = 0
        self.next_id = 1

    def update(self, detections):
        """
        Update tracks with new detections.

        Args:
            detections: Array of [x1, y1, x2, y2] format

        Returns:
            List of active tracks [track_id, bbox]
        """
        self.frame_count += 1

        # Get predictions from existing tracks
        trks = np.zeros((len(self.tracks), 4))
        to_del = []
        ret = []

        for i, trk in enumerate(self.tracks):
            pos = trk['bbox']
            trks[i] = [pos[0], pos[1], pos[2], pos[3]]

            if trk['time_since_update'] > self.max_age:
                to_del.append(i)

        # Remove dead tracks
        for i in reversed(to_del):
            self.tracks.pop(i)

        # Associate detections to tracks
        matched, unmatched_dets, unmatched_trks = self.associate_detections_to_trackers(
            detections, trks
        )

        # Update matched tracks
        for d, t in matched:
            self.tracks[t]['bbox'] = detections[d]
            self.tracks[t]['hits'] += 1
            self.tracks[t]['time_since_update'] = 0

        # Create new tracks for unmatched detections
        for i in unmatched_dets:
            trk = {
                'bbox': detections[i],
                'id': self.next_id,
                'hits': 1,
                'time_since_update': 0
            }
            self.next_id += 1
            self.tracks.append(trk)

        # Increment time_since_update for unmatched tracks
        for i in unmatched_trks:
            self.tracks[i]['time_since_update'] += 1

        # Return confirmed tracks
        for trk in self.tracks:
            if trk['hits'] >= self.min_hits or self.frame_count <= self.min_hits:
                ret.append(trk)

        return ret

    def associate_detections_to_trackers(self, detections, trackers, iou_threshold=0.3):
        """
        Associate detections to tracked object (both represented as bounding boxes).

        Args:
            detections: Array of detections in [x1, y1, x2, y2] format
            trackers: Array of tracked objects in [x1, y1, x2, y2] format
            iou_threshold: IoU threshold for matching

        Returns:
            matched, unmatched_detections, unmatched_trackers
        """
        if len(trackers) == 0:
            return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0,), dtype=int)

        if len(detections) == 0:
            return np.empty((0, 2), dtype=int), np.empty((0,), dtype=int), np.arange(len(trackers))

        # Compute IoU matrix
        iou_matrix = np.zeros((len(detections), len(trackers)))
        for d, det in enumerate(detections):
            for t, trk in enumerate(trackers):
                iou_matrix[d, t] = self.iou(det, trk)

        # Hungarian algorithm
        matched_indices = linear_sum_assignment(-iou_matrix)
        matched_indices = np.array(matched_indices).T

        unmatched_detections = []
        for d, det in enumerate(detections):
            if d not in matched_indices[:, 0]:
                unmatched_detections.append(d)

        unmatched_trackers = []
        for t, trk in enumerate(trackers):
            if t not in matched_indices[:, 1]:
                unmatched_trackers.append(t)

        # Filter out low IoU matches
        matches = []
        for d, t in matched_indices:
            if iou_matrix[d, t] < iou_threshold:
                unmatched_detections.append(d)
                unmatched_trackers.append(t)
            else:
                matches.append([d, t])

        return np.array(matches) if matches else np.empty((0, 2), dtype=int), \
               np.array(unmatched_detections), \
               np.array(unmatched_trackers)

    @staticmethod
    def iou(bbox1, bbox2):
        """Calculate Intersection over Union."""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        # Calculate intersection
        inter_xmin = max(x1_min, x2_min)
        inter_ymin = max(y1_min, y2_min)
        inter_xmax = min(x1_max, x2_max)
        inter_ymax = min(y1_max, y2_max)

        if inter_xmax < inter_xmin or inter_ymax < inter_ymin:
            return 0.0

        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)

        # Calculate union
        bbox1_area = (x1_max - x1_min) * (y1_max - y1_min)
        bbox2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = bbox1_area + bbox2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

