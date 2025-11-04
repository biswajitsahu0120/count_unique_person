#!/usr/bin/env python3
"""
Person Counter - Main Entry Point
Simplified counter for detecting and counting unique people
with 24-hour recount window and advanced filtering
"""

from applications.simple_counter import SimplifiedPersonCounter

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("PERSON COUNTER - PRODUCTION VERSION")
    print("Advanced Filtering | 24-Hour Recount Window")
    print("="*60 + "\n")

    counter = SimplifiedPersonCounter(
        model_name='yolov8n.pt',
        confidence_threshold=0.5,  # Lowered to 0.5 for better detection
        recount_hours=24
    )

    counter.run(camera_id=0)


if __name__ == '__main__':
    main()

