# 🚀 QUICK START GUIDE - Advanced System

## Choose Your System

### 1️⃣ Original Simple System (Lightweight)
**Best for:** Single person at a time, budget laptops, basic needs

```bash
python main.py
```

**Features:**
- ✅ Fast (12-15 FPS)
- ✅ Low CPU usage
- ✅ Basic tracking
- ❌ No face recognition
- ❌ No multi-camera

---

### 2️⃣ Advanced Single Camera (Recommended)
**Best for:** Accurate counting, busy areas, professional use

```bash
# Install dependencies first
pip install -r utilities/requirements.txt

# Run advanced system
python applications/advanced_counter.py
```

**Features:**
- ✅ DeepSORT tracking
- ✅ Face embeddings (512d)
- ✅ 24-hour memory
- ✅ Object permanence
- ✅ 95%+ accuracy
- ⚠️  Slower (8-12 FPS)
- ⚠️  Higher CPU usage

---

### 3️⃣ Multi-Camera System (Enterprise)
**Best for:** Buildings, malls, multiple entry points

```bash
# Install dependencies first
pip install -r utilities/requirements.txt

# Edit camera config in multi_camera_system.py
# Then run:
python applications/multi_camera_system.py
```

**Features:**
- ✅ All advanced features
- ✅ Multiple cameras
- ✅ Cross-camera tracking
- ✅ Shared embeddings
- ✅ Mosaic display
- ⚠️  Requires good hardware
- ⚠️  4-8 FPS per camera

---

## Installation

### Step 1: Install Python Packages

```bash
cd utilities
pip install -r requirements.txt
```

**What gets installed:**
- `ultralytics` - YOLO models
- `opencv-python` - Video processing
- `deep-sort-realtime` - Advanced tracking
- `facenet-pytorch` - Face embeddings
- `scikit-learn` - Similarity matching
- `pandas` - Data logging

### Step 2: Download Models

Models auto-download on first run:
- YOLOv8n: ~6 MB (auto-downloads)
- FaceNet: ~100 MB (auto-downloads)

---

## Configuration

### Simple System (main.py)

No configuration needed - just run!

### Advanced System (advanced_counter.py)

Edit these lines:

```python
counter = AdvancedPersonCounter(
    model_name='yolov8n.pt',      # Use yolov8n.pt or yolov10n.pt
    confidence_threshold=0.5,      # 0.3-0.7 (higher = stricter)
    recount_hours=24,              # Hours before recount (8-48)
    camera_id='cam_0'              # Unique camera name
)
```

### Multi-Camera (multi_camera_system.py)

Edit camera config:

```python
camera_configs = [
    {'id': 'cam_0', 'source': 0, 'name': 'Main Entrance'},
    {'id': 'cam_1', 'source': 1, 'name': 'Side Door'},
    # Add more cameras:
    # {'id': 'cam_2', 'source': 'rtsp://192.168.1.10/stream', 'name': 'Exit'},
]
```

**Camera sources:**
- `0, 1, 2` - USB webcams
- `'video.mp4'` - Video file
- `'rtsp://ip/stream'` - IP camera
- `'http://ip/mjpeg'` - HTTP stream

---

## Troubleshooting

### Issue: "No module named 'deep_sort_realtime'"

**Solution:**
```bash
pip install deep-sort-realtime
```

### Issue: "No module named 'facenet_pytorch'"

**Solution:**
```bash
pip install facenet-pytorch
```

### Issue: Low FPS with advanced system

**Solution 1:** Disable face embeddings (in advanced_counter.py):
```python
# In FaceEmbeddingExtractor.__init__:
self.enabled = False  # Add this line
```

**Solution 2:** Use GPU (requires CUDA):
```python
self.device = torch.device('cuda')
```

**Solution 3:** Lower resolution (in camera_thread):
```python
frame = cv2.resize(frame, (640, 480))
```

### Issue: Face embeddings not working

**Causes:**
- Faces too small or blurry
- Person wearing mask
- Bad lighting

**Solutions:**
- Better camera position
- Improve lighting
- Get closer to camera
- Remove masks (if possible)

### Issue: Multi-camera lag

**Solutions:**
- Reduce camera resolution
- Use fewer cameras
- Disable face embeddings
- Use better hardware

---

## Data Storage

### File Structure

```
data/2025-11-03/
├── captures/
│   ├── person_001_track_5_220802.jpg
│   └── person_002_track_8_220805.jpg
├── embeddings/
│   └── embeddings.pkl  ← Face embedding database
└── events.csv          ← Log of all events
```

### CSV Format

```csv
timestamp,person_id,track_id,image_path,confidence,count_number,camera_id,embedding_match
2025-11-03 22:08:02,5,5,person_001_track_5_220802.jpg,0.84,1,cam_0,new
2025-11-03 22:08:05,8,8,person_002_track_8_220805.jpg,0.85,2,cam_0,new
2025-11-03 22:08:20,5,5,,0.82,0,cam_0,1  ← Recognized, not counted
```

---

## Performance Tips

### For Better Speed:
1. Use simple system (`main.py`)
2. Disable face embeddings
3. Use GPU if available
4. Reduce camera resolution
5. Close other applications

### For Better Accuracy:
1. Use advanced system
2. Enable face embeddings
3. Good lighting
4. High resolution camera
5. Camera at face height

### For Multi-Camera:
1. Use dedicated hardware
2. Lower individual camera FPS
3. Share embeddings across cameras
4. Use network cameras (offload encoding)
5. Consider edge computing

---

## System Requirements

### Minimum (Simple System):
- CPU: Intel i3 or equivalent
- RAM: 4 GB
- Storage: 1 GB
- OS: Windows/Mac/Linux

### Recommended (Advanced System):
- CPU: Intel i5 or better
- RAM: 8 GB
- Storage: 5 GB
- GPU: Optional but helps
- OS: Windows/Mac/Linux

### Multi-Camera System:
- CPU: Intel i7 or better
- RAM: 16 GB
- Storage: 10 GB
- GPU: Recommended
- Network: Gigabit for IP cameras
- OS: Linux recommended

---

## Next Steps

1. **Choose your system** (simple/advanced/multi-camera)
2. **Install dependencies** (`pip install -r utilities/requirements.txt`)
3. **Configure if needed** (edit camera sources)
4. **Run the system** (`python applications/...`)
5. **Check output** (data folder, CSV, images)
6. **Read docs** (`ADVANCED_SYSTEM.md` for details)

---

## Support & Documentation

- **Full docs:** `ADVANCED_SYSTEM.md`
- **Project structure:** `docs/PROJECT_STRUCTURE.md`
- **Implementation:** `docs/IMPLEMENTATION.md`
- **Fixes applied:** `DUPLICATE_FIX.md`, `COUNT_RESTORATION.md`, etc.

---

## Quick Commands

```bash
# Simple system
python main.py

# Advanced single camera
python applications/advanced_counter.py

# Multi-camera system
python applications/multi_camera_system.py

# Install dependencies
pip install -r utilities/requirements.txt

# Check data
ls data/2025-11-03/captures/
cat data/2025-11-03/events.csv
```

---

*Quick Start Guide - November 3, 2025*  
*All systems ready to use!* ✅

