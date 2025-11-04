#!/usr/bin/env python3
"""
Emergency diagnostic script to test detection directly
"""
import cv2
from ultralytics import YOLO
import sys

print("=" * 60)
print("EMERGENCY DIAGNOSTIC TEST")
print("=" * 60)

# Test 1: Camera
print("\n1. Testing camera...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("   ❌ FAIL: Camera not accessible!")
    sys.exit(1)

ret, frame = cap.read()
if not ret:
    print("   ❌ FAIL: Cannot read from camera!")
    cap.release()
    sys.exit(1)

h, w = frame.shape[:2]
print(f"   ✅ SUCCESS: Camera working! Resolution: {w}x{h}")

# Test 2: YOLO Model
print("\n2. Testing YOLO model...")
try:
    model = YOLO('yolov8n.pt')
    print("   ✅ SUCCESS: Model loaded!")
except Exception as e:
    print(f"   ❌ FAIL: Model error: {e}")
    cap.release()
    sys.exit(1)

# Test 3: Detection
print("\n3. Testing detection on 10 frames...")
print(f"   Confidence threshold: 0.5")
print(f"   Looking for people (class 0)...")

detection_count = 0
for i in range(10):
    ret, frame = cap.read()
    if not ret:
        continue

    results = model(frame, conf=0.5, verbose=False)

    for result in results:
        for box in result.boxes:
            if int(box.cls) == 0:  # person
                detection_count += 1
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf)
                w_box = x2 - x1
                h_box = y2 - y1
                area = w_box * h_box

                print(f"\n   Frame {i+1}: PERSON DETECTED!")
                print(f"     Position: ({x1:.0f}, {y1:.0f}) to ({x2:.0f}, {y2:.0f})")
                print(f"     Size: {w_box:.0f}x{h_box:.0f} pixels")
                print(f"     Area: {area:.0f} px²")
                print(f"     Confidence: {conf:.2f}")
                print(f"     Edge check:")
                print(f"       - x1 >= 20? {x1 >= 20} ({x1:.0f})")
                print(f"       - y1 >= 20? {y1 >= 20} ({y1:.0f})")
                print(f"       - x2 <= {w-20}? {x2 <= w-20} ({x2:.0f})")
                print(f"       - y2 <= {h-20}? {y2 <= h-20} ({y2:.0f})")
                print(f"     Size check:")
                print(f"       - area >= 3000? {area >= 3000}")
                print(f"       - width >= 30? {w_box >= 30}")
                print(f"       - height >= 60? {h_box >= 60}")

cap.release()

# Summary
print("\n" + "=" * 60)
print(f"SUMMARY: {detection_count} person detections in 10 frames")
if detection_count == 0:
    print("❌ PROBLEM: No people detected!")
    print("   Possible causes:")
    print("   - No person in front of camera")
    print("   - Room too dark")
    print("   - Camera angle wrong")
    print("   - Person too far from camera")
    print("\n   TRY: Stand directly in front of camera, 1-2 meters away")
else:
    print(f"✅ SUCCESS: Detection working! ({detection_count} detections)")
print("=" * 60)

