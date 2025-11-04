#!/usr/bin/env python3
"""
Quick test to verify stats table display
"""
import cv2
import numpy as np
from datetime import datetime

# Create a test frame
frame = np.zeros((480, 640, 3), dtype=np.uint8)

# Draw stats table
table_x = 10
table_y = 10
table_width = 350
table_height = 140

# Draw background
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
cv2.putText(frame, "PERSON DETECTION STATS", (table_x + 10, table_y + 25),
           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

# Horizontal line
cv2.line(frame, (table_x, table_y + 35),
        (table_x + table_width, table_y + 35), (255, 255, 255), 1)

# Test values
unique_count = 5
in_frame = 3
density = "MODERATE"
fps = 8.5
date = datetime.now().strftime('%Y-%m-%d')

# Stats rows
row_y = table_y + 55
row_spacing = 25

# Row 1
cv2.putText(frame, f"Total Unique:", (table_x + 15, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
cv2.putText(frame, f"{unique_count}", (table_x + 250, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# Row 2
row_y += row_spacing
cv2.putText(frame, f"In Frame Now:", (table_x + 15, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
cv2.putText(frame, f"{in_frame}", (table_x + 250, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

# Row 3
row_y += row_spacing
cv2.putText(frame, f"Density:", (table_x + 15, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
cv2.putText(frame, f"{density}", (table_x + 250, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

# Row 4
row_y += row_spacing
cv2.putText(frame, f"FPS:", (table_x + 15, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
cv2.putText(frame, f"{fps:.1f}", (table_x + 250, row_y),
           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

# Date
cv2.putText(frame, f"Date: {date} | 24hr window", (table_x + 15, table_y + table_height - 10),
           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

# Display
cv2.imshow("Stats Table Test", frame)
print("✅ Stats table test:")
print(f"  Total Unique: {unique_count}")
print(f"  In Frame: {in_frame}")
print(f"  Density: {density}")
print(f"  FPS: {fps}")
print("\nPress any key to close...")
cv2.waitKey(0)
cv2.destroyAllWindows()
print("✅ Test complete!")

