#!/usr/bin/env python3
"""
Person Counter - Main Entry Point
Simplified counter for detecting and counting unique people
with 24-hour recount window and advanced filtering
Optional Face Recognition Authorization
"""

from applications.simple_counter import SimplifiedPersonCounter
import sys

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("PERSON COUNTER - PRODUCTION VERSION")
    print("Advanced Filtering | 24-Hour Recount Window")
    print("Optional Face Recognition Authorization")
    print("="*60 + "\n")

    # Ask if user wants to enable face recognition
    enable_face = False
    if '--face-recognition' in sys.argv or '--face' in sys.argv:
        enable_face = True
        print("🔐 Face Recognition: ENABLED")
    else:
        try:
            response = input("Enable Face Recognition Authorization? (yes/no) [no]: ").strip().lower()
            enable_face = response in ['yes', 'y']
        except:
            pass

    if enable_face:
        print("\n🔐 Starting with Face Recognition Authorization")
        print("   Only recognized faces will be counted")
        print("   Unknown persons will be blocked and logged")
        print("   Tolerance: 0.6 (adjustable)")
    else:
        print("\n📊 Starting without Face Recognition")
        print("   All detected persons will be counted")

    print()

    counter = SimplifiedPersonCounter(
        model_name='yolov8n.pt',
        confidence_threshold=0.5,  # Lowered to 0.5 for better detection
        recount_hours=24,
        enable_face_recognition=enable_face,
        face_tolerance=0.6  # Lower = stricter matching
    )

    # Set camera ID for display
    counter.camera_id = 'cam_0'

    counter.run(camera_id=0)


if __name__ == '__main__':
    main()

