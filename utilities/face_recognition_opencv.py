#!/usr/bin/env python3
"""
Lightweight Face Recognition Authorization Module using OpenCV
No dlib dependency - uses OpenCV's DNN face detection and feature extraction
"""

import cv2
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import pickle
from typing import Dict, List

logger = logging.getLogger(__name__)


class FaceRecognitionAuth:
    """Lightweight Face Recognition Authorization System using OpenCV"""

    def __init__(self, known_faces_dir='known_faces', tolerance=0.4, use_dnn=True):
        """
        Initialize Face Recognition system

        Args:
            known_faces_dir: Directory containing known face images
            tolerance: Face match threshold (lower = stricter, default 0.4 for cosine similarity)
            use_dnn: Use DNN face detector (more accurate) or Haar Cascade (faster)
        """
        self.known_faces_dir = Path(known_faces_dir)
        self.tolerance = tolerance
        self.use_dnn = use_dnn

        # Storage for known faces
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []

        # Cache file for faster loading
        self.cache_file = self.known_faces_dir / 'face_encodings_cache_opencv.pkl'

        # Recognition log
        self.log_dir = Path('data') / 'face_recognition_logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Load face detector
        self._load_face_detector()

        # Load face recognizer
        self._load_face_recognizer()

        # Initialize the system
        self._setup_directories()
        self._load_known_faces()

        logger.info(f"✅ Face Recognition initialized with {len(self.known_face_names)} known faces")
        logger.info(f"   Tolerance: {tolerance}, DNN: {use_dnn}")

    def _load_face_detector(self):
        """Load OpenCV face detector"""
        if self.use_dnn:
            try:
                # Load DNN face detector (more accurate)
                model_file = Path(__file__).parent / 'models' / 'opencv_face_detector_uint8.pb'
                config_file = Path(__file__).parent / 'models' / 'opencv_face_detector.pbtxt'

                if not model_file.exists() or not config_file.exists():
                    logger.warning("⚠️  DNN models not found, falling back to Haar Cascade")
                    self.use_dnn = False
                else:
                    self.face_detector = cv2.dnn.readNetFromTensorflow(str(model_file), str(config_file))
                    logger.info("   Using DNN face detector")
                    return
            except Exception as e:
                logger.warning(f"⚠️  Failed to load DNN detector: {e}")
                self.use_dnn = False

        # Fallback to Haar Cascade (faster, built-in)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        logger.info("   Using Haar Cascade face detector")

    def _load_face_recognizer(self):
        """Initialize face feature extraction"""
        # We'll use histogram and LBP features (no external model needed)
        logger.info("   Using feature-based face recognition")

    def _setup_directories(self):
        """Setup directory structure for known faces"""
        self.known_faces_dir.mkdir(exist_ok=True)

        # Create models directory
        models_dir = Path(__file__).parent / 'models'
        models_dir.mkdir(exist_ok=True)

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

    def _extract_face_features(self, face_image):
        """
        Extract face features using histogram-based method

        Args:
            face_image: Face region (grayscale)

        Returns:
            Feature vector
        """
        # Resize to standard size
        face_resized = cv2.resize(face_image, (100, 100))

        # Extract HOG features
        hist = cv2.calcHist([face_resized], [0], None, [256], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        # Also use LBP features
        lbp = self._compute_lbp(face_resized)

        # Combine features
        features = np.concatenate([hist, lbp])

        return features

    def _compute_lbp(self, image):
        """Compute Local Binary Pattern features"""
        # Simple LBP implementation
        rows, cols = image.shape
        lbp_image = np.zeros((rows-2, cols-2), dtype=np.uint8)

        for i in range(1, rows-1):
            for j in range(1, cols-1):
                center = image[i, j]
                code = 0
                code |= (image[i-1, j-1] >= center) << 7
                code |= (image[i-1, j] >= center) << 6
                code |= (image[i-1, j+1] >= center) << 5
                code |= (image[i, j+1] >= center) << 4
                code |= (image[i+1, j+1] >= center) << 3
                code |= (image[i+1, j] >= center) << 2
                code |= (image[i+1, j-1] >= center) << 1
                code |= (image[i, j-1] >= center) << 0
                lbp_image[i-1, j-1] = code

        # Compute histogram
        hist = cv2.calcHist([lbp_image], [0], None, [256], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        return hist

    def _detect_faces_dnn(self, image):
        """Detect faces using DNN"""
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(image, 1.0, (300, 300), [104, 117, 123], False, False)

        self.face_detector.setInput(blob)
        detections = self.face_detector.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (x1, y1, x2, y2) = box.astype("int")

                # Ensure within bounds
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 > x1 and y2 > y1:
                    faces.append((x1, y1, x2-x1, y2-y1))

        return faces

    def _detect_faces_haar(self, image):
        """Detect faces using Haar Cascade"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        return faces

    def detect_faces(self, image):
        """Detect faces in image"""
        if self.use_dnn:
            return self._detect_faces_dnn(image)
        else:
            return self._detect_faces_haar(image)

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
                    person_name = name_part.replace('_', ' ')
                else:
                    person_id = filename
                    person_name = filename

                # Load image
                image = cv2.imread(str(img_path))
                if image is None:
                    logger.warning(f"⚠️  Failed to load {img_path.name}")
                    continue

                # Detect faces
                faces = self.detect_faces(image)

                if len(faces) == 0:
                    logger.warning(f"⚠️  No face detected in {img_path.name}")
                    continue

                if len(faces) > 1:
                    logger.warning(f"⚠️  Multiple faces in {img_path.name}, using first one")

                # Get first face
                x, y, w, h = faces[0]
                face_roi = image[y:y+h, x:x+w]

                # Convert to grayscale
                if len(face_roi.shape) == 3:
                    face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                else:
                    face_gray = face_roi

                # Extract features
                features = self._extract_face_features(face_gray)

                self.known_face_encodings.append(features)
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

    def _compute_similarity(self, features1, features2):
        """Compute cosine similarity between two feature vectors"""
        # Cosine similarity
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return similarity

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
                - confidence: Match confidence (0-1, higher is better)
        """
        if not self.known_face_encodings:
            return []

        # Detect faces
        faces = self.detect_faces(frame)

        if len(faces) == 0:
            return []

        results = []

        for face in faces:
            x, y, w, h = face

            # Extract face region
            face_roi = frame[y:y+h, x:x+w]

            # Convert to grayscale
            if len(face_roi.shape) == 3:
                face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            else:
                face_gray = face_roi

            # Extract features
            try:
                features = self._extract_face_features(face_gray)
            except Exception as e:
                logger.debug(f"Failed to extract features: {e}")
                continue

            # Compare with known faces
            best_match_idx = -1
            best_similarity = 0.0

            for idx, known_features in enumerate(self.known_face_encodings):
                similarity = self._compute_similarity(features, known_features)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_idx = idx

            # Check if match is within tolerance
            if best_similarity >= (1.0 - self.tolerance):
                name = self.known_face_names[best_match_idx]
                person_id = self.known_face_ids[best_match_idx]
                allowed = True
            else:
                name = "UNKNOWN"
                person_id = "UNKNOWN"
                allowed = False

            results.append({
                'bbox': (x, y, x+w, y+h),
                'name': name,
                'person_id': person_id,
                'allowed': allowed,
                'confidence': float(best_similarity)
            })

        return results

    def draw_recognition_results(self, frame: np.ndarray, recognitions: List[Dict]) -> np.ndarray:
        """Draw recognition results on frame"""
        for rec in recognitions:
            x1, y1, x2, y2 = rec['bbox']

            # Color: Green if allowed, Red if unknown
            color = (0, 255, 0) if rec['allowed'] else (0, 0, 255)

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Prepare text
            if rec['allowed']:
                label = f"ALLOWED: {rec['name']}"
                confidence_text = f"Match: {rec['confidence']*100:.1f}%"
            else:
                label = "UNKNOWN PERSON - NOT ALLOWED"
                confidence_text = f"Confidence: {rec['confidence']*100:.1f}%"

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
        """Log recognition event to CSV and optionally save frame"""
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
            logger.info(f"✅ [{time_str}] ALLOWED: {name} (score={confidence*100:.1f}%)")
        else:
            logger.info(f"❌ [{time_str}] UNKNOWN PERSON - NOT ALLOWED (conf={confidence*100:.1f}%)")

    def reload_faces(self):
        """Reload known faces from directory"""
        logger.info("🔄 Reloading face database...")
        self._rebuild_face_database()

    def add_new_face(self, image_path: str, person_id: str, person_name: str) -> bool:
        """Add a new face to the database"""
        try:
            src_path = Path(image_path)
            filename = f"{person_id}_{person_name.replace(' ', '_')}{src_path.suffix}"
            dest_path = self.known_faces_dir / filename

            # Validate image has a face
            image = cv2.imread(str(src_path))
            if image is None:
                logger.error(f"❌ Failed to load image: {src_path}")
                return False

            faces = self.detect_faces(image)
            if len(faces) == 0:
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
            'detector': 'DNN' if self.use_dnn else 'Haar Cascade'
        }

