#!/usr/bin/env python3
"""
FINAL PRODUCTION SYSTEM
Integrates all components:
- YOLOv8 Detection
- StrongSORT + OSNet ReID
- Camera Motion Compensation
- Redis ID Manager + PostgreSQL
- Edge device optimization
"""

import cv2
import numpy as np
import torch
import logging
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add utilities to path
sys.path.append(str(Path(__file__).parent.parent))

from ultralytics import YOLO
from utilities.strongsort import StrongSORT
from utilities.camera_motion import CameraMotionCompensator
from utilities.id_manager import RedisIDManager
from utilities.database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class FinalProductionSystem:
    """
    Complete production system with all components integrated
    """

    def __init__(self,
                 model_name='yolov8n.pt',
                 reid_model='osnet_x1_0',
                 confidence_threshold=0.4,
                 use_camera_motion=True,
                 use_redis=True,
                 use_postgres=True,
                 camera_id='cam_0',
                 edge_mode=False):
        """
        Initialize complete system

        Args:
            model_name: YOLO model
            reid_model: OSNet ReID model
            confidence_threshold: Detection threshold
            use_camera_motion: Enable motion compensation
            use_redis: Use Redis for ID management
            use_postgres: Use PostgreSQL for storage
            camera_id: Camera identifier
            edge_mode: Edge device optimization (Jetson/TX2)
        """
        logger.info("🚀 Initializing Final Production System...")

        self.camera_id = camera_id
        self.edge_mode = edge_mode
        self.confidence_threshold = confidence_threshold

        # Device selection
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        if edge_mode and self.device == 'cpu':
            logger.warning("⚠️  Edge mode enabled but no GPU detected")

        # 1. YOLO Detection
        logger.info(f"📦 Loading YOLO: {model_name}")
        self.model = YOLO(model_name)

        # 2. StrongSORT Tracking with OSNet ReID
        logger.info(f"🔄 Initializing StrongSORT + {reid_model}")
        self.tracker = StrongSORT(
            reid_model=reid_model,
            max_age=50,
            min_hits=2,
            iou_threshold=0.3,
            max_reid_distance=0.25,
            nn_budget=150,
            device=self.device
        )

        # 3. Camera Motion Compensation
        self.motion_compensator = None
        if use_camera_motion:
            logger.info("📹 Enabling camera motion compensation")
            self.motion_compensator = CameraMotionCompensator(
                method='optical_flow'  # or 'feature_based'
            )

        # 4. ID Manager (Redis + LRU fallback)
        logger.info("💾 Initializing ID Manager")
        self.id_manager = RedisIDManager(
            use_redis=use_redis,
            ttl_hours=24
        )

        # 5. Database (PostgreSQL + SQLite fallback)
        logger.info("🗄️  Initializing Database")
        self.database = DatabaseManager(
            use_postgres=use_postgres
        )

        # Tracking state
        self.unique_count = 0
        self.frame_count = 0
        self.fps_count = 0
        self.fps_time = datetime.now()
        self.current_fps = 0.0
        self.current_frame_people_count = 0
        self.max_density = 0

        # Performance monitoring
        self.detection_time = 0
        self.tracking_time = 0
        self.motion_time = 0
        self.total_time = 0

        # Session start time
        self.session_start = datetime.now()

        # Load existing count
        self.load_existing_count()

        logger.info("✅ Final Production System Ready!")
        logger.info(f"   Device: {self.device}")
        logger.info(f"   Camera motion: {'ON' if use_camera_motion else 'OFF'}")
        logger.info(f"   ID Manager: {self.id_manager.get_stats(camera_id)['backend']}")
        logger.info(f"   Database: {'PostgreSQL' if self.database.using_postgres else 'SQLite'}")
        logger.info("")

    def load_existing_count(self):
        """Load existing count from database"""
        try:
            stats = self.database.get_daily_stats(self.camera_id)
            if stats:
                self.unique_count = stats.get('total_unique', 0)
                logger.info(f"📊 Restored: {self.unique_count} people counted today")
        except:
            pass

    def detect_persons(self, frame):
        """Detect persons using YOLO"""
        import time
        start = time.time()

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

                # Validate
                w, h = x2 - x1, y2 - y1
                if w < 20 or h < 40 or w * h < 1000:
                    continue

                detections.append([x1, y1, x2, y2, conf])

        self.detection_time = time.time() - start
        return detections

    def process_frame(self, frame):
        """Process frame with all components"""
        import time
        frame_start = time.time()

        self.frame_count += 1
        self.update_fps_counter()

        # 1. Camera Motion Compensation
        homography = None
        camera_moving = False

        if self.motion_compensator:
            motion_start = time.time()
            homography, camera_moving = self.motion_compensator.compensate(frame)
            self.motion_time = time.time() - motion_start

        # 2. Detect persons
        detections = self.detect_persons(frame)

        # 3. Compensate detections for camera motion
        if homography is not None and camera_moving:
            compensated_detections = []
            for det in detections:
                bbox = self.motion_compensator.transform_bbox(det[:4], homography)
                compensated_detections.append(bbox + [det[4]])
            detections = compensated_detections

        # 4. Update tracker
        track_start = time.time()
        tracks = self.tracker.update(detections, frame=frame)
        self.tracking_time = time.time() - track_start

        # 5. Process tracks
        new_ids = set()
        active_tracks = []

        for track in tracks:
            x1, y1, x2, y2, track_id, class_id = track

            active_tracks.append((track_id, [x1, y1, x2, y2]))

            # Check ID manager first (cross-session persistence)
            if self.id_manager.exists(track_id, self.camera_id):
                self.id_manager.update_person_seen(track_id, self.camera_id)
                continue

            # New unique person
            self.unique_count += 1

            # Store in ID manager
            metadata = {
                'count_number': self.unique_count,
                'first_seen': datetime.now().isoformat(),
                'camera': self.camera_id,
                'confidence': float(np.mean([d[4] for d in detections]) if detections else 0.9)
            }
            self.id_manager.store_person(track_id, metadata, self.camera_id)

            # Store in database
            self.database.insert_person(
                person_id=track_id,
                camera_id=self.camera_id,
                metadata=metadata
            )

            # Log event
            self.database.insert_event(
                person_id=track_id,
                camera_id=self.camera_id,
                event_type='counted',
                bbox=[x1, y1, x2, y2],
                confidence=metadata['confidence'],
                track_id=track_id,
                camera_motion=camera_moving
            )

            logger.info(f"👤 Person #{self.unique_count} detected (Track: {track_id})")
            new_ids.add(track_id)

        # Update density
        self.current_frame_people_count = len(active_tracks)
        self.max_density = max(self.max_density, self.current_frame_people_count)

        # Draw on frame
        frame = self.draw_detections(frame, active_tracks, new_ids, camera_moving)

        self.total_time = time.time() - frame_start

        return frame

    def draw_detections(self, frame, tracks, new_ids, camera_moving):
        """Draw bounding boxes and stats"""
        for track_id, bbox in tracks:
            x1, y1, x2, y2 = map(int, bbox)

            # Color
            color = (0, 255, 0) if track_id in new_ids else (0, 165, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Get person info from ID manager
            person_data = self.id_manager.get_person(track_id, self.camera_id)
            if person_data:
                count_num = person_data.get('count_number')
                if count_num:
                    text = f"#{count_num}"
                    cv2.rectangle(frame, (x1, y1 - 25), (x1 + 50, y1), color, -1)
                    cv2.putText(frame, text, (x1 + 5, y1 - 8),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw comprehensive stats
        frame = self.draw_stats_panel(frame, camera_moving)

        return frame

    def draw_stats_panel(self, frame, camera_moving):
        """Draw comprehensive stats panel"""
        h, w = frame.shape[:2]

        # Density level
        count = self.current_frame_people_count
        if count == 0:
            density_level, density_color = "EMPTY", (100, 100, 100)
        elif count <= 2:
            density_level, density_color = "LOW", (0, 255, 0)
        elif count <= 5:
            density_level, density_color = "MODERATE", (0, 255, 255)
        else:
            density_level, density_color = "HIGH", (0, 0, 255)

        # Panel dimensions
        panel_width, panel_height = 420, 240
        panel_x, panel_y = 10, 10

        # Background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height),
                     (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Border
        cv2.rectangle(frame, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height),
                     (0, 255, 255), 2)

        # Title
        cv2.putText(frame, "FINAL PRODUCTION SYSTEM", (panel_x + 10, panel_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        cv2.line(frame, (panel_x, panel_y + 35),
                (panel_x + panel_width, panel_y + 35), (0, 255, 255), 1)

        # Stats
        row_y = panel_y + 58
        row_spacing = 22

        stats = [
            ("Total Unique:", f"{self.unique_count}", (0, 255, 0)),
            ("In Frame:", f"{self.current_frame_people_count}", density_color),
            ("Density:", density_level, density_color),
            ("FPS:", f"{self.current_fps:.1f}", (255, 255, 255)),
            ("Detection:", f"{self.detection_time*1000:.0f}ms", (200, 200, 200)),
            ("Tracking:", f"{self.tracking_time*1000:.0f}ms", (200, 200, 200)),
            ("Motion:", f"{self.motion_time*1000:.0f}ms", (200, 200, 200)),
            ("Camera:", "MOVING" if camera_moving else "STABLE",
             (255, 165, 0) if camera_moving else (0, 255, 0)),
        ]

        for label, value, color in stats:
            cv2.putText(frame, label, (panel_x + 15, row_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            cv2.putText(frame, str(value), (panel_x + 310, row_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
            row_y += row_spacing

        # Footer
        footer = f"{self.camera_id} | StrongSORT+OSNet+MotionComp | {self.device.upper()}"
        cv2.putText(frame, footer, (panel_x + 15, panel_y + panel_height - 10),
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

            # Update database stats every second
            uptime = (datetime.now() - self.session_start).total_seconds()
            self.database.update_camera_stats(
                camera_id=self.camera_id,
                stats={
                    'total_unique': self.unique_count,
                    'max_density': self.max_density,
                    'avg_fps': self.current_fps,
                    'uptime_seconds': int(uptime),
                    'detections_count': self.frame_count
                }
            )

    def run(self, camera_source=0):
        """Run the system"""
        cap = cv2.VideoCapture(camera_source)

        if not cap.isOpened():
            logger.error("❌ Failed to open camera")
            return

        logger.info("🎥 Camera opened successfully")
        logger.info("📸 Starting final production system...")
        logger.info("⏹️  Press 'q' to quit\n")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Process frame
                frame = self.process_frame(frame)

                # Display
                cv2.imshow(f"Final Production - {self.camera_id}", frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("\n⏹️  Stopping system...")
                    break

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrupted by user")
        finally:
            cap.release()
            cv2.destroyAllWindows()

            # Final stats
            logger.info(f"\n✅ Final Statistics:")
            logger.info(f"   Total Unique: {self.unique_count}")
            logger.info(f"   Max Density: {self.max_density}")
            logger.info(f"   Avg FPS: {self.current_fps:.1f}")
            logger.info(f"   ID Cache: {self.id_manager.get_stats(self.camera_id)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Final Production Person Tracking System')
    parser.add_argument('--model', default='yolov8n.pt', help='YOLO model')
    parser.add_argument('--reid', default='osnet_x1_0', help='ReID model')
    parser.add_argument('--conf', type=float, default=0.4, help='Confidence threshold')
    parser.add_argument('--no-motion', action='store_true', help='Disable camera motion compensation')
    parser.add_argument('--no-redis', action='store_true', help='Disable Redis')
    parser.add_argument('--no-postgres', action='store_true', help='Disable PostgreSQL')
    parser.add_argument('--camera', default=0, help='Camera source (0, 1, or RTSP URL)')
    parser.add_argument('--camera-id', default='cam_0', help='Camera identifier')
    parser.add_argument('--edge', action='store_true', help='Edge device mode (Jetson/TX2)')

    args = parser.parse_args()

    # Convert camera to int if numeric
    try:
        camera_source = int(args.camera)
    except:
        camera_source = args.camera

    system = FinalProductionSystem(
        model_name=args.model,
        reid_model=args.reid,
        confidence_threshold=args.conf,
        use_camera_motion=not args.no_motion,
        use_redis=not args.no_redis,
        use_postgres=not args.no_postgres,
        camera_id=args.camera_id,
        edge_mode=args.edge
    )

    system.run(camera_source=camera_source)

