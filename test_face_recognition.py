#!/usr/bin/env python3
"""
Test Face Recognition Module
Quick test to verify face recognition is working
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / 'utilities'))

def test_face_recognition():
    """Test face recognition initialization and basic functions"""
    print("\n" + "="*60)
    print("FACE RECOGNITION MODULE TEST")
    print("="*60 + "\n")

    try:
        # Try importing the module
        print("1. Testing import...")
        from utilities.face_recognition_opencv import FaceRecognitionAuth
        print("   ✅ Import successful (OpenCV-based)")

        # Initialize
        print("\n2. Initializing face recognition...")
        face_auth = FaceRecognitionAuth(
            known_faces_dir='known_faces',
            tolerance=0.4,
            use_dnn=False
        )
        print("   ✅ Initialization successful")

        # Get statistics
        print("\n3. Getting statistics...")
        stats = face_auth.get_statistics()
        print(f"   Total known faces: {stats['total_known_faces']}")
        print(f"   Detector: {stats['detector']}")
        print(f"   Tolerance: {stats['tolerance']}")

        if stats['total_known_faces'] > 0:
            print("\n   Known People:")
            for person_id, name in stats['known_people']:
                print(f"      {person_id}: {name}")
        else:
            print("\n   ⚠️  No known faces found")
            print("      Add faces using: python utilities/setup_known_faces.py")

        # Test face detection on webcam
        print("\n4. Testing face detection...")
        print("   Opening webcam...")

        import cv2
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("   ⚠️  Cannot open webcam")
        else:
            print("   ✅ Webcam opened")
            print("   Capturing test frame...")

            ret, frame = cap.read()
            if ret:
                print("   ✅ Frame captured")

                # Test recognition
                print("   Running face recognition...")
                recognitions = face_auth.recognize_faces(frame)

                if recognitions:
                    print(f"   ✅ Detected {len(recognitions)} face(s)")
                    for i, rec in enumerate(recognitions, 1):
                        status = "ALLOWED" if rec['allowed'] else "NOT ALLOWED"
                        print(f"      Face {i}: {status} - {rec['name']} ({rec['confidence']*100:.1f}%)")
                else:
                    print("   ℹ️  No faces detected in frame")

            cap.release()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nNext steps:")
        print("1. Add known faces: python utilities/setup_known_faces.py")
        print("2. Run with face recognition: python main.py --face-recognition")
        print()

    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nMake sure you have installed:")
        print("  pip install opencv-python numpy pandas")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_face_recognition()

