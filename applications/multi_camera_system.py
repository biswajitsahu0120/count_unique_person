#!/usr/bin/env python3
"""
Multi-Camera Fusion System
- Fuse multiple CCTV feeds
- Cross-camera tracking using face embeddings
- Unified person count across all cameras
"""

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import threading
import queue
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from applications.simple_counter import SimplifiedPersonCounter

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress OpenCV MJPEG warnings
import os
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
cv2.setLogLevel(0)


class MultiCameraSystem:
    """Multi-camera person counting system with cross-camera tracking"""

    def __init__(self, camera_configs):
        """
        Initialize multi-camera system

        Args:
            camera_configs: List of dicts with camera configs
                [
                    {'id': 'cam_0', 'source': 0, 'name': 'Entrance'},
                    {'id': 'cam_1', 'source': 1, 'name': 'Exit'},
                ]
        """
        logger.info("🔄 Initializing Multi-Camera System...")

        self.camera_configs = camera_configs
        self.counters = {}
        self.threads = {}
        self.frame_queues = {}
        self.stop_event = threading.Event()

        # Thread lock for shared database access
        self.db_lock = threading.Lock()

        # Shared state class to hold mutable counters
        class SharedState:
            def __init__(self):
                self.unique_count = 0
                self.next_person_id = 1

        self.shared_state = SharedState()

        # Create one master counter to initialize databases
        master_counter = SimplifiedPersonCounter(
            model_name='yolov8n.pt',
            confidence_threshold=0.5,
            recount_hours=24
        )

        # Get initial counts from master
        self.shared_state.unique_count = master_counter.unique_count
        self.shared_state.next_person_id = master_counter.next_person_id

        # Initialize counter for each camera with SHARED database
        for config in camera_configs:
            cam_id = config['id']
            counter = SimplifiedPersonCounter(
                model_name='yolov8n.pt',
                confidence_threshold=0.5,
                recount_hours=24
            )

            # Share the mutable database objects across all cameras
            counter.tracked_people = master_counter.tracked_people
            counter.image_hashes = master_counter.image_hashes
            counter.last_capture_time = master_counter.last_capture_time
            counter.csv_buffer = master_counter.csv_buffer
            counter.csv_path = master_counter.csv_path

            # Link to shared state for counters
            counter.shared_state = self.shared_state
            counter.db_lock = self.db_lock

            # Set camera-specific ID for subfolder creation
            counter.camera_id = cam_id

            self.counters[cam_id] = counter
            self.frame_queues[cam_id] = queue.Queue(maxsize=2)

        # Keep reference to master for final stats
        self.master_counter = master_counter

        logger.info(f"✅ Initialized {len(camera_configs)} cameras with shared database")
        for config in camera_configs:
            logger.info(f"   📹 {config['id']}: {config['name']}")

    def camera_thread(self, cam_id, source):
        """Thread function to process each camera"""
        counter = self.counters[cam_id]
        retry_count = 0
        max_retries = 5
        cap = None

        while retry_count < max_retries and not self.stop_event.is_set():
            logger.info(f"📡 Connecting to camera {cam_id}... (attempt {retry_count + 1}/{max_retries})")

            # For IP cameras, set timeout
            if isinstance(source, str) and (source.startswith('http') or source.startswith('rtsp')):
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for lower latency
            else:
                cap = cv2.VideoCapture(source)

            if cap.isOpened():
                logger.info(f"✅ Camera {cam_id} connected successfully")
                break
            else:
                retry_count += 1
                logger.warning(f"⚠️ Camera {cam_id} connection failed, retrying...")
                import time
                time.sleep(2)

        if not cap.isOpened():
            logger.error(f"❌ Failed to open camera {cam_id} after {max_retries} attempts")
            return

        logger.info(f"🎥 Camera {cam_id} started")
        frame_count = 0
        error_count = 0
        max_errors = 30  # Allow 30 consecutive errors before stopping

        while not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                error_count += 1
                if error_count >= max_errors:
                    logger.error(f"❌ Camera {cam_id} stopped responding after {max_errors} errors")
                    break
                continue

            error_count = 0  # Reset error count on successful read
            frame_count += 1

            # Process frame
            processed_frame = counter.process_frame(frame)

            # Put in queue for display
            if not self.frame_queues[cam_id].full():
                self.frame_queues[cam_id].put(processed_frame)

        cap.release()
        logger.info(f"⏹️  Camera {cam_id} stopped (processed {frame_count} frames)")

    def create_mosaic(self, frames_dict):
        """Create a mosaic view of all camera feeds"""
        if len(frames_dict) == 0:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        # Get frame size (assume all same size, resize if needed)
        first_frame = list(frames_dict.values())[0]
        h, w = first_frame.shape[:2]

        # Calculate grid size
        n_cams = len(frames_dict)
        if n_cams == 1:
            return list(frames_dict.values())[0]
        elif n_cams == 2:
            cols, rows = 2, 1
        elif n_cams <= 4:
            cols, rows = 2, 2
        else:
            cols, rows = 3, 2

        # Resize frames to fit in grid
        cell_w = w // cols
        cell_h = h // rows

        # Create mosaic
        mosaic = np.zeros((cell_h * rows, cell_w * cols, 3), dtype=np.uint8)

        for idx, (cam_id, frame) in enumerate(frames_dict.items()):
            if idx >= cols * rows:
                break

            row = idx // cols
            col = idx % cols

            # Resize frame
            resized = cv2.resize(frame, (cell_w, cell_h))

            # Add camera label
            cv2.putText(resized, cam_id, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            # Place in mosaic
            y1 = row * cell_h
            y2 = y1 + cell_h
            x1 = col * cell_w
            x2 = x1 + cell_w

            mosaic[y1:y2, x1:x2] = resized

        return mosaic

    def get_global_stats(self):
        """Get combined statistics across all cameras"""
        # Use shared state for accurate global unique count
        total_unique = self.shared_state.unique_count

        # Sum up current people in frame across all cameras
        total_in_frame = sum(counter.current_frame_people_count
                            for counter in self.counters.values())

        # Count stored hashes for duplicate detection
        total_embeddings = len(self.master_counter.image_hashes)

        return total_unique, total_in_frame, total_embeddings

    def run(self):
        """Run multi-camera system"""
        logger.info("🚀 Starting all cameras...")

        # Start camera threads
        for config in self.camera_configs:
            cam_id = config['id']
            source = config['source']

            thread = threading.Thread(
                target=self.camera_thread,
                args=(cam_id, source),
                daemon=True
            )
            thread.start()
            self.threads[cam_id] = thread

        logger.info("📺 Display starting...")
        logger.info("⏹️  Press 'q' to quit\n")

        try:
            while True:
                # Collect frames from all cameras
                frames_dict = {}
                for cam_id in self.frame_queues:
                    try:
                        frame = self.frame_queues[cam_id].get(timeout=0.1)
                        frames_dict[cam_id] = frame
                    except queue.Empty:
                        pass

                if frames_dict:
                    # Create mosaic view
                    mosaic = self.create_mosaic(frames_dict)

                    # Add global stats
                    total_unique, total_in_frame, total_embeddings = self.get_global_stats()

                    stats_text = f"GLOBAL: {total_unique} unique | {total_in_frame} in frame | {total_embeddings} embeddings"
                    cv2.rectangle(mosaic, (5, mosaic.shape[0] - 35),
                                (len(stats_text) * 12, mosaic.shape[0] - 5),
                                (0, 0, 0), -1)
                    cv2.putText(mosaic, stats_text, (10, mosaic.shape[0] - 15),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                    cv2.imshow("Multi-Camera Person Counter", mosaic)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("\n⏹️  Stopping all cameras...")
                    break

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrupted by user")
        finally:
            self.stop_event.set()

            # Wait for threads to finish
            for thread in self.threads.values():
                thread.join(timeout=2)

            cv2.destroyAllWindows()

            # Print final statistics using shared state
            logger.info(f"\n✅ Final Statistics:")
            logger.info(f"   Total Unique People (across all cameras): {self.shared_state.unique_count}")
            logger.info(f"   Total tracked IDs: {len(self.master_counter.tracked_people)}")
            logger.info(f"   Images captured: {len(list(self.master_counter.captures_dir.glob('**/*.jpg')))}")

            # Show which cameras contributed to detection
            logger.info(f"\n   Camera contributions:")
            for cam_id in self.counters.keys():
                logger.info(f"      📹 {cam_id}: Active")


if __name__ == "__main__":
    # Configure your cameras here
    camera_configs = [
        {'id': 'cam_0', 'source': 0, 'name': 'Laptop Camera'},
        {'id': 'cam_1', 'source': 'http://root:root@192.168.1.3:8080/video', 'name': 'IP Camera'},
    ]

    logger.info("=" * 60)
    logger.info("🎥 Multi-Camera Person Counter System")
    logger.info("=" * 60)
    logger.info("Configured Cameras:")
    for config in camera_configs:
        logger.info(f"  📹 {config['name']} ({config['id']})")
    logger.info("=" * 60)
    logger.info("")

    system = MultiCameraSystem(camera_configs)
    system.run()

