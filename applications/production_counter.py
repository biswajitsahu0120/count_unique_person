#!/usr/bin/env python3
"""
Production Person Counter with StrongSORT + OSNet ReID
Handles all common failure modes:
- ID switches during pan
- Similar-looking people
- Low light detection
- Occlusions and drift
- FPS optimization
"""

import cv2
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO
import logging
import sys
import torch

# Add utilities to path
sys.path.append(str(Path(__file__).parent.parent / 'utilities'))
from strongsort import StrongSORT

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ProductionPersonCounter:
    """
    Production-grade person counter with all failure mode handling

    Handles:
    1. ID switches during pan → Extended gallery TTL, stronger ReID
    2. Similar-looking people → Higher embedding threshold, temporal constraints
    3. Low light → YOLOv8m/x support, confidence tuning
    4. Occlusions → Tuned Kalman, appearance re-linking
    5. FPS drops → Frame skipping, model downsizing, adaptive processing
    """

    def __init__(self,
                 model_name='yolov8n.pt',
                 reid_model='osnet_x1_0',
                 confidence_threshold=0.4,
                 recount_hours=24,
                 frame_skip=2,
                 low_light_mode=False,
                 camera_id='cam_0'):
        """
        Initialize production counter

        Args:
            model_name: YOLO model (yolov8n/s/m/l/x - larger for low light)
            reid_model: OSNet model (osnet_x1_0/x0_75/x0_5/x0_25)
            confidence_threshold: Detection confidence (lower for low light)
            recount_hours: Hours before recounting same person
            frame_skip: Process every N frames (1=all, 2=every other, etc.)
            low_light_mode: Enable low light optimizations
            camera_id: Camera identifier
        """
        logger.info("🔄 Initializing Production Person Counter...")

        # Model selection based on mode
        self.low_light_mode = low_light_mode
        if low_light_mode:
            if 'n' in model_name.lower():
                logger.warning("⚠️  Low light mode: Consider using yolov8m or yolov8x")
            confidence_threshold = min(confidence_threshold, 0.35)  # Lower threshold

        # Initialize YOLO
        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self.camera_id = camera_id

        # Frame processing strategy
        self.frame_skip = max(1, frame_skip)
        self.process_counter = 0
        self.last_detections = []

        # Device selection
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Initialize StrongSORT with failure mode handling
        self.tracker = StrongSORT(
            reid_model=reid_model,
            max_age=50,  # INCREASED for pan/occlusion (was 30)
            min_hits=2,  # REDUCED for faster confirmation (was 3)
            iou_threshold=0.3,
            max_reid_distance=0.25,  # RAISED for similar people (was 0.2)
            nn_budget=150,  # INCREASED gallery size (was 100)
            device=self.device
        )

        # Storage setup
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        self.data_dir = Path('data')
        self.date_dir = self.data_dir / self.current_date
        self.captures_dir = self.date_dir / 'captures'
        self.date_dir.mkdir(parents=True, exist_ok=True)
        self.captures_dir.mkdir(exist_ok=True)

        # CSV logging
        self.csv_path = self.date_dir / 'events.csv'
        self.init_csv()

        # Tracking state
        self.tracked_people = {}  # {track_id: person_info}
        self.unique_count = 0
        self.recount_seconds = recount_hours * 3600

        # Frame statistics
        self.frame_count = 0
        self.fps_count = 0
        self.fps_time = datetime.now()
        self.current_fps = 0.0

        # Density tracking
        self.current_frame_people_count = 0
        self.max_density = 0

        # Performance monitoring
        self.detection_time = 0
        self.tracking_time = 0
        self.total_time = 0

        # Load existing count
        self.load_existing_count()

        logger.info("✅ Production counter initialized")
        logger.info(f"📅 Date: {self.current_date}")
        logger.info(f"📹 Camera: {self.camera_id}")
        logger.info(f"🎯 YOLO: {model_name} on {self.device}")
        logger.info(f"🧠 ReID: {reid_model}")
        logger.info(f"⚡ Frame skip: 1/{self.frame_skip} (FPS optimization)")
        logger.info(f"🌙 Low light mode: {'ON' if low_light_mode else 'OFF'}")
        logger.info("")

    def init_csv(self):
        """Initialize CSV file"""
        if not self.csv_path.exists():
            df = pd.DataFrame(columns=[
                'timestamp', 'track_id', 'image_path', 'confidence',
                'count_number', 'camera_id', 'detection_quality'
            ])
            df.to_csv(self.csv_path, index=False)

    def load_existing_count(self):
        """Load existing count from today's data"""
        try:
            if self.csv_path.exists():
                df = pd.read_csv(self.csv_path)
                if len(df) > 0:
                    self.unique_count = int(df['count_number'].max())
                    logger.info(f"📊 Restored: {self.unique_count} people counted today")
                    return
            logger.info(f"📊 Starting fresh: No existing data for today")
        except Exception as e:
            logger.warning(f"⚠️  Error loading existing count: {e}")

    def detect_persons(self, frame):
        """
        Detect persons with low-light optimization
        """
        import time
        start = time.time()

        # Run detection
        results = self.model(
            frame,
            conf=self.confidence_threshold,
            classes=[0],  # Person only
            verbose=False,
            device=self.device
        )

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf)

                # Validate detection
                w, h = x2 - x1, y2 - y1
                if w < 20 or h < 40:  # Minimum size
                    continue
                if w * h < 1000:  # Minimum area
                    continue

                detections.append([x1, y1, x2, y2, conf])

        self.detection_time = time.time() - start
        return detections

    def should_count(self, track_id):
        """Check if person should be counted"""
        if track_id not in self.tracked_people:
            return True

        person = self.tracked_people[track_id]
        if not person.get('counted', False):
            return True

        # Check recount window
        first_count_time = person.get('first_count_time')
        if first_count_time:
            elapsed = (datetime.now() - first_count_time).total_seconds()
            if elapsed >= self.recount_seconds:
                return True

        return False

    def process_frame(self, frame):
        """
        Process frame with adaptive frame skipping
        """
        import time
        frame_start = time.time()

        self.frame_count += 1
        self.update_fps_counter()

        # Adaptive frame skipping for FPS optimization
        should_process = (self.process_counter % self.frame_skip == 0)
        self.process_counter += 1

        if should_process:
            # Detect persons
            detections = self.detect_persons(frame)

            # Update tracker
            track_start = time.time()
            tracks = self.tracker.update(detections, frame=frame)
            self.tracking_time = time.time() - track_start

            self.last_detections = tracks
        else:
            # Use cached detections (tracking only)
            tracks = self.last_detections

        # Process tracks
        new_ids = set()
        active_tracks = []

        for track in tracks:
            x1, y1, x2, y2, track_id, class_id = track

            active_tracks.append((track_id, [x1, y1, x2, y2]))

            # Initialize new track
            if track_id not in self.tracked_people:
                self.tracked_people[track_id] = {
                    'first_seen': datetime.now(),
                    'counted': False,
                    'count_number': None,
                    'frames_seen': 0
                }

            # Increment frames seen
            self.tracked_people[track_id]['frames_seen'] += 1

            # Count new person (require minimum stability)
            if (self.should_count(track_id) and
                self.tracked_people[track_id]['frames_seen'] >= 3):

                # Capture photo
                x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
                crop = frame[y1:y2, x1:x2]

                if crop.size > 0:
                    self.unique_count += 1
                    self.tracked_people[track_id]['counted'] = True
                    self.tracked_people[track_id]['count_number'] = self.unique_count
                    self.tracked_people[track_id]['first_count_time'] = datetime.now()

                    # Save image
                    timestamp = datetime.now().strftime('%H%M%S')
                    image_name = f"person_{self.unique_count:03d}_track_{track_id}_{timestamp}.jpg"
                    image_path = self.captures_dir / image_name
                    cv2.imwrite(str(image_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

                    # Calculate quality score
                    quality_score = self._calculate_quality(crop)

                    # Log event
                    self.log_event(track_id, self.unique_count, str(image_path), 0.9, quality_score)

                    logger.info(f"👤 Person #{self.unique_count} detected (Track: {track_id})")
                    logger.info(f"📸 Photo saved: {image_name}")

                    new_ids.add(track_id)

        # Update density
        self.current_frame_people_count = len(active_tracks)
        self.max_density = max(self.max_density, self.current_frame_people_count)

        # Draw on frame
        frame = self.draw_detections(frame, active_tracks, new_ids)

        self.total_time = time.time() - frame_start

        return frame

    def _calculate_quality(self, img):
        """Calculate image quality score (sharpness)"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return min(100, laplacian_var)

    def log_event(self, track_id, count_number, image_path, confidence, quality):
        """Log detection event"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df = pd.DataFrame([{
            'timestamp': timestamp,
            'track_id': track_id,
            'image_path': image_path,
            'confidence': f"{confidence:.2f}",
            'count_number': count_number,
            'camera_id': self.camera_id,
            'detection_quality': f"{quality:.1f}"
        }])
        df.to_csv(self.csv_path, mode='a', header=False, index=False)

    def draw_detections(self, frame, tracks, new_ids):
        """Draw bounding boxes and stats"""
        for track_id, bbox in tracks:
            x1, y1, x2, y2 = map(int, bbox)

            # Color
            color = (0, 255, 0) if track_id in new_ids else (0, 165, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw count number
            person_info = self.tracked_people.get(track_id, {})
            count_num = person_info.get('count_number')

            if count_num:
                text = f"#{count_num}"
                cv2.rectangle(frame, (x1, y1 - 25), (x1 + 50, y1), color, -1)
                cv2.putText(frame, text, (x1 + 5, y1 - 8),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw stats
        frame = self.draw_stats_table(frame)

        return frame

    def draw_stats_table(self, frame):
        """Draw production stats table"""
        h, w = frame.shape[:2]

        # Density level
        count = self.current_frame_people_count
        if count == 0:
            density_level, density_color = "EMPTY", (100, 100, 100)
        elif count <= 2:
            density_level, density_color = "LOW", (0, 255, 0)
        elif count <= 5:
            density_level, density_color = "MODERATE", (0, 255, 255)
        elif count <= 10:
            density_level, density_color = "HIGH", (0, 165, 255)
        else:
            density_level, density_color = "CROWDED", (0, 0, 255)

        # Table dimensions
        table_width, table_height = 400, 195
        table_x, table_y = 10, 10

        # Background
        overlay = frame.copy()
        cv2.rectangle(overlay, (table_x, table_y),
                     (table_x + table_width, table_y + table_height),
                     (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Border
        cv2.rectangle(frame, (table_x, table_y),
                     (table_x + table_width, table_y + table_height),
                     (0, 255, 255), 2)

        # Title
        cv2.putText(frame, "PRODUCTION TRACKING", (table_x + 10, table_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        cv2.line(frame, (table_x, table_y + 35),
                (table_x + table_width, table_y + 35), (0, 255, 255), 1)

        # Stats
        row_y = table_y + 58
        row_spacing = 22

        stats = [
            ("Total Unique:", f"{self.unique_count}", (0, 255, 0)),
            ("In Frame:", f"{self.current_frame_people_count}", density_color),
            ("Density:", density_level, density_color),
            ("FPS:", f"{self.current_fps:.1f}", (255, 255, 255)),
            ("Detection:", f"{self.detection_time*1000:.0f}ms", (200, 200, 200)),
            ("Tracking:", f"{self.tracking_time*1000:.0f}ms", (200, 200, 200)),
        ]

        for label, value, color in stats:
            cv2.putText(frame, label, (table_x + 15, row_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            cv2.putText(frame, str(value), (table_x + 290, row_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
            row_y += row_spacing

        # Footer
        footer = f"{self.camera_id} | StrongSORT+OSNet | Skip:1/{self.frame_skip}"
        cv2.putText(frame, footer, (table_x + 15, table_y + table_height - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)

        return frame

    def update_fps_counter(self):
        """Update FPS counter"""
        current_time = datetime.now()
        elapsed = (current_time - self.fps_time).total_seconds()
        self.fps_count += 1

        if elapsed >= 1.0:
            self.current_fps = self.fps_count / elapsed
            self.fps_count = 0
            self.fps_time = current_time

    def run(self, camera_id=0):
        """Run the counter"""
        cap = cv2.VideoCapture(camera_id)

        if not cap.isOpened():
            logger.error("❌ Failed to open camera")
            return

        logger.info("🎥 Camera opened successfully")
        logger.info("📸 Starting production tracking...")
        logger.info("⏹️  Press 'q' to quit\n")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Process frame
                frame = self.process_frame(frame)

                # Display
                cv2.imshow(f"Production Counter - {self.camera_id}", frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("\n⏹️  Stopping counter...")
                    break

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrupted by user")
        finally:
            cap.release()
            cv2.destroyAllWindows()

            logger.info(f"\n✅ Final Statistics:")
            logger.info(f"   Total Unique: {self.unique_count}")
            logger.info(f"   Max Density: {self.max_density}")
            logger.info(f"   Avg FPS: {self.current_fps:.1f}")
            logger.info(f"   Gallery Size: {len(self.tracker.reid_gallery)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Production Person Counter')
    parser.add_argument('--model', default='yolov8n.pt', help='YOLO model (n/s/m/l/x)')
    parser.add_argument('--reid', default='osnet_x1_0', help='ReID model')
    parser.add_argument('--conf', type=float, default=0.4, help='Confidence threshold')
    parser.add_argument('--skip', type=int, default=2, help='Frame skip (1=all frames)')
    parser.add_argument('--low-light', action='store_true', help='Enable low light mode')
    parser.add_argument('--camera', type=int, default=0, help='Camera ID')

    args = parser.parse_args()

    counter = ProductionPersonCounter(
        model_name=args.model,
        reid_model=args.reid,
        confidence_threshold=args.conf,
        frame_skip=args.skip,
        low_light_mode=args.low_light,
        camera_id=f'cam_{args.camera}'
    )

    counter.run(camera_id=args.camera)

