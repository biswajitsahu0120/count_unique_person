#!/usr/bin/env python3
"""
Face Recognition Authorization Module
Detects and recognizes faces against a known database
"""

import cv2
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import pickle
import face_recognition
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class FaceRecognitionAuth:
    """Face Recognition Authorization System"""

    def __init__(self, known_faces_dir='known_faces', tolerance=0.6, model='hog'):
        """
        Initialize Face Recognition system

        Args:
            known_faces_dir: Directory containing known face images
            tolerance: Face match threshold (lower = stricter, default 0.6)
            model: 'hog' for CPU (faster) or 'cnn' for GPU (more accurate)
        """
        self.known_faces_dir = Path(known_faces_dir)
        self.tolerance = tolerance
        self.model = model

        # Storage for known faces
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []

        # Cache file for faster loading
        self.cache_file = self.known_faces_dir / 'face_encodings_cache.pkl'

        # Recognition log
        self.log_dir = Path('data') / 'face_recognition_logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize the system
        self._setup_directories()
        self._load_known_faces()

        logger.info(f"✅ Face Recognition initialized with {len(self.known_face_names)} known faces")
        logger.info(f"   Tolerance: {tolerance}, Model: {model}")

    def _setup_directories(self):
        """Setup directory structure for known faces"""
        self.known_faces_dir.mkdir(exist_ok=True)

        # Create example structure
        readme_path = self.known_faces_dir / 'README.txt'
        if not readme_path.exists():
            readme_path.write_text("""
Face Recognition - Known Faces Directory
=========================================

Store authorized person images here with naming convention:
    P1_PersonName.jpg
    P2_AnotherPerson.jpg
    P3_ThirdPerson.jpg

Format: {ID}_{Name}.{jpg|png}

Examples:
    P1_JohnDoe.jpg
    P2_JaneSmith.png
    P3_AliceWang.jpg

Tips:
- Use clear, front-facing photos
- Good lighting
- One face per image
- Minimum 200x200 pixels recommended
- JPG or PNG format
""")

    def _load_known_faces(self):
        """Load known faces from directory or cache"""
        # Try loading from cache first
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.known_face_encodings = cache_data['encodings']
                    self.known_face_names = cache_data['names']
                    self.known_face_ids = cache_data['ids']
                logger.info(f"📦 Loaded {len(self.known_face_names)} faces from cache")
                return
            except Exception as e:
                logger.warning(f"⚠️  Cache load failed: {e}. Rebuilding...")

        # Load from images
        self._rebuild_face_database()

    def _rebuild_face_database(self):
        """Rebuild face database from images"""
        logger.info("🔄 Building face database from images...")

        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []

        # Supported image formats
        image_extensions = ['.jpg', '.jpeg', '.png']

        # Find all face images
        face_images = []
        for ext in image_extensions:
            face_images.extend(list(self.known_faces_dir.glob(f'*{ext}')))
            face_images.extend(list(self.known_faces_dir.glob(f'*{ext.upper()}')))

        if not face_images:
            logger.warning(f"⚠️  No known face images found in {self.known_faces_dir}")
            logger.warning("   Please add images with format: P1_PersonName.jpg")
            return

        # Process each image
        for img_path in sorted(face_images):
            try:
                # Parse filename: P1_JohnDoe.jpg -> ID=P1, Name=John Doe
                filename = img_path.stem

                # Skip README and other non-face files
                if not any(filename.startswith(f'P{i}') for i in range(1, 100)):
                    continue

                # Split ID and name
                if '_' in filename:
                    person_id, name_part = filename.split('_', 1)
                    # Replace underscores with spaces in name
                    person_name = name_part.replace('_', ' ')
                else:
                    person_id = filename
                    person_name = filename

                # Load image
                image = face_recognition.load_image_file(str(img_path))

                # Detect faces
                face_encodings = face_recognition.face_encodings(image, model=self.model)

                if not face_encodings:
                    logger.warning(f"⚠️  No face detected in {img_path.name}")
                    continue

                if len(face_encodings) > 1:
                    logger.warning(f"⚠️  Multiple faces in {img_path.name}, using first one")

                # Store the first face encoding
                encoding = face_encodings[0]
                self.known_face_encodings.append(encoding)
                self.known_face_names.append(person_name)
                self.known_face_ids.append(person_id)

                logger.info(f"   ✅ Loaded: {person_id} - {person_name}")

            except Exception as e:
                logger.error(f"   ❌ Failed to load {img_path.name}: {e}")

        # Save cache
        if self.known_face_encodings:
            try:
                cache_data = {
                    'encodings': self.known_face_encodings,
                    'names': self.known_face_names,
                    'ids': self.known_face_ids,
                    'timestamp': datetime.now().isoformat()
                }
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                logger.info(f"💾 Saved face cache with {len(self.known_face_names)} faces")
            except Exception as e:
                logger.error(f"❌ Failed to save cache: {e}")

    def recognize_faces(self, frame: np.ndarray) -> List[Dict]:
        """
        Recognize faces in a frame

        Args:
            frame: BGR image from OpenCV

        Returns:
            List of dicts with keys:
                - bbox: (x1, y1, x2, y2)
                - name: Person name or "UNKNOWN"
                - person_id: P1, P2, etc. or "UNKNOWN"
                - allowed: True if recognized, False if unknown
                - confidence: Match confidence (0-1, lower is better)
        """
        if not self.known_face_encodings:
            return []

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame, model=self.model)

        if not face_locations:
            return []

        # Get face encodings
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        results = []

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Compare with known faces
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            best_match_index = np.argmin(face_distances)
            best_distance = face_distances[best_match_index]

            # Check if match is within tolerance
            if best_distance <= self.tolerance:
                name = self.known_face_names[best_match_index]
                person_id = self.known_face_ids[best_match_index]
                allowed = True
            else:
                name = "UNKNOWN"
                person_id = "UNKNOWN"
                allowed = False

            results.append({
                'bbox': (left, top, right, bottom),
                'name': name,
                'person_id': person_id,
                'allowed': allowed,
                'confidence': float(best_distance)
            })

        return results

    def draw_recognition_results(self, frame: np.ndarray, recognitions: List[Dict]) -> np.ndarray:
        """
        Draw recognition results on frame

        Args:
            frame: Input frame
            recognitions: List of recognition results from recognize_faces()

        Returns:
            Frame with annotations
        """
        for rec in recognitions:
            x1, y1, x2, y2 = rec['bbox']

            # Color: Green if allowed, Red if unknown
            color = (0, 255, 0) if rec['allowed'] else (0, 0, 255)

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Prepare text
            if rec['allowed']:
                label = f"ALLOWED: {rec['name']}"
                confidence_text = f"Match: {(1-rec['confidence'])*100:.1f}%"
            else:
                label = "UNKNOWN PERSON - NOT ALLOWED"
                confidence_text = f"No Match (dist: {rec['confidence']:.2f})"

            # Draw label background
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - 30), (x1 + label_size[0] + 10, y1), color, -1)

            # Draw label text
            cv2.putText(frame, label, (x1 + 5, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Draw confidence below box
            cv2.putText(frame, confidence_text, (x1, y2 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return frame

    def log_recognition(self, recognition: Dict, frame: np.ndarray = None, save_image: bool = True):
        """
        Log recognition event to CSV and optionally save frame

        Args:
            recognition: Recognition result dict
            frame: Frame to save (optional)
            save_image: Whether to save the frame image
        """
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y-%m-%d')
        time_str = timestamp.strftime('%H:%M:%S')

        # Create date-specific log directory
        date_log_dir = self.log_dir / date_str
        date_log_dir.mkdir(exist_ok=True)

        # Prepare log entry
        status = "ALLOWED" if recognition['allowed'] else "NOT_ALLOWED"
        name = recognition['name']
        person_id = recognition['person_id']
        confidence = recognition['confidence']

        # Save image if requested
        image_path = None
        if save_image and frame is not None:
            timestamp_str = timestamp.strftime('%H%M%S')
            image_filename = f"{person_id}_{name.replace(' ', '_')}_{timestamp_str}.jpg"
            image_path = date_log_dir / 'captures' / image_filename
            image_path.parent.mkdir(exist_ok=True)

            # Crop face region for storage
            x1, y1, x2, y2 = recognition['bbox']
            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size > 0:
                cv2.imwrite(str(image_path), face_crop)

        # Log to CSV
        csv_path = date_log_dir / 'face_recognition_log.csv'

        import pandas as pd
        log_entry = {
            'timestamp': timestamp.isoformat(),
            'date': date_str,
            'time': time_str,
            'status': status,
            'person_id': person_id,
            'name': name,
            'confidence': confidence,
            'image_path': str(image_path) if image_path else None
        }

        # Append to CSV
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df = pd.concat([df, pd.DataFrame([log_entry])], ignore_index=True)
        else:
            df = pd.DataFrame([log_entry])

        df.to_csv(csv_path, index=False)

        # Console log
        if recognition['allowed']:
            logger.info(f"✅ [{time_str}] ALLOWED: {name} (score={(1-confidence)*100:.1f}%)")
        else:
            logger.info(f"❌ [{time_str}] UNKNOWN PERSON - NOT ALLOWED (dist={confidence:.2f})")

    def reload_faces(self):
        """Reload known faces from directory (useful for adding new faces without restart)"""
        logger.info("🔄 Reloading face database...")
        self._rebuild_face_database()

    def add_new_face(self, image_path: str, person_id: str, person_name: str) -> bool:
        """
        Add a new face to the database

        Args:
            image_path: Path to face image
            person_id: ID like P1, P2, etc.
            person_name: Person's name

        Returns:
            True if successful, False otherwise
        """
        try:
            # Copy image to known_faces directory with correct naming
            src_path = Path(image_path)
            filename = f"{person_id}_{person_name.replace(' ', '_')}{src_path.suffix}"
            dest_path = self.known_faces_dir / filename

            # Load and validate image has a face
            image = face_recognition.load_image_file(str(src_path))
            face_encodings = face_recognition.face_encodings(image, model=self.model)

            if not face_encodings:
                logger.error(f"❌ No face detected in {src_path}")
                return False

            # Copy image
            import shutil
            shutil.copy2(src_path, dest_path)

            # Reload database
            self.reload_faces()

            logger.info(f"✅ Added new face: {person_id} - {person_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to add face: {e}")
            return False

    def get_statistics(self) -> Dict:
        """Get face recognition statistics"""
        return {
            'total_known_faces': len(self.known_face_names),
            'known_people': list(zip(self.known_face_ids, self.known_face_names)),
            'tolerance': self.tolerance,
            'model': self.model
        }

