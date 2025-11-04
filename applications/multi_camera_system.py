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
from applications.advanced_counter import AdvancedPersonCounter

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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

        # Shared embedding database for cross-camera tracking
        self.global_embedding_db = {}

        # Initialize counter for each camera
        for config in camera_configs:
            cam_id = config['id']
            counter = AdvancedPersonCounter(
                model_name='yolov8n.pt',
                confidence_threshold=0.5,
                recount_hours=24,
                camera_id=cam_id
            )

            # Share embedding database across cameras
            counter.embedding_database = self.global_embedding_db

            self.counters[cam_id] = counter
            self.frame_queues[cam_id] = queue.Queue(maxsize=2)

        logger.info(f"✅ Initialized {len(camera_configs)} cameras")
        for config in camera_configs:
            logger.info(f"   📹 {config['id']}: {config['name']}")

    def camera_thread(self, cam_id, source):
        """Thread function to process each camera"""
        cap = cv2.VideoCapture(source)
        counter = self.counters[cam_id]

        if not cap.isOpened():
            logger.error(f"❌ Failed to open camera {cam_id}")
            return

        logger.info(f"🎥 Camera {cam_id} started")

        while not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            # Process frame
            processed_frame = counter.process_frame(frame)

            # Put in queue for display
            if not self.frame_queues[cam_id].full():
                self.frame_queues[cam_id].put(processed_frame)

        cap.release()
        logger.info(f"⏹️  Camera {cam_id} stopped")

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
        total_unique = 0
        total_in_frame = 0
        total_embeddings = len(self.global_embedding_db)

        for counter in self.counters.values():
            total_unique = max(total_unique, counter.unique_count)
            total_in_frame += counter.current_frame_people_count

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

            # Print final statistics
            total_unique, total_in_frame, total_embeddings = self.get_global_stats()
            logger.info(f"\n✅ Final Statistics:")
            logger.info(f"   Total Unique People: {total_unique}")
            logger.info(f"   Embeddings Stored: {total_embeddings}")

            for cam_id, counter in self.counters.items():
                logger.info(f"   {cam_id}: {counter.unique_count} people")


if __name__ == "__main__":
    # Configure your cameras here
    camera_configs = [
        {'id': 'cam_0', 'source': 0, 'name': 'Main Entrance'},
        # Add more cameras as needed:
        # {'id': 'cam_1', 'source': 1, 'name': 'Exit Door'},
        # {'id': 'cam_2', 'source': 'rtsp://camera_ip/stream', 'name': 'Side Entrance'},
    ]

    system = MultiCameraSystem(camera_configs)
    system.run()

