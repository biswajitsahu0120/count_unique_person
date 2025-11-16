#!/usr/bin/env python3
"""
Test script to verify camera connections
"""

import cv2
import sys

def test_camera(cam_id, source, name):
    """Test a single camera connection"""
    print(f"\n{'='*60}")
    print(f"Testing {name} ({cam_id})")
    print(f"Source: {source}")
    print(f"{'='*60}")

    try:
        # Try to open camera
        if isinstance(source, str) and (source.startswith('http') or source.startswith('rtsp')):
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            print(f"❌ FAILED to connect to {name}")
            return False

        print(f"✅ Connected successfully")

        # Try to read a frame
        ret, frame = cap.read()
        if not ret:
            print(f"❌ FAILED to read frame from {name}")
            cap.release()
            return False

        print(f"✅ Read frame successfully")
        print(f"   Resolution: {frame.shape[1]}x{frame.shape[0]}")
        print(f"   FPS: {cap.get(cv2.CAP_PROP_FPS)}")

        # Show the frame
        cv2.imshow(f"{name} - Press any key to continue", frame)
        cv2.waitKey(2000)  # Show for 2 seconds
        cv2.destroyAllWindows()

        cap.release()
        print(f"✅ {name} is working properly!")
        return True

    except Exception as e:
        print(f"❌ ERROR testing {name}: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎥 Camera Connection Test")
    print("="*60)

    # Define cameras to test
    cameras = [
        {'id': 'cam_0', 'source': 0, 'name': 'Laptop Camera'},
        {'id': 'cam_1', 'source': 'http://root:root@192.168.1.3:8080/video', 'name': 'IP Camera'},
    ]

    results = {}
    for cam in cameras:
        results[cam['id']] = test_camera(cam['id'], cam['source'], cam['name'])

    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Summary")
    print(f"{'='*60}")
    for cam in cameras:
        status = "✅ WORKING" if results[cam['id']] else "❌ FAILED"
        print(f"{cam['name']:20} {status}")

    all_working = all(results.values())
    if all_working:
        print(f"\n✅ All cameras are working! You can now run the multi-camera system.")
        sys.exit(0)
    else:
        print(f"\n⚠️ Some cameras failed. Please check the connections and try again.")
        sys.exit(1)

