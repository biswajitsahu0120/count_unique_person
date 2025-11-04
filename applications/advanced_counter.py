#!/usr/bin/env python3
"""
Advanced Person Counter with DeepSORT Tracking and Face Embeddings
- YOLOv10 for person detection
- DeepSORT for multi-object tracking with persistent IDs
- Face embeddings for long-term recognition
- Object permanence logic (embeddings stored for 24 hours)
- Multi-camera support ready
"""

import cv2
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from ultralytics import YOLO
import logging
import pickle
import torch
from collections import defaultdict, deque
from deep_sort_realtime.deepsort_tracker import DeepSort
from sklearn.metrics.pairwise import cosine_similarity

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class FaceEmbeddingExtractor:
    """Extract face embeddings using FaceNet for persistent recognition"""

    def __init__(self):
        try:
            from facenet_pytorch import MTCNN, InceptionResnetV1
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.mtcnn = MTCNN(keep_all=False, device=self.device)
            self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)
            self.enabled = True
            logger.info("✅ Face embedding extractor initialized")
        except Exception as e:
            logger.warning(f"⚠️  Face embeddings disabled: {e}")
            self.enabled = False

    def extract_embedding(self, image):
        """Extract 512-dimensional face embedding from image"""
        if not self.enabled:
            return None

        try:
            # Detect face
            face = self.mtcnn(image)
            if face is None:
                return None

            # Extract embedding
            face = face.unsqueeze(0).to(self.device)
            with torch.no_grad():
                embedding = self.resnet(face).cpu().numpy().flatten()

            return embedding
        except Exception as e:
            logger.debug(f"Face extraction failed: {e}")
            return None


class AdvancedPersonCounter:
    """Advanced person counter with DeepSORT tracking and face embeddings"""

    def __init__(self, model_name='yolov8n.pt', confidence_threshold=0.5,
                 recount_hours=24, camera_id='cam_0'):
        """
        Initialize advanced counter

        Args:
            model_name: YOLO model (yolov8n.pt or yolov10n.pt)
            confidence_threshold: Detection confidence (0-1)
            recount_hours: Hours before same person can be recounted
            camera_id: Unique camera identifier for multi-camera setup
        """
        logger.info("🔄 Initializing Advanced Person Counter with DeepSORT...")

        # Model and detection
        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self.recount_hours = recount_hours
        self.recount_seconds = recount_hours * 3600
        self.camera_id = camera_id

        # DeepSORT tracker initialization
        self.tracker = DeepSort(
            max_age=30,  # Frames to keep alive without detections
            n_init=3,    # Frames needed to confirm track
            nms_max_overlap=0.7,
            max_cosine_distance=0.4,
            nn_budget=100,
            embedder="mobilenet",
            half=True,
            bgr=True,
            embedder_gpu=False
        )

        # Face embedding extractor
        self.face_extractor = FaceEmbeddingExtractor()

        # Storage setup
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        self.data_dir = Path('data')
        self.date_dir = self.data_dir / self.current_date
        self.captures_dir = self.date_dir / 'captures'
        self.embeddings_dir = self.date_dir / 'embeddings'

        self.data_dir.mkdir(exist_ok=True)
        self.date_dir.mkdir(exist_ok=True)
        self.captures_dir.mkdir(exist_ok=True)
        self.embeddings_dir.mkdir(exist_ok=True)

        # CSV logging
        self.csv_path = self.date_dir / 'events.csv'
        self.init_csv()

        # Tracking state
        self.tracked_people = {}  # {track_id: person_info}
        self.unique_count = 0
        self.next_person_id = 1

        # Embedding database for persistent recognition
        self.embedding_database = {}  # {person_count: embedding}
        self.embedding_match_threshold = 0.75  # Cosine similarity threshold
        self.load_embeddings_database()

        # Frame statistics
        self.frame_count = 0
        self.fps_count = 0
        self.fps_time = datetime.now()
        self.current_fps = 0.0

        # Density tracking
        self.current_frame_people_count = 0
        self.max_density = 0

        # Load existing count
        self.load_existing_count()

        logger.info("✅ Advanced counter initialized")
        logger.info(f"📅 Date: {self.current_date}")
        logger.info(f"📹 Camera: {self.camera_id}")
        logger.info(f"🎯 Using DeepSORT tracker")
        logger.info(f"🧠 Face embeddings: {'Enabled' if self.face_extractor.enabled else 'Disabled'}")
        logger.info("")

    def load_embeddings_database(self):
        """Load stored embeddings from previous sessions"""
        embeddings_file = self.embeddings_dir / 'embeddings.pkl'
        if embeddings_file.exists():
            try:
                with open(embeddings_file, 'rb') as f:
                    self.embedding_database = pickle.load(f)
                logger.info(f"📦 Loaded {len(self.embedding_database)} embeddings from database")
            except Exception as e:
                logger.warning(f"⚠️  Could not load embeddings: {e}")
                self.embedding_database = {}

    def save_embeddings_database(self):
        """Save embeddings database to disk"""
        embeddings_file = self.embeddings_dir / 'embeddings.pkl'
        try:
            with open(embeddings_file, 'wb') as f:
                pickle.dump(self.embedding_database, f)
        except Exception as e:
            logger.warning(f"⚠️  Could not save embeddings: {e}")

    def match_embedding(self, embedding):
        """
        Match face embedding against database to check if person was seen before
        Returns: (person_count, similarity) or (None, 0)
        """
        if embedding is None or len(self.embedding_database) == 0:
            return None, 0

        best_match = None
        best_similarity = 0

        for person_count, stored_embedding in self.embedding_database.items():
            similarity = cosine_similarity(
                embedding.reshape(1, -1),
                stored_embedding.reshape(1, -1)
            )[0][0]

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = person_count

        if best_similarity >= self.embedding_match_threshold:
            return best_match, best_similarity

        return None, best_similarity

    def load_existing_count(self):
        """Load existing person count from today's data"""
        try:
            if self.csv_path.exists():
                df = pd.read_csv(self.csv_path)
                if len(df) > 0:
                    self.unique_count = int(df['count_number'].max())
                    self.next_person_id = int(df['person_id'].max()) + 1
                    logger.info(f"📊 Restored: {self.unique_count} people counted today")
                    return

            logger.info(f"📊 Starting fresh: No existing data for today")
        except Exception as e:
            logger.warning(f"⚠️  Error loading existing count: {e}")

    def init_csv(self):
        """Initialize CSV file"""
        if not self.csv_path.exists():
            df = pd.DataFrame(columns=[
                'timestamp', 'person_id', 'track_id', 'image_path',
                'confidence', 'count_number', 'camera_id', 'embedding_match'
            ])
            df.to_csv(self.csv_path, index=False)

    def detect_persons(self, frame):
        """Detect persons using YOLO"""
        results = self.model(frame, conf=self.confidence_threshold, classes=[0], verbose=False)

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf)

                # Convert to DeepSORT format: [x, y, w, h]
                x, y = int(x1), int(y1)
                w, h = int(x2 - x1), int(y2 - y1)

                detections.append(([x, y, w, h], conf, 'person'))

        return detections

    def process_frame(self, frame):
        """Process frame with DeepSORT tracking"""
        self.frame_count += 1
        self.update_fps_counter()

        # Detect persons
        detections = self.detect_persons(frame)

        # Update tracker
        tracks = self.tracker.update_tracks(detections, frame=frame)

        # Process tracks
        new_ids = set()
        active_tracks = []

        for track in tracks:
            if not track.is_confirmed():
                continue

            track_id = track.track_id
            bbox = track.to_ltrb()  # left, top, right, bottom

            active_tracks.append((track_id, bbox))

            # Initialize new track
            if track_id not in self.tracked_people:
                self.tracked_people[track_id] = {
                    'first_seen': datetime.now(),
                    'counted': False,
                    'count_number': None,
                    'embedding': None,
                    'embedding_match': None
                }

            # Try to count new person
            if not self.tracked_people[track_id]['counted']:
                x1, y1, x2, y2 = map(int, bbox)
                crop = frame[y1:y2, x1:x2]

                if crop.size > 0:
                    # Extract face embedding
                    embedding = self.face_extractor.extract_embedding(crop)

                    # Check if this person was seen before (via embedding)
                    person_match, similarity = self.match_embedding(embedding)

                    if person_match is not None:
                        logger.info(f"🔄 Person recognized from database (similarity: {similarity:.2f})")
                        logger.info(f"   Previous count: #{person_match}, not recounting")
                        self.tracked_people[track_id]['counted'] = True
                        self.tracked_people[track_id]['embedding_match'] = person_match
                        continue

                    # New unique person
                    self.unique_count += 1
                    self.tracked_people[track_id]['counted'] = True
                    self.tracked_people[track_id]['count_number'] = self.unique_count
                    self.tracked_people[track_id]['embedding'] = embedding

                    # Store embedding in database
                    if embedding is not None:
                        self.embedding_database[self.unique_count] = embedding
                        self.save_embeddings_database()

                    # Save image
                    timestamp = datetime.now().strftime('%H%M%S')
                    image_name = f"person_{self.unique_count:03d}_track_{track_id}_{timestamp}.jpg"
                    image_path = self.captures_dir / image_name
                    cv2.imwrite(str(image_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

                    # Log event
                    self.log_event(track_id, self.unique_count, str(image_path),
                                 track.get_det_conf() if hasattr(track, 'get_det_conf') else 0.9,
                                 person_match)

                    logger.info(f"👤 Person #{self.unique_count} detected (Track: {track_id})")
                    logger.info(f"📸 Photo saved: {image_name}")

                    new_ids.add(track_id)

        # Update density
        self.current_frame_people_count = len(active_tracks)
        if self.current_frame_people_count > self.max_density:
            self.max_density = self.current_frame_people_count

        # Draw on frame
        frame = self.draw_detections(frame, active_tracks, new_ids)

        return frame

    def log_event(self, track_id, count_number, image_path, confidence, embedding_match):
        """Log detection event to CSV"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        df = pd.DataFrame([{
            'timestamp': timestamp,
            'person_id': track_id,
            'track_id': track_id,
            'image_path': image_path,
            'confidence': f"{confidence:.2f}",
            'count_number': count_number,
            'camera_id': self.camera_id,
            'embedding_match': embedding_match if embedding_match else 'new'
        }])

        df.to_csv(self.csv_path, mode='a', header=False, index=False)

    def draw_detections(self, frame, tracks, new_ids):
        """Draw bounding boxes and stats"""
        for track_id, bbox in tracks:
            x1, y1, x2, y2 = map(int, bbox)

            # Color: green if new, orange if tracked
            color = (0, 255, 0) if track_id in new_ids else (0, 165, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw count number if counted
            person_info = self.tracked_people.get(track_id, {})
            count_num = person_info.get('count_number')

            if count_num:
                text = f"#{count_num}"
                cv2.rectangle(frame, (x1, y1 - 25), (x1 + 50, y1), color, -1)
                cv2.putText(frame, text, (x1 + 5, y1 - 8),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw stats table
        frame = self.draw_stats_table(frame)

        return frame

    def draw_stats_table(self, frame):
        """Draw stats table"""
        h, w = frame.shape[:2]

        # Get density level
        count = self.current_frame_people_count
        if count == 0:
            density_level, density_color = "EMPTY", (100, 100, 100)
        elif count == 1:
            density_level, density_color = "LOW", (0, 255, 0)
        elif count <= 3:
            density_level, density_color = "MODERATE", (0, 255, 255)
        elif count <= 5:
            density_level, density_color = "HIGH", (0, 165, 255)
        else:
            density_level, density_color = "CROWDED", (0, 0, 255)

        # Table dimensions
        table_width, table_height = 380, 170
        table_x, table_y = 10, 10

        # Draw table background
        overlay = frame.copy()
        cv2.rectangle(overlay, (table_x, table_y),
                     (table_x + table_width, table_y + table_height),
                     (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Draw border
        cv2.rectangle(frame, (table_x, table_y),
                     (table_x + table_width, table_y + table_height),
                     (255, 255, 255), 2)

        # Title
        cv2.putText(frame, "ADVANCED TRACKING STATS", (table_x + 10, table_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Horizontal line
        cv2.line(frame, (table_x, table_y + 35),
                (table_x + table_width, table_y + 35), (255, 255, 255), 1)

        # Stats rows
        row_y = table_y + 55
        row_spacing = 23

        # Total Unique
        cv2.putText(frame, "Total Unique:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{self.unique_count}", (table_x + 280, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # In Frame
        row_y += row_spacing
        cv2.putText(frame, "In Frame Now:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{self.current_frame_people_count}", (table_x + 280, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, density_color, 2)

        # Density
        row_y += row_spacing
        cv2.putText(frame, "Density:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, density_level, (table_x + 280, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, density_color, 2)

        # FPS
        row_y += row_spacing
        cv2.putText(frame, "FPS:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{self.current_fps:.1f}", (table_x + 280, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Embeddings
        row_y += row_spacing
        cv2.putText(frame, "Embeddings:", (table_x + 15, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"{len(self.embedding_database)}", (table_x + 280, row_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)

        # Date
        date_text = f"{self.camera_id} | {self.current_date} | DeepSORT"
        cv2.putText(frame, date_text, (table_x + 15, table_y + table_height - 10),
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

        return self.current_fps

    def run(self, camera_id=0):
        """Run the counter with live camera feed"""
        cap = cv2.VideoCapture(camera_id)

        if not cap.isOpened():
            logger.error("❌ Failed to open camera")
            return

        logger.info("🎥 Camera opened successfully")
        logger.info("📸 Starting detection with DeepSORT tracking...")
        logger.info("⏹️  Press 'q' to quit\n")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    break

                # Process frame
                frame = self.process_frame(frame)

                # Display
                cv2.imshow(f"Advanced Person Counter - {self.camera_id}", frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("\n⏹️  Stopping counter...")
                    break

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrupted by user")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            logger.info(f"✅ Final count: {self.unique_count} unique people")
            logger.info(f"📊 Max density: {self.max_density} people")
            logger.info(f"🧠 Embeddings stored: {len(self.embedding_database)}")


if __name__ == "__main__":
    counter = AdvancedPersonCounter(
        model_name='yolov8n.pt',  # Can use yolov10n.pt if available
        confidence_threshold=0.5,
        recount_hours=24,
        camera_id='cam_0'
    )
    counter.run(camera_id=0)

