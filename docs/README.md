# Person Detection and Counting System

A real-time person detection and counting system using YOLOv8 and DeepSORT/SORT tracking. This application detects unique people entering the camera frame, assigns unique IDs, and logs detection events.

## 🎯 Features

- **Real-time Person Detection**: Uses YOLOv8 model for accurate person detection
- **Multi-Object Tracking**: Stable track IDs assigned to each person using DeepSORT
- **Unique Person Counting**: Maintains a count of unique individuals across the entire session
- **Photo Capture**: Automatically captures and saves photos of newly detected persons
- **Event Logging**: CSV log with timestamp, person ID, image path, and confidence scores
- **Live Display**: Real-time video feed with bounding boxes and statistics overlay
- **Performance Optimized**: Designed to run on CPU-only laptops with target of 10+ FPS

## 📋 System Requirements

- Python 3.8+
- Webcam/Camera device
- Minimum 4GB RAM (8GB recommended)
- CPU with at least 4 cores

## 🚀 Installation

1. **Clone or setup the project directory**:
   ```bash
   cd count_unique_person
   ```

2. **Create and activate virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 📊 Project Structure

```
count_unique_person/
├── run.py                    # Main application (with DeepSORT)
├── run_lite.py               # Lightweight version (with SORT)
├── requirements.txt          # Python dependencies
├── utils/
│   └── tracker_utils.py      # SORT tracker implementation
├── data/
│   ├── events.csv            # Logged detection events
│   └── captures/             # Saved person photos
└── README.md                 # This file
```

## 🎮 Usage

### Option 1: Full Version (DeepSORT - More Accurate)
```bash
python run.py
```

### Option 2: Lite Version (SORT - Faster, CPU-friendly)
```bash
python run_lite.py
```

### Specify Different Model Size
```bash
# Using small model (more accurate but slower)
python run.py yolov8s.pt

# Using nano model (fastest, good for CPU)
python run.py yolov8n.pt
```

## 🎛️ Configuration

You can customize the behavior by editing the main files:

### In `run.py` or `run_lite.py`:

```python
# Adjust these parameters in the main() function:
counter = PersonCounter(
    model_name='yolov8n.pt',      # Model size
    confidence_threshold=0.5,      # Detection confidence (0-1)
    max_age=30                     # Frames to keep track alive
)
```

### Available Models
- `yolov8n.pt` - Nano (fastest, ~5-10 FPS on CPU)
- `yolov8s.pt` - Small (balanced, ~3-5 FPS on CPU)
- `yolov8m.pt` - Medium (slower, ~1-2 FPS on CPU)

## 📖 Output Files

### Console Output
```
[2025-11-03 14:52:31] [INFO] Person 1 detected at 2025-11-03 14:52:31
[2025-11-03 14:52:45] [INFO] Person 2 detected at 2025-11-03 14:52:45
[2025-11-03 14:53:12] [INFO] Person 3 detected at 2025-11-03 14:53:12
```

### CSV Log (data/events.csv)
| timestamp | person_id | image_path | confidence |
|-----------|-----------|------------|-----------|
| 2025-11-03 14:52:31 | 1 | data/captures/person_001_track_1_20251103_145231_123.jpg | 0.95 |
| 2025-11-03 14:52:45 | 2 | data/captures/person_002_track_2_20251103_145245_456.jpg | 0.92 |

### Video Display
- **Green bounding boxes** around detected persons
- **Track ID** label on each person
- **Total Unique People** count in top-left
- **FPS** counter in real-time

## ⌨️ Controls

- **q** - Quit the application
- **Ctrl+C** - Force quit (alternative)

## 🔧 Troubleshooting

### "Failed to open camera"
- Ensure camera is not used by another application
- Try specifying different camera ID: `counter.run(camera_id=0)` or `1`, `2`, etc.

### Low FPS Performance
- Use lighter model: `yolov8n.pt` (nano)
- Use lite version: `python run_lite.py`
- Reduce frame resolution by editing the code
- Close other CPU-intensive applications

### Memory Issues
- Use nano model instead of larger models
- Reduce `max_age` parameter
- Use lite version (SORT instead of DeepSORT)

### Not Detecting People
- Check lighting conditions
- Ensure people are clearly visible in frame
- Increase `confidence_threshold` gradually from 0.5

### Photos not Saved
- Verify `data/` directory has write permissions
- Check available disk space

## 📈 Performance Tips

1. **For CPU-only devices**:
   - Use `run_lite.py` (SORT tracker)
   - Use `yolov8n.pt` model
   - Reduce input frame size

2. **For better accuracy**:
   - Use `run.py` (DeepSORT tracker)
   - Use larger model (`yolov8s.pt` or `yolov8m.pt`)
   - Increase `confidence_threshold` to 0.6-0.7

3. **For longer sessions**:
   - Monitor disk space for saved images
   - Consider archiving old CSV files

## 🎓 How It Works

1. **Frame Capture**: Continuously reads frames from webcam
2. **Person Detection**: YOLOv8 detects all persons in frame
3. **Tracking**: Assigns stable IDs to each detected person using:
   - **DeepSORT** (run.py): Deep learning + Hungarian algorithm (more accurate)
   - **SORT** (run_lite.py): IoU + Kalman filter (faster, CPU-friendly)
4. **Unique Counting**: If track ID not seen before → increment count and capture photo
5. **Logging**: Record event with timestamp to CSV
6. **Display**: Show annotated frame with boxes, IDs, and statistics

## 📝 License

This project uses open-source libraries:
- YOLOv8 (Ultralytics)
- OpenCV
- DeepSORT / SORT implementations
- PyTorch

## 🤝 Contributing

Feel free to fork, modify, and improve this project!

## ❓ FAQ

**Q: Can I track multiple people simultaneously?**
A: Yes! The system is designed to track multiple people in the same frame with unique IDs.

**Q: What if the same person leaves and returns?**
A: The tracking system will maintain the track ID for ~30 frames (configurable). If they return within this time, same ID is used. After 30 frames, a new ID is assigned (counted as new person).

**Q: Can I use this with IP cameras?**
A: Yes! OpenCV supports IP camera streams. Modify `camera_id` in `run.py`:
```python
cap = cv2.VideoCapture('rtsp://your_camera_url')
```

**Q: How accurate is the counting?**
A: Accuracy depends on lighting, camera angle, and model size. Nano model achieves ~85-90% accuracy in good conditions.

**Q: Can I train a custom model?**
A: Yes! YOLOv8 supports training. This project uses pre-trained models by default.

