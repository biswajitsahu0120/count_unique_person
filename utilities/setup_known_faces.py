#!/usr/bin/env python3
"""
Setup Known Faces for Face Recognition
This script helps you register known faces in the system
"""

import cv2
import sys
from pathlib import Path
import shutil
import numpy as np

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def capture_face_photo():
    """Capture a face photo using webcam"""
    print("\n📸 Face Photo Capture")
    print("=" * 60)

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Error: Cannot open camera")
        return None

    print("📷 Camera opened successfully")
    print("Instructions:")
    print("  - Position your face in the center")
    print("  - Ensure good lighting")
    print("  - Press SPACE to capture")
    print("  - Press Q to cancel")
    print()

    captured_frame = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Flip for mirror view
        frame = cv2.flip(frame, 1)

        # Draw guide rectangle
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2
        box_size = 300
        x1 = center_x - box_size // 2
        y1 = center_y - box_size // 2
        x2 = center_x + box_size // 2
        y2 = center_y + box_size // 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, "Position face in green box", (x1, y1 - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, "SPACE = Capture | Q = Cancel", (20, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow('Capture Face Photo', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):  # Space to capture
            captured_frame = frame.copy()
            print("✅ Photo captured!")
            break
        elif key == ord('q'):  # Q to cancel
            print("❌ Capture cancelled")
            break

    cap.release()
    cv2.destroyAllWindows()

    return captured_frame


def get_next_person_id():
    """Automatically generate the next available Person ID"""
    known_faces_dir = Path('known_faces')

    if not known_faces_dir.exists():
        return "P1"

    # Find all existing person IDs
    existing_ids = []
    for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
        for img_file in known_faces_dir.glob(f'P*{ext}'):
            filename = img_file.stem
            if '_' in filename:
                person_id = filename.split('_', 1)[0]
                if person_id.startswith('P') and person_id[1:].isdigit():
                    existing_ids.append(int(person_id[1:]))

    if not existing_ids:
        return "P1"

    # Return next available ID
    next_id = max(existing_ids) + 1
    return f"P{next_id}"


def check_duplicate_face(new_image):
    """
    Check if the face in new_image already exists in the database
    Uses multiple comparison methods for better accuracy
    Returns: (is_duplicate, existing_person_id, existing_name, similarity)
    """
    known_faces_dir = Path('known_faces')

    if not known_faces_dir.exists():
        return False, None, None, 0.0

    # Extract features from new image
    try:
        # Try using face_recognition for better accuracy
        try:
            import face_recognition
            import numpy as np

            rgb_image = cv2.cvtColor(new_image, cv2.COLOR_BGR2RGB)
            new_encodings = face_recognition.face_encodings(rgb_image)

            if not new_encodings:
                print("   ⚠️  No face detected for comparison")
                return False, None, None, 0.0

            new_encoding = new_encodings[0]

            # Compare with all existing faces
            print("   🔍 Checking against existing faces...")

            for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                for img_file in known_faces_dir.glob(f'P*{ext}'):
                    try:
                        # Load existing image
                        existing_image = cv2.imread(str(img_file))
                        if existing_image is None:
                            continue

                        existing_rgb = cv2.cvtColor(existing_image, cv2.COLOR_BGR2RGB)
                        existing_encodings = face_recognition.face_encodings(existing_rgb)

                        if not existing_encodings:
                            continue

                        existing_encoding = existing_encodings[0]

                        # Calculate face distance (lower = more similar)
                        distance = face_recognition.face_distance([existing_encoding], new_encoding)[0]
                        similarity = (1 - distance) * 100  # Convert to percentage

                        # Threshold: 0.6 distance = 40% tolerance
                        # If distance < 0.6, faces are likely the same person
                        if distance < 0.6:
                            # Extract person info
                            filename = img_file.stem
                            if '_' in filename:
                                person_id, name_part = filename.split('_', 1)
                                person_name = name_part.replace('_', ' ')
                            else:
                                person_id = filename
                                person_name = filename

                            return True, person_id, person_name, similarity

                    except Exception as e:
                        continue

            return False, None, None, 0.0

        except ImportError:
            # Fallback to IMPROVED OpenCV-based comparison
            import numpy as np

            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray_new = cv2.cvtColor(new_image, cv2.COLOR_BGR2GRAY)
            faces_new = face_cascade.detectMultiScale(gray_new, 1.3, 5)

            if len(faces_new) == 0:
                return False, None, None, 0.0

            # Get first face from new image
            x, y, w, h = faces_new[0]
            new_face = gray_new[y:y+h, x:x+w]
            new_face_resized = cv2.resize(new_face, (100, 100))

            # Compute MULTIPLE features for better comparison
            # 1. Histogram
            new_hist = cv2.calcHist([new_face_resized], [0], None, [256], [0, 256])
            new_hist = cv2.normalize(new_hist, new_hist).flatten()

            # 2. LBP (Local Binary Pattern) - more robust
            def compute_lbp_histogram(image):
                """Compute LBP histogram for better face comparison"""
                lbp_image = np.zeros_like(image)
                for i in range(1, image.shape[0] - 1):
                    for j in range(1, image.shape[1] - 1):
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
                        lbp_image[i, j] = code

                lbp_hist = cv2.calcHist([lbp_image], [0], None, [256], [0, 256])
                lbp_hist = cv2.normalize(lbp_hist, lbp_hist).flatten()
                return lbp_hist

            new_lbp_hist = compute_lbp_histogram(new_face_resized)

            print("   🔍 Checking against existing faces (Enhanced OpenCV mode)...")

            # Compare with existing faces
            for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                for img_file in known_faces_dir.glob(f'P*{ext}'):
                    try:
                        existing_image = cv2.imread(str(img_file))
                        if existing_image is None:
                            continue

                        gray_existing = cv2.cvtColor(existing_image, cv2.COLOR_BGR2GRAY)
                        faces_existing = face_cascade.detectMultiScale(gray_existing, 1.3, 5)

                        if len(faces_existing) == 0:
                            continue

                        x, y, w, h = faces_existing[0]
                        existing_face = gray_existing[y:y+h, x:x+w]
                        existing_face_resized = cv2.resize(existing_face, (100, 100))

                        # Compare using histogram
                        existing_hist = cv2.calcHist([existing_face_resized], [0], None, [256], [0, 256])
                        existing_hist = cv2.normalize(existing_hist, existing_hist).flatten()
                        hist_similarity = cv2.compareHist(new_hist, existing_hist, cv2.HISTCMP_CORREL) * 100

                        # Compare using LBP for more robust matching
                        existing_lbp_hist = compute_lbp_histogram(existing_face_resized)
                        lbp_similarity = cv2.compareHist(new_lbp_hist, existing_lbp_hist, cv2.HISTCMP_CORREL) * 100

                        # Compare using structural similarity (template matching)
                        template_match = cv2.matchTemplate(new_face_resized, existing_face_resized, cv2.TM_CCOEFF_NORMED)[0][0]
                        template_similarity = template_match * 100

                        # Combined similarity score (weighted average)
                        combined_similarity = (
                            hist_similarity * 0.3 +        # Histogram: 30%
                            lbp_similarity * 0.4 +          # LBP: 40% (most important)
                            template_similarity * 0.3       # Template: 30%
                        )

                        filename = img_file.stem
                        if '_' in filename:
                            person_id, name_part = filename.split('_', 1)
                            person_name = name_part.replace('_', ' ')
                        else:
                            person_id = filename
                            person_name = filename

                        # Debug output
                        print(f"      Comparing with {person_id}_{person_name}:")
                        print(f"         Histogram: {hist_similarity:.1f}%")
                        print(f"         LBP: {lbp_similarity:.1f}%")
                        print(f"         Template: {template_similarity:.1f}%")
                        print(f"         Combined: {combined_similarity:.1f}%")

                        # Lower threshold: >75% combined similarity = same person (more sensitive)
                        if combined_similarity > 75:
                            return True, person_id, person_name, combined_similarity

                    except Exception as e:
                        print(f"      Error comparing with {img_file.name}: {e}")
                        continue

            return False, None, None, 0.0

    except Exception as e:
        print(f"   ⚠️  Duplicate check error: {e}")
        return False, None, None, 0.0


def add_known_face():
    """Add a new known face to the database"""
    print("\n" + "=" * 60)
    print("ADD NEW KNOWN FACE")
    print("=" * 60)

    # Auto-generate person ID
    person_id = get_next_person_id()
    print(f"\n✨ Auto-generated Person ID: {person_id}")

    print(f"✅ Using Person ID: {person_id}")

    person_name = input("Enter Person Name (e.g., John Doe): ").strip()
    if not person_name:
        print("❌ Name cannot be empty")
        return

    # Choose input method
    print("\nChoose input method:")
    print("1. Capture from webcam")
    print("2. Use existing photo file")
    choice = input("Enter choice (1 or 2): ").strip()

    image = None

    if choice == '1':
        # Capture from webcam
        image = capture_face_photo()
        if image is None:
            print("❌ Failed to capture photo")
            return

    elif choice == '2':
        # Use existing file
        file_path = input("Enter path to photo file: ").strip()
        if not Path(file_path).exists():
            print(f"❌ File not found: {file_path}")
            return

        image = cv2.imread(file_path)
        if image is None:
            print(f"❌ Failed to load image from: {file_path}")
            return

    else:
        print("❌ Invalid choice")
        return

    # Validate face in image
    print("\n🔍 Validating face in image...")

    try:
        # Try using face_recognition if available
        try:
            import face_recognition
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_image)
        except ImportError:
            # Fallback to OpenCV Haar Cascade
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            face_locations = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(face_locations) == 0:
            print("❌ No face detected in image!")
            print("   Please use a clear front-facing photo with good lighting")
            return

        if len(face_locations) > 1:
            print(f"⚠️  Multiple faces detected ({len(face_locations)})")
            print("   Using the first detected face")

        print("✅ Face detected successfully")

    except Exception as e:
        print(f"⚠️  Face validation error: {e}")
        print("   Skipping validation - image will be saved anyway")

    # Check for duplicate face
    print("\n🔍 Checking for duplicate faces...")
    is_duplicate, existing_id, existing_name, similarity = check_duplicate_face(image)

    if is_duplicate:
        print("\n" + "="*60)
        print("❌ DUPLICATE FACE DETECTED!")
        print("="*60)
        print(f"   This face already exists in the database:")
        print(f"   • Existing ID: {existing_id}")
        print(f"   • Existing Name: {existing_name}")
        print(f"   • Similarity: {similarity:.1f}%")
        print()
        print("   ⚠️  CANNOT ADD: The same face cannot be registered twice!")
        print("   💡 Tip: Names may differ, but faces must be unique.")
        print("="*60)

        # Ask if user wants to see the existing face
        show = input("\nShow existing face image? (yes/no): ").strip().lower()
        if show in ['yes', 'y']:
            known_faces_dir = Path('known_faces')
            for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                matching_files = list(known_faces_dir.glob(f"{existing_id}_*{ext}"))
                if matching_files:
                    existing_img = cv2.imread(str(matching_files[0]))
                    if existing_img is not None:
                        # Show both images side by side
                        h1, w1 = image.shape[:2]
                        h2, w2 = existing_img.shape[:2]

                        # Resize to same height for comparison
                        target_h = 400
                        new_w1 = int(w1 * target_h / h1)
                        new_w2 = int(w2 * target_h / h2)

                        img1_resized = cv2.resize(image, (new_w1, target_h))
                        img2_resized = cv2.resize(existing_img, (new_w2, target_h))

                        # Create side-by-side comparison
                        comparison = np.hstack([img1_resized, img2_resized])

                        # Add labels
                        cv2.putText(comparison, "NEW (Rejected)", (10, 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        cv2.putText(comparison, f"EXISTING: {existing_name}", (new_w1 + 10, 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        cv2.putText(comparison, f"Similarity: {similarity:.1f}%", (10, target_h - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

                        cv2.imshow('Duplicate Face Comparison - Press any key to close', comparison)
                        cv2.waitKey(0)
                        cv2.destroyAllWindows()
                    break

        return  # Exit without saving

    print("✅ No duplicate found - face is unique")

    # Save to known_faces directory
    known_faces_dir = Path('known_faces')
    known_faces_dir.mkdir(exist_ok=True)

    filename = f"{person_id}_{person_name.replace(' ', '_')}.jpg"
    save_path = known_faces_dir / filename

    cv2.imwrite(str(save_path), image)

    print("\n" + "="*60)
    print("✅ SUCCESS!")
    print("="*60)
    print(f"   Person ID: {person_id}")
    print(f"   Name: {person_name}")
    print(f"   Saved to: {save_path}")
    print()
    print("💡 The face database will be automatically reloaded on next run")
    print("="*60)


def list_known_faces():
    """List all known faces in the database"""
    known_faces_dir = Path('known_faces')

    if not known_faces_dir.exists():
        print("\n❌ No known_faces directory found")
        return

    # Find all image files
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
        image_files.extend(list(known_faces_dir.glob(f'*{ext}')))

    # Filter valid face files (starting with P)
    face_files = [f for f in image_files if any(f.stem.startswith(f'P{i}') for i in range(1, 100))]

    if not face_files:
        print("\n📭 No known faces found")
        print("   Use option 1 to add faces")
        return

    print("\n" + "=" * 60)
    print("KNOWN FACES DATABASE")
    print("=" * 60)

    for face_file in sorted(face_files):
        filename = face_file.stem
        if '_' in filename:
            person_id, name_part = filename.split('_', 1)
            person_name = name_part.replace('_', ' ')
        else:
            person_id = filename
            person_name = filename

        print(f"  {person_id}: {person_name}")

    print(f"\nTotal: {len(face_files)} known faces")
    print("=" * 60)


def delete_known_face():
    """Delete a known face from the database"""
    list_known_faces()

    person_id = input("\nEnter Person ID to delete (or 'cancel'): ").strip()

    if person_id.lower() == 'cancel':
        return

    known_faces_dir = Path('known_faces')

    # Find matching files
    matching_files = list(known_faces_dir.glob(f"{person_id}_*.*"))

    if not matching_files:
        print(f"❌ No face found with ID: {person_id}")
        return

    # Confirm deletion
    print(f"\nFound: {matching_files[0].name}")
    confirm = input("Are you sure you want to delete? (yes/no): ").strip().lower()

    if confirm == 'yes':
        for file in matching_files:
            file.unlink()
        print(f"✅ Deleted: {person_id}")

        # Delete cache to force rebuild
        cache_file = known_faces_dir / 'face_encodings_cache.pkl'
        if cache_file.exists():
            cache_file.unlink()
            print("   Cache cleared - database will rebuild on next run")
    else:
        print("❌ Deletion cancelled")


def main():
    """Main menu"""
    while True:
        print("\n" + "=" * 60)
        print("FACE RECOGNITION - KNOWN FACES SETUP")
        print("=" * 60)
        print("\n1. Add New Known Face")
        print("2. List All Known Faces")
        print("3. Delete a Known Face")
        print("4. Clear Cache (Force Rebuild)")
        print("5. Exit")

        choice = input("\nEnter choice (1-5): ").strip()

        if choice == '1':
            add_known_face()
        elif choice == '2':
            list_known_faces()
        elif choice == '3':
            delete_known_face()
        elif choice == '4':
            cache_file = Path('known_faces/face_encodings_cache.pkl')
            if cache_file.exists():
                cache_file.unlink()
                print("✅ Cache cleared - database will rebuild on next run")
            else:
                print("ℹ️  No cache file found")
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice")


if __name__ == '__main__':
    main()

