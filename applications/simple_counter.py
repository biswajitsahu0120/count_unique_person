#!/usr/bin/env python3
"""
Simplified Person Counter - 24 Hour Recount Window
- Detects unique people entering the frame
- Counts them once per 24-hour window
- Captures photos automatically with date-organized folders
- Logs events to date-organized CSV files
- After 24 hours, same person can be counted again as new entry
"""

import cv2
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO
import logging
import hashlib
from collections import defaultdict
import sys

# Add utilities to path for face recognition
sys.path.append(str(Path(__file__).parent.parent / 'utilities'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class SimplifiedPersonCounter:
    """Person counter with 24-hour recount window and date-organized storage"""

    def __init__(self, model_name='yolov8n.pt', confidence_threshold=0.5, recount_hours=24, enable_face_recognition=False, face_tolerance=0.6):
        """
        Initialize counter

        Args:
            model_name: YOLOv8 model (nano for speed)
            confidence_threshold: Detection confidence (0-1) - increased to 0.75 for fewer false positives
            recount_hours: Hours before same person can be recounted (default 24)
            enable_face_recognition: Enable face recognition authorization (default False)
            face_tolerance: Face match threshold for recognition (lower = stricter, default 0.6)
        """
        logger.info("🔄 Initializing Person Counter...")

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self.recount_hours = recount_hours
        self.recount_seconds = recount_hours * 3600

        # Face Recognition Module (optional)
        self.enable_face_recognition = enable_face_recognition
        self.face_recognizer = None
        if enable_face_recognition:
            try:
                # Try OpenCV-based face recognition first (no dlib dependency)
                try:
                    from face_recognition_opencv import FaceRecognitionAuth
                    self.face_recognizer = FaceRecognitionAuth(
                        known_faces_dir='known_faces',
                        tolerance=face_tolerance,
                        use_dnn=False  # Use Haar Cascade for speed
                    )
                    logger.info("✅ Face Recognition ENABLED (OpenCV)")
                except ImportError:
                    # Fallback to dlib-based if available
                    from face_recognition_auth import FaceRecognitionAuth
                    self.face_recognizer = FaceRecognitionAuth(
                        known_faces_dir='known_faces',
                        tolerance=face_tolerance,
                        model='hog'
                    )
                    logger.info("✅ Face Recognition ENABLED (dlib)")

                logger.info(f"   Known faces loaded: {len(self.face_recognizer.known_face_names)}")
            except Exception as e:
                logger.warning(f"⚠️  Face Recognition failed to initialize: {e}")
                logger.warning("   Continuing without face recognition")
                self.enable_face_recognition = False

        # Detection filtering thresholds - RELAXED for better detection
        self.min_bbox_area = 3000  # Minimum area: 55x55 pixels (RELAXED)
        self.max_bbox_area_ratio = 0.80  # Max 80% of frame (RELAXED)
        self.min_aspect_ratio = 0.3  # Min height/width ratio (RELAXED)
        self.max_aspect_ratio = 3.5  # Max height/width ratio (RELAXED)
        self.min_height_pixels = 60  # Minimum person height (RELAXED)
        self.min_width_pixels = 30  # Minimum person width (RELAXED)
        self.edge_margin = 20  # Pixels from edge (REDUCED - less strict)
        self.min_completeness = 0.8  # Require 80% of body to be in frame
        self.temporal_consistency_frames = 3  # Track detections (REDUCED for faster counting)
        self.detection_history = {}  # Store recent detections for consistency checking
        self.stable_frame_count = {}  # Count stable detections before capture

        # Get current date for organizing files by date
        self.current_date = datetime.now().strftime('%Y-%m-%d')

        # Setup directories with date organization
        self.data_dir = Path('data')
        self.date_dir = self.data_dir / self.current_date
        self.captures_dir = self.date_dir / 'captures'

        self.data_dir.mkdir(exist_ok=True)
        self.date_dir.mkdir(exist_ok=True)
        self.captures_dir.mkdir(exist_ok=True)

        # CSV file for logging (organized by date)
        self.csv_path = self.date_dir / 'events.csv'
        self.init_csv()

        # Batch CSV writes for performance
        self.csv_buffer = []
        self.csv_batch_size = 5  # Write to CSV every 5 detections

        # Tracking: {person_id: {'first_seen': datetime, 'counted': bool, 'count_number': int, 'first_count_time': datetime}}
        self.tracked_people = {}
        self.unique_count = 0
        self.next_person_id = 1

        # Duplicate image detection - RELAXED thresholds
        self.image_hashes = {}  # {track_id: [hash1, hash2, ...]}
        self.duplicate_threshold = 12  # Hamming distance threshold (RELAXED from 8)
        self.max_images_per_person = 3  # Maximum images to save per person
        self.min_capture_interval = 2  # Minimum seconds between captures (REDUCED from 3)
        self.last_capture_time = {}  # {track_id: last_capture_datetime}

        # Frame-level tracking for density
        self.current_frame_people_count = 0  # People in current frame
        self.max_density = 0  # Max people seen in a single frame

        # Display stats and performance optimization
        self.frame_count = 0
        self.fps_count = 0
        self.fps_time = datetime.now()
        self.current_fps = 0.0
        self.skip_frames = 1  # Process every frame for better quality (changed from 2)
        self.frame_skip_counter = 0
        self.last_detections = []  # Cache for skipped frames

        logger.info("✅ Counter initialized")
        logger.info(f"📅 Date: {self.current_date}")
        logger.info(f"⏱️  Recount window: {recount_hours} hours")
        logger.info(f"📁 Storage: {self.date_dir}/")
        logger.info(f"⚡ Performance: Frame skipping enabled (every {self.skip_frames} frames)")
        logger.info("🎯 Detection Filters:")
        logger.info(f"   • Confidence threshold: {confidence_threshold}")
        logger.info(f"   • Min bbox area: {self.min_bbox_area}px² (RELAXED)")
        logger.info(f"   • Aspect ratio: {self.min_aspect_ratio:.1f} to {self.max_aspect_ratio:.1f}")
        logger.info(f"   • Min height: {self.min_height_pixels}px (RELAXED)")
        logger.info(f"   • Edge margin: DISABLED (accept all positions)")
        logger.info("   • NMS IoU threshold: 0.3")
        logger.info(f"   • Temporal consistency: {self.temporal_consistency_frames} frames")
        logger.info("📸 Image Quality & Duplicate Detection:")
        logger.info(f"   • Min sharpness: 80.0 (RELAXED)")
        logger.info(f"   • JPEG quality: 95")
        logger.info(f"   • Duplicate threshold: {self.duplicate_threshold} bits (RELAXED)")
        logger.info(f"   • Similarity threshold: 90%")
        logger.info(f"   • Max images per person: {self.max_images_per_person}")
        logger.info(f"   • Min capture interval: {self.min_capture_interval}s (RELAXED)")
        logger.info("👥 Density Tracking:")
        logger.info(f"   • Real-time people count in frame")
        logger.info(f"   • Density visualization enabled")
        logger.info("")

        # Load existing count from today's data
        self.load_existing_count()

    def load_existing_count(self):
        """Load existing person count from today's CSV/images to avoid duplicates on restart"""
        try:
            # Check if CSV exists and has data
            if self.csv_path.exists():
                df = pd.read_csv(self.csv_path)
                if len(df) > 0:
                    # Get the highest count number from CSV
                    max_count = df['count_number'].max()
                    self.unique_count = int(max_count)
                    self.next_person_id = int(df['person_id'].max()) + 1

                    logger.info(f"📊 Restored from existing data:")
                    logger.info(f"   • Previous count: {self.unique_count} people")
                    logger.info(f"   • Next person ID: {self.next_person_id}")
                    logger.info(f"   • CSV entries: {len(df)}")

                    # Verify with images in captures folder
                    image_count = len(list(self.captures_dir.glob('*.jpg')))
                    logger.info(f"   • Images in folder: {image_count}")

                    if image_count != len(df):
                        logger.warning(f"⚠️  Mismatch: CSV has {len(df)} entries but folder has {image_count} images")

                    return

            # Check if images exist but no CSV (corrupted scenario)
            images = list(self.captures_dir.glob('person_*.jpg'))
            if len(images) > 0:
                # Parse filenames to get max count: person_XXX_id_Y_time.jpg
                max_count = 0
                max_id = 0
                for img in images:
                    try:
                        # Parse: person_001_id_1_220802.jpg
                        parts = img.stem.split('_')
                        if len(parts) >= 4:
                            count_num = int(parts[1])
                            person_id = int(parts[3])
                            max_count = max(max_count, count_num)
                            max_id = max(max_id, person_id)
                    except:
                        continue

                if max_count > 0:
                    self.unique_count = max_count
                    self.next_person_id = max_id + 1
                    logger.info(f"📊 Restored from images (CSV missing):")
                    logger.info(f"   • Previous count: {self.unique_count} people")
                    logger.info(f"   • Next person ID: {self.next_person_id}")
                    logger.info(f"   • Images found: {len(images)}")
                    return

            # No existing data
            logger.info(f"📊 Starting fresh: No existing data for today")

        except Exception as e:
            logger.warning(f"⚠️  Error loading existing count: {e}")
            logger.info(f"📊 Starting from 0")

    def init_csv(self):
        """Initialize CSV file for current date"""
        if not self.csv_path.exists():
            df = pd.DataFrame(columns=['timestamp', 'person_id', 'image_path', 'confidence', 'count_number'])
            df.to_csv(self.csv_path, index=False)
            logger.info(f"📋 CSV log created: {self.csv_path}")

    def validate_bbox(self, x1, y1, x2, y2, frame_h, frame_w, confidence):
        """
        Validate bounding box to filter out false positives
        SIMPLIFIED - Only essential checks, no position restrictions
        Returns: (is_valid, reason)
        """
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        bbox_area = bbox_width * bbox_height

        # Check 1: Minimum area
        if bbox_area < self.min_bbox_area:
            return False, f"too_small({bbox_area:.0f}<{self.min_bbox_area})"

        # Check 2: Minimum width
        if bbox_width < self.min_width_pixels:
            return False, f"too_narrow({bbox_width:.0f}<{self.min_width_pixels})"

        # Check 3: Minimum height
        if bbox_height < self.min_height_pixels:
            return False, f"too_short({bbox_height:.0f}<{self.min_height_pixels})"

        # Check 4: Aspect ratio
        if bbox_width == 0 or not self._check_aspect_ratio(bbox_height, bbox_width):
            aspect = bbox_height / bbox_width if bbox_width > 0 else 0
            return False, f"bad_aspect({aspect:.2f})"

        # Check 5: Confidence score
        if confidence < self.confidence_threshold:
            return False, f"low_confidence({confidence:.2f}<{self.confidence_threshold})"

        # All checks passed - ACCEPT ANY SIZE, ANY POSITION!
        return True, "valid"

    def _check_aspect_ratio(self, height, width):
        """Helper to check if aspect ratio is valid for human shape"""
        if width == 0:
            return False
        aspect_ratio = height / width
        return self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio

    def calculate_perceptual_hash(self, image, hash_size=8):
        """
        Calculate perceptual hash (pHash) of an image for duplicate detection
        Uses DCT-based hashing which is robust to minor variations

        Args:
            image: Input image
            hash_size: Size of the hash (default 8x8 = 64 bits)

        Returns:
            Binary hash string
        """
        if image is None or image.size == 0:
            return None

        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Resize to 32x32 (even dimensions for DCT, then we'll downsample)
        # DCT requires even dimensions
        resized = cv2.resize(gray, (32, 32))

        # Apply DCT (Discrete Cosine Transform)
        dct = cv2.dct(np.float32(resized))

        # Extract top-left 8x8 corner (low frequencies)
        dct_low = dct[:hash_size, :hash_size]

        # Calculate median
        median = np.median(dct_low)

        # Generate binary hash
        binary_hash = dct_low > median

        # Convert to binary string for compact storage
        hash_string = ''.join(['1' if x else '0' for x in binary_hash.flatten()])
        return hash_string

    def hamming_distance(self, hash1, hash2):
        """
        Calculate Hamming distance between two hashes
        Returns number of different bits
        """
        if hash1 is None or hash2 is None:
            return float('inf')

        if len(hash1) != len(hash2):
            return float('inf')

        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    def calculate_image_similarity(self, img1, img2):
        """
        Calculate structural similarity between two images
        Returns similarity score (0-1, higher = more similar)
        """
        if img1 is None or img2 is None or img1.size == 0 or img2.size == 0:
            return 0.0

        # Resize both to same size for comparison
        size = (64, 64)

        # Convert to grayscale
        if len(img1.shape) == 3:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        else:
            gray1 = img1

        if len(img2.shape) == 3:
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            gray2 = img2

        # Resize
        gray1 = cv2.resize(gray1, size)
        gray2 = cv2.resize(gray2, size)

        # Calculate mean squared error
        mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)

        # Convert to similarity score (0-1)
        # Lower MSE = higher similarity
        if mse == 0:
            return 1.0

        # Normalize MSE to similarity (inverse relationship)
        similarity = 1.0 / (1.0 + mse / 1000.0)
        return similarity

    def is_duplicate_image(self, image, track_id):
        """
        Check if image is a duplicate using BOTH perceptual hash AND structural similarity

        Args:
            image: Image to check
            track_id: Person track ID

        Returns:
            (is_duplicate, min_distance, saved_count)
        """
        # Calculate hash of current image
        current_hash = self.calculate_perceptual_hash(image)

        if current_hash is None:
            return True, 0, 0  # Invalid image, consider duplicate

        # Initialize hash list for this person if needed
        if track_id not in self.image_hashes:
            self.image_hashes[track_id] = []

        saved_count = len(self.image_hashes[track_id])

        # Check if we've reached max images per person
        if saved_count >= self.max_images_per_person:
            return True, 0, saved_count

        # If no previous hashes, not a duplicate
        if saved_count == 0:
            return False, float('inf'), 0

        # Compare with all previous hashes using BOTH methods
        min_distance = float('inf')
        max_similarity = 0.0

        for prev_hash_data in self.image_hashes[track_id]:
            prev_hash = prev_hash_data['hash']
            prev_image = prev_hash_data.get('thumbnail')  # Store thumbnail for comparison

            # Method 1: Hamming distance (pHash)
            distance = self.hamming_distance(current_hash, prev_hash)
            min_distance = min(min_distance, distance)

            # Method 2: Structural similarity (if thumbnail available)
            if prev_image is not None:
                similarity = self.calculate_image_similarity(image, prev_image)
                max_similarity = max(max_similarity, similarity)

        # Duplicate if EITHER:
        # 1. Hamming distance <= threshold (8 bits)
        # 2. Structural similarity >= 0.90 (90% similar)
        is_dup_hash = min_distance <= self.duplicate_threshold
        is_dup_similarity = max_similarity >= 0.90

        is_dup = is_dup_hash or is_dup_similarity

        return is_dup, min_distance, saved_count

    def store_image_hash(self, image, track_id):
        """Store the hash and thumbnail of a saved image for better duplicate detection"""
        image_hash = self.calculate_perceptual_hash(image)
        if image_hash:
            if track_id not in self.image_hashes:
                self.image_hashes[track_id] = []

            # Create thumbnail for structural similarity comparison
            thumbnail = cv2.resize(image, (64, 64)) if image is not None and image.size > 0 else None

            self.image_hashes[track_id].append({
                'hash': image_hash,
                'thumbnail': thumbnail,
                'timestamp': datetime.now()
            })

    def check_temporal_consistency(self, det_id, detection_bbox):
        """
        Check if detection is consistent across frames (reduces jitter false positives)
        Returns: True if detection is consistent or new, False if likely false positive
        """
        if det_id not in self.detection_history:
            self.detection_history[det_id] = []

        # Store this detection
        self.detection_history[det_id].append(detection_bbox)

        # Keep only recent history
        max_history = self.temporal_consistency_frames
        if len(self.detection_history[det_id]) > max_history:
            self.detection_history[det_id] = self.detection_history[det_id][-max_history:]

        # If we have enough history, check consistency
        if len(self.detection_history[det_id]) >= 2:
            # Check if positions are within reasonable range
            bboxes = self.detection_history[det_id]
            for i in range(1, len(bboxes)):
                prev_bbox = bboxes[i-1]
                curr_bbox = bboxes[i]

                # Calculate center movement
                prev_center_x = (prev_bbox[0] + prev_bbox[2]) / 2
                prev_center_y = (prev_bbox[1] + prev_bbox[3]) / 2
                curr_center_x = (curr_bbox[0] + curr_bbox[2]) / 2
                curr_center_y = (curr_bbox[1] + curr_bbox[3]) / 2

                movement = np.sqrt((curr_center_x - prev_center_x)**2 +
                                 (curr_center_y - prev_center_y)**2)

                # If too much jitter in single frame (likely false positive)
                if movement > 200:  # 200 pixels max reasonable movement
                    return False

        return True

    def calculate_iou(self, bbox1, bbox2):
        """Calculate Intersection over Union (IoU) between two bounding boxes"""
        x1_i, y1_i, x2_i, y2_i = bbox1
        x1_k, y1_k, x2_k, y2_k = bbox2

        # Intersection
        xi1 = max(x1_i, x1_k)
        yi1 = max(y1_i, y1_k)
        xi2 = min(x2_i, x2_k)
        yi2 = min(y2_i, y2_k)

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)

        # Union
        det_i_area = (x2_i - x1_i) * (y2_i - y1_i)
        kept_det_area = (x2_k - x1_k) * (y2_k - y1_k)
        union_area = det_i_area + kept_det_area - inter_area

        # IoU
        return inter_area / union_area if union_area > 0 else 0

    def apply_nms_filtering(self, detections, iou_threshold=0.3):
        """
        Apply Non-Maximum Suppression to remove overlapping detections
        Keeps only the highest confidence detection in overlapping regions
        """
        if len(detections) <= 1:
            return detections

        # Sort by confidence (highest first)
        sorted_dets = sorted(enumerate(detections), key=lambda x: x[1]['confidence'], reverse=True)

        keep_indices = []
        for idx_i, det_i in sorted_dets:
            should_keep = True

            # Check against already kept detections
            for kept_idx in keep_indices:
                kept_det = detections[kept_idx]

                # Calculate IoU
                iou = self.calculate_iou(det_i['bbox'], kept_det['bbox'])

                # If too much overlap, discard this detection
                if iou > iou_threshold:
                    should_keep = False
                    break

            if should_keep:
                keep_indices.append(idx_i)

        # Return filtered detections in original order
        filtered_dets = [detections[i] for i in sorted(keep_indices)]
        return filtered_dets



    def detect_persons(self, frame):
        """Detect persons in frame using YOLOv8 - with advanced filtering for false positive reduction"""
        h, w = frame.shape[:2]
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)

        detections = []

        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:  # class 0 = person
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf)

                    # FILTER 1: Validate bounding box geometry
                    is_valid, reason = self.validate_bbox(x1, y1, x2, y2, h, w, confidence)
                    if not is_valid:
                        continue

                    # Create detection ID for temporal consistency checking
                    det_id = f"{int(x1)}_{int(y1)}_{int(x2)}_{int(y2)}"

                    # FILTER 2: Check temporal consistency (reduces jitter false positives)
                    if not self.check_temporal_consistency(det_id, (x1, y1, x2, y2)):
                        continue

                    # Expand bounding box to capture full body (not just face)
                    bbox_width = x2 - x1
                    bbox_height = y2 - y1

                    pad_left = int(bbox_width * 0.15)
                    pad_right = int(bbox_width * 0.15)
                    pad_top = int(bbox_height * 0.20)
                    pad_bottom = int(bbox_height * 0.10)

                    x1_expanded = max(0, int(x1) - pad_left)
                    y1_expanded = max(0, int(y1) - pad_top)
                    x2_expanded = min(w, int(x2) + pad_right)
                    y2_expanded = min(h, int(y2) + pad_bottom)

                    center_x = (x1_expanded + x2_expanded) / 2
                    center_y = (y1_expanded + y2_expanded) / 2

                    detections.append({
                        'bbox': (x1_expanded, y1_expanded, x2_expanded, y2_expanded),
                        'center': (center_x, center_y),
                        'confidence': confidence,
                        'original_bbox': (int(x1), int(y1), int(x2), int(y2))
                    })

        # FILTER 3: Apply NMS to remove overlapping detections
        detections = self.apply_nms_filtering(detections, iou_threshold=0.3)

        return detections


    def calculate_adaptive_threshold(self, person_info):
        """Calculate adaptive distance threshold based on person size"""
        prev_bbox = person_info.get('prev_bbox')
        if not prev_bbox:
            return 120

        prev_width = prev_bbox[2] - prev_bbox[0]
        prev_height = prev_bbox[3] - prev_bbox[1]
        max_size = max(prev_width, prev_height)

        # Threshold is 50% of person size, min 80px, max 200px
        threshold = max_size * 0.5
        return max(80, min(200, threshold))

    def find_best_match(self, person_info, unmatched_dets, detections):
        """Find best matching detection for a tracked person"""
        best_dist = float('inf')
        best_det_idx = -1

        for det_idx in unmatched_dets:
            det = detections[det_idx]
            dist = np.sqrt((det['center'][0] - person_info['center'][0])**2 +
                          (det['center'][1] - person_info['center'][1])**2)

            if dist < best_dist:
                best_dist = dist
                best_det_idx = det_idx

        return best_det_idx, best_dist

    def match_detections(self, detections):
        """
        Simple centroid-based matching for detected persons
        Returns: list of (person_id, detection_index) tuples
        """
        matched = []
        unmatched_dets = list(range(len(detections)))

        # Try to match with existing tracked people
        for track_id, person_info in self.tracked_people.items():
            if 'center' not in person_info:
                continue

            best_det_idx, best_dist = self.find_best_match(person_info, unmatched_dets, detections)
            adaptive_threshold = self.calculate_adaptive_threshold(person_info)

            if best_det_idx >= 0 and best_dist < adaptive_threshold:
                matched.append((track_id, best_det_idx))
                unmatched_dets.remove(best_det_idx)

        # Create new IDs for unmatched detections
        for det_idx in unmatched_dets:
            new_id = self.next_person_id
            self.next_person_id += 1
            matched.append((new_id, det_idx))

        return matched, detections

    def should_count(self, person_id):
        """Check if person should be counted (respects 24-hour window)"""
        if person_id not in self.tracked_people:
            return True

        person = self.tracked_people[person_id]

        if not person.get('counted', False):
            return True

        # Check if 24-hour recount window has passed
        first_count_time = person.get('first_count_time')
        if first_count_time:
            time_since = (datetime.now() - first_count_time).total_seconds()
            if time_since >= self.recount_seconds:
                logger.info(f"🔄 Person {person_id} eligible for recount (24h window passed)")
                return True

        return False

    def log_event(self, person_id, count_number, image_path, confidence):
        """Log detection event to CSV - optimized with batch writes"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Add to buffer instead of writing immediately
        self.csv_buffer.append({
            'timestamp': timestamp,
            'person_id': person_id,
            'image_path': image_path,
            'confidence': f"{confidence:.2f}",
            'count_number': count_number
        })

        # Batch write to CSV
        if len(self.csv_buffer) >= self.csv_batch_size:
            self.flush_csv_buffer()

        logger.info(f"👤 Person #{count_number} detected (ID: {person_id})")

    def flush_csv_buffer(self):
        """Flush buffered CSV writes to disk - called periodically"""
        if not self.csv_buffer:
            return

        try:
            df = pd.read_csv(self.csv_path)
            df = pd.concat([df, pd.DataFrame(self.csv_buffer)], ignore_index=True)
            df.to_csv(self.csv_path, index=False)
            self.csv_buffer = []
        except Exception as e:
            logger.warning(f"Error writing CSV: {e}")

    def calculate_sharpness(self, image):
        """Calculate image sharpness using Laplacian variance"""
        if image is None or image.size == 0:
            return 0.0

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Calculate Laplacian variance (higher = sharper)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var

    def is_image_quality_good(self, image, min_sharpness=100.0):
        """
        Check if image has good quality (not blurry)

        Args:
            image: Image to check
            min_sharpness: Minimum acceptable sharpness (default 100)

        Returns:
            (is_good, sharpness_score)
        """
        if image is None or image.size == 0:
            return False, 0.0

        # Check image size
        h, w = image.shape[:2]
        if h < 80 or w < 60:
            return False, 0.0

        # Check sharpness
        sharpness = self.calculate_sharpness(image)
        is_good = sharpness >= min_sharpness

        return is_good, sharpness

    def capture_person(self, frame, person_id, count_number, min_sharpness=80.0, max_jpeg_quality=95):
        """
        Capture and save person photo with quality validation and duplicate detection
        Only saves sharp, clear, non-duplicate images with time interval
        """
        # STEP 1: Check time interval (prevent rapid captures)
        current_time = datetime.now()
        if person_id in self.last_capture_time:
            time_since_last = (current_time - self.last_capture_time[person_id]).total_seconds()
            if time_since_last < self.min_capture_interval:
                return None

        # STEP 2: Validate image quality
        is_good, sharpness = self.is_image_quality_good(frame, min_sharpness)

        if not is_good:
            return None

        # STEP 3: Check for duplicate
        is_dup, distance, saved_count = self.is_duplicate_image(frame, person_id)

        if is_dup:
            return None

        # STEP 4: Save the image
        timestamp = datetime.now().strftime('%H%M%S')
        image_name = f"person_{count_number:03d}_id_{person_id}_{timestamp}.jpg"
        image_path = self.captures_dir / image_name

        # Save with high quality JPEG settings
        cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, max_jpeg_quality])

        # STEP 5: Store hash and update last capture time
        self.store_image_hash(frame, person_id)
        self.last_capture_time[person_id] = current_time

        logger.info(f"📸 Photo saved: {image_name}")
        return str(image_path)

    def update_tracked_person(self, track_id, detection):
        """Initialize or update a tracked person"""
        if track_id not in self.tracked_people:
            self.tracked_people[track_id] = {
                'first_seen': datetime.now(),
                'counted': False,
                'count_number': None,
                'first_count_time': None,
                'prev_bbox': None
            }

        self.tracked_people[track_id]['center'] = detection['center']
        self.tracked_people[track_id]['confidence'] = detection['confidence']
        self.tracked_people[track_id]['prev_bbox'] = detection['bbox']

    def process_new_person(self, frame, track_id, detection, is_key_frame=True):
        """Process and count a newly detected person - only captures from key frames with quality check"""
        if self.should_count(track_id):
            # Initialize stability counter if needed
            if track_id not in self.stable_frame_count:
                self.stable_frame_count[track_id] = 0

            # Increment stability counter
            self.stable_frame_count[track_id] += 1

            # Require at least 2 stable detections before counting (REDUCED from 3)
            if self.stable_frame_count[track_id] < 2:
                return None

            # Face Recognition Authorization Check (if enabled)
            if self.enable_face_recognition and self.face_recognizer:
                # Extract person region for face recognition
                x1, y1, x2, y2 = detection['bbox']
                person_crop = frame[y1:y2, x1:x2]

                if person_crop.size > 0:
                    # Recognize face in person region
                    face_recs = self.face_recognizer.recognize_faces(person_crop)

                    # Check if any face is recognized and allowed
                    if face_recs:
                        allowed = any(rec['allowed'] for rec in face_recs)
                        if not allowed:
                            # Person detected but NOT ALLOWED - do not count
                            logger.warning(f"❌ Track {track_id}: UNKNOWN PERSON - NOT ALLOWED")
                            return None
                        else:
                            # Log the allowed person
                            allowed_rec = next(rec for rec in face_recs if rec['allowed'])
                            logger.info(f"✅ Track {track_id}: ALLOWED - {allowed_rec['name']}")
                    else:
                        # No face detected in person region - check configuration
                        if hasattr(self, 'require_face_for_counting') and self.require_face_for_counting:
                            logger.warning(f"⚠️  Track {track_id}: No face detected - not counting")
                            return None

            # Only capture from key frames (non-skipped) for best quality
            if is_key_frame:
                # Capture photo with expanded bounding box (full body)
                x1, y1, x2, y2 = detection['bbox']
                crop = frame[y1:y2, x1:x2]

                if crop.size > 0:
                    # Get current count (from shared state if multi-camera, else local)
                    current_count = getattr(self, 'shared_state', self).unique_count

                    # Try to capture with quality check and duplicate detection
                    image_path = self.capture_person(crop, track_id, current_count + 1, min_sharpness=80.0)

                    # ONLY count if photo was successfully saved
                    if image_path:
                        # Increment counter (thread-safe if multi-camera)
                        if hasattr(self, 'shared_state'):
                            # Multi-camera: use shared state with lock
                            with self.db_lock:
                                self.shared_state.unique_count += 1
                                count_num = self.shared_state.unique_count
                        else:
                            # Single camera: use local counter
                            self.unique_count += 1
                            count_num = self.unique_count

                        # Mark as counted in current window
                        self.tracked_people[track_id]['counted'] = True
                        self.tracked_people[track_id]['count_number'] = count_num
                        self.tracked_people[track_id]['first_count_time'] = datetime.now()

                        # Log the successful event
                        self.log_event(track_id, count_num, image_path, detection['confidence'])

                        # Simple clean log message
                        logger.info(f"👤 Person #{count_num} detected (ID: {track_id})")
                        return track_id
                    else:
                        # Photo rejected - DO NOT count, DO NOT log
                        return None
        return None

    def draw_detections(self, frame, matched, detections_list, new_ids):
        """Draw bounding boxes and clean stats table on frame"""
        for track_id, det_idx in matched:
            detection = detections_list[det_idx]
            x1, y1, x2, y2 = detection['bbox']

            # Color: green if newly counted, orange if existing
            color = (0, 255, 0) if track_id in new_ids else (0, 165, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw count number if counted
            if self.tracked_people[track_id]['count_number']:
                count_num = self.tracked_people[track_id]['count_number']
                text = f"#{count_num}"
                # Add background for better text visibility
                cv2.rectangle(frame, (x1, y1 - 25), (x1 + 40, y1), color, -1)
                cv2.putText(frame, text, (x1 + 5, y1 - 8),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw clean stats table (top)
        frame = self.draw_stats_table(frame)

        return frame

    def draw_stats_table(self, frame):
        """Draw a clean table with all statistics"""
        h, w = frame.shape[:2]

        # Draw camera name at top right corner
        camera_name = getattr(self, 'camera_id', 'Camera')
        cam_text = f"📹 {camera_name.upper()}"

        # Measure text size for background
        (text_w, text_h), baseline = cv2.getTextSize(cam_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cam_x = w - text_w - 20
        cam_y = 15

        # Draw background for camera name
        cv2.rectangle(frame, (cam_x - 10, cam_y - text_h - 5),
                     (w - 10, cam_y + baseline + 5), (0, 100, 200), -1)
        cv2.rectangle(frame, (cam_x - 10, cam_y - text_h - 5),
                     (w - 10, cam_y + baseline + 5), (255, 255, 255), 2)

        # Draw camera name text
        cv2.putText(frame, cam_text, (cam_x, cam_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Get density level
        density_level, density_color = self.get_density_level()

        # Table dimensions
        table_width = 350
        table_height = 140
        table_x = 10
        table_y = 10

        # Draw table background (semi-transparent black)
        overlay = frame.copy()
        cv2.rectangle(overlay, (table_x, table_y),
                     (table_x + table_width, table_y + table_height),
                     (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Draw table border
        cv2.rectangle(frame, (table_x, table_y),
                     (table_x + table_width, table_y + table_height),
                     (255, 255, 255), 2)

        # Title
        cv2.putText(frame, "PERSON DETECTION STATS", (table_x + 10, table_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Draw horizontal line after title
        cv2.line(frame, (table_x, table_y + 35),
                (table_x + table_width, table_y + 35), (255, 255, 255), 1)

        # Stats rows
        row_y = table_y + 55
        row_spacing = 25

        # Row 1: Total Unique (use shared state if multi-camera)
        display_count = getattr(self, 'shared_state', self).unique_count
        cv2.putText(frame, f"Total Unique:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{display_count}", (table_x + 250, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Row 2: In Frame
        row_y += row_spacing
        cv2.putText(frame, f"In Frame Now:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{self.current_frame_people_count}", (table_x + 250, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, density_color, 2)

        # Row 3: Density Level
        row_y += row_spacing
        cv2.putText(frame, f"Density:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{density_level}", (table_x + 250, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, density_color, 2)

        # Row 4: FPS
        row_y += row_spacing
        cv2.putText(frame, f"FPS:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{self.current_fps:.1f}", (table_x + 250, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Date info at bottom
        date_text = f"Date: {self.current_date} | 24hr window"
        cv2.putText(frame, date_text, (table_x + 15, table_y + table_height - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

        return frame

    def update_fps_counter(self):
        """Update FPS counter and return current FPS"""
        current_time = datetime.now()
        elapsed = (current_time - self.fps_time).total_seconds()
        self.fps_count += 1

        if elapsed >= 1.0:
            self.current_fps = self.fps_count / elapsed
            self.fps_count = 0
            self.fps_time = current_time

        return self.current_fps

    def update_density_tracking(self, current_count):
        """Update current frame people count"""
        self.current_frame_people_count = current_count

        # Update max density
        if current_count > self.max_density:
            self.max_density = current_count

    def get_density_level(self):
        """Get current density level as text"""
        count = self.current_frame_people_count
        if count == 0:
            return "EMPTY", (100, 100, 100)
        elif count == 1:
            return "LOW", (0, 255, 0)
        elif count <= 3:
            return "MODERATE", (0, 255, 255)
        elif count <= 5:
            return "HIGH", (0, 165, 255)
        else:
            return "CROWDED", (0, 0, 255)

    def draw_fps(self, frame):
        """Draw FPS on frame (not used - now in stats table)"""
        return frame


    def process_frame(self, frame):
        """Process single frame for detection and counting"""
        self.frame_count += 1

        # Performance optimization: skip frames for faster processing
        self.frame_skip_counter += 1
        is_key_frame = False

        if self.frame_skip_counter >= self.skip_frames:
            self.frame_skip_counter = 0
            is_key_frame = True
            # Detect persons only on key frames
            detections = self.detect_persons(frame)
            self.last_detections = detections
        else:
            # Use cached detections for skipped frames
            detections = self.last_detections

        # Match with existing tracks
        matched, detections_list = self.match_detections(detections)

        # Update FPS FIRST (before drawing)
        self.update_fps_counter()

        # Update density tracking (people in current frame)
        self.update_density_tracking(len(matched))

        # Update tracking and counting
        new_ids = set()

        for track_id, det_idx in matched:
            detection = detections_list[det_idx]

            # Update tracked person info
            self.update_tracked_person(track_id, detection)

            # Process new person if should count (only capture on key frames for quality)
            newly_counted = self.process_new_person(frame, track_id, detection, is_key_frame)
            if newly_counted:
                new_ids.add(newly_counted)

        # Face Recognition (if enabled and on key frames)
        face_recognitions = []
        if self.enable_face_recognition and self.face_recognizer and is_key_frame:
            face_recognitions = self.face_recognizer.recognize_faces(frame)

            # Log face recognition events
            for rec in face_recognitions:
                # Log each recognition (throttled internally)
                if not rec['allowed']:
                    self.face_recognizer.log_recognition(rec, frame, save_image=True)
                # Only log allowed faces once per session
                elif not hasattr(self, '_logged_faces'):
                    self._logged_faces = set()
                if rec['allowed'] and rec['person_id'] not in self._logged_faces:
                    self.face_recognizer.log_recognition(rec, frame, save_image=True)
                    self._logged_faces.add(rec['person_id'])

        # Draw detections with stats table (all values updated now)
        frame = self.draw_detections(frame, matched, detections_list, new_ids)

        # Draw face recognition results (if enabled)
        if self.enable_face_recognition and face_recognitions:
            frame = self.face_recognizer.draw_recognition_results(frame, face_recognitions)


        return frame


    def run(self, camera_id=0):
        """Run the counter with live camera feed"""
        cap = cv2.VideoCapture(camera_id)

        if not cap.isOpened():
            logger.error("❌ Failed to open camera")
            return

        logger.info("🎥 Camera opened successfully")
        logger.info("📸 Starting detection...")
        logger.info("⏹️  Press 'q' to quit\n")

        try:
            while True:
                ret, frame = cap.read()

                if not ret:
                    logger.warning("Failed to read frame")
                    break

                # Flip for selfie view
                frame = cv2.flip(frame, 1)

                # Process frame
                frame = self.process_frame(frame)

                # Display
                cv2.imshow('Person Counter - 24hr Recount Window', frame)

                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("\n⏹️  Stopping...")
                    break

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrupted by user")

        finally:
            # Flush any remaining CSV entries
            self.flush_csv_buffer()

            cap.release()
            cv2.destroyAllWindows()

            logger.info("\n" + "="*60)
            logger.info("📊 SESSION SUMMARY")
            logger.info("="*60)
            logger.info(f"✅ Total unique people counted: {self.unique_count}")
            logger.info(f"📺 Total frames processed: {self.frame_count}")
            logger.info(f"📅 Date folder: {self.date_dir}/")
            logger.info("  📄 CSV log: events.csv")
            logger.info("  📸 Photos: captures/")
            logger.info(f"⏱️  Recount window: {self.recount_hours} hours")
            logger.info(f"⚡ Optimizations: Frame skipping (every {self.skip_frames} frames)")
            logger.info("="*60)
            logger.info("Note: After 24 hours, same person will be counted again")
            logger.info("="*60 + "\n")


def main():
    """Main entry point"""
    logger.info("\n" + "="*60)
    logger.info("SIMPLIFIED PERSON COUNTER")
    logger.info("24-Hour Recount Window")
    logger.info("="*60 + "\n")

    counter = SimplifiedPersonCounter(
        model_name='yolov8n.pt',
        confidence_threshold=0.5,
        recount_hours=24
    )

    counter.run(camera_id=0)


if __name__ == '__main__':
    main()

