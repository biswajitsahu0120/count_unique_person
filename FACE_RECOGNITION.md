# Face Recognition Authorization Module

## 🎯 Overview

The Face Recognition Authorization Module adds security and access control to the person counting system. It:

- ✅ **Recognizes authorized persons** from a stored database
- ❌ **Blocks unknown persons** and logs unauthorized access attempts  
- 📸 **Captures photos** of both authorized and unauthorized persons
- 📊 **Logs all events** with timestamps and confidence scores
- 🔄 **Only counts authorized persons** when enabled

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
# Install face recognition library and its dependencies
pip install face_recognition dlib cmake

# Or install all requirements
pip install -r utilities/requirements.txt
```

**Note for macOS users:** You may need to install cmake first:
```bash
brew install cmake
```

### Step 2: Set Up Known Faces

Run the setup utility to register authorized persons:

```bash
cd count_unique_person
python utilities/setup_known_faces.py
```

**Menu Options:**
1. **Add New Known Face** - Register a new authorized person
2. **List All Known Faces** - View all registered persons
3. **Delete a Known Face** - Remove a person from the database
4. **Clear Cache** - Force database rebuild
5. **Exit**

### Step 3: Add Authorized Persons

#### Option A: Capture from Webcam
1. Choose option `1` (Add New Known Face)
2. Enter Person ID (e.g., `P1`, `P2`, `P3`)
3. Enter Person Name (e.g., `John Doe`)
4. Choose `1` (Capture from webcam)
5. Position your face in the green box
6. Press `SPACE` to capture
7. Face will be automatically validated and saved

#### Option B: Use Existing Photo
1. Choose option `1` (Add New Known Face)
2. Enter Person ID (e.g., `P1`)
3. Enter Person Name (e.g., `Jane Smith`)
4. Choose `2` (Use existing photo)
5. Enter path to photo file (e.g., `/path/to/photo.jpg`)
6. Photo will be validated and saved

### Step 4: Run with Face Recognition

```bash
# Option 1: Interactive prompt
python main.py
# Answer "yes" when asked about face recognition

# Option 2: Command line flag
python main.py --face-recognition
# or
python main.py --face
```

---

## 📁 Directory Structure

```
count_unique_person/
├── known_faces/              # Known faces database
│   ├── P1_JohnDoe.jpg       # Format: {ID}_{Name}.jpg
│   ├── P2_JaneSmith.jpg
│   ├── P3_AliceWang.jpg
│   ├── face_encodings_cache.pkl  # Auto-generated cache
│   └── README.txt
├── data/
│   └── face_recognition_logs/    # Face recognition logs
│       └── 2025-11-08/
│           ├── face_recognition_log.csv
│           └── captures/
│               ├── P1_JohnDoe_143052.jpg
│               └── UNKNOWN_Person_143125.jpg
└── utilities/
    ├── face_recognition_auth.py     # Core face recognition module
    └── setup_known_faces.py          # Setup utility
```

---

## 🎨 Visual Output

### When Face is Recognized ✅
```
┌─────────────────────────────┐
│ Green bounding box          │
│ ✅ ALLOWED: John Doe        │
│ Match: 95.2%                │
└─────────────────────────────┘
```

### When Face is Unknown ❌
```
┌─────────────────────────────┐
│ Red bounding box            │
│ ❌ UNKNOWN PERSON            │
│    NOT ALLOWED              │
│ No Match (dist: 0.78)       │
└─────────────────────────────┘
```

---

## 📊 Console Logs

```
[2025-11-08 20:15:23] INFO: ✅ [20:15:23] ALLOWED: John Doe (score=95.8%)
[2025-11-08 20:16:05] INFO: ❌ [20:16:05] UNKNOWN PERSON - NOT ALLOWED (dist=0.78)
[2025-11-08 20:16:08] INFO: ✅ Track 42: ALLOWED - Jane Smith
[2025-11-08 20:16:12] INFO: ❌ Track 43: UNKNOWN PERSON - NOT ALLOWED
```

---

## 📈 CSV Log Format

File: `data/face_recognition_logs/YYYY-MM-DD/face_recognition_log.csv`

| timestamp | date | time | status | person_id | name | confidence | image_path |
|-----------|------|------|--------|-----------|------|------------|------------|
| 2025-11-08T20:15:23 | 2025-11-08 | 20:15:23 | ALLOWED | P1 | John Doe | 0.42 | P1_JohnDoe_201523.jpg |
| 2025-11-08T20:16:05 | 2025-11-08 | 20:16:05 | NOT_ALLOWED | UNKNOWN | UNKNOWN | 0.78 | UNKNOWN_Person_201605.jpg |

---

## ⚙️ Configuration

### Adjust Face Matching Threshold

In `main.py`:
```python
counter = SimplifiedPersonCounter(
    enable_face_recognition=True,
    face_tolerance=0.6  # Lower = stricter (0.4-0.7 recommended)
)
```

**Recommended Tolerance Values:**
- `0.4` - Very strict (may miss some matches)
- `0.6` - Balanced (default, recommended)
- `0.7` - Lenient (may have false positives)

### Choose Detection Model

In `utilities/face_recognition_auth.py`:
```python
self.face_recognizer = FaceRecognitionAuth(
    model='hog'  # 'hog' for CPU (faster) or 'cnn' for GPU (more accurate)
)
```

**Model Comparison:**
| Model | Speed | Accuracy | Hardware |
|-------|-------|----------|----------|
| HOG | Fast (5-10 FPS) | Good | CPU only |
| CNN | Slower (1-3 FPS) | Excellent | Requires GPU |

### Require Face for Counting

To only count persons with visible faces:
```python
counter.require_face_for_counting = True
```

---

## 🔧 API Usage

### Programmatic Access

```python
from utilities.face_recognition_auth import FaceRecognitionAuth

# Initialize
face_auth = FaceRecognitionAuth(
    known_faces_dir='known_faces',
    tolerance=0.6,
    model='hog'
)

# Recognize faces in a frame
recognitions = face_auth.recognize_faces(frame)

for rec in recognitions:
    if rec['allowed']:
        print(f"✅ ALLOWED: {rec['name']} ({rec['person_id']})")
    else:
        print(f"❌ UNKNOWN PERSON - NOT ALLOWED")
    
    # Access bounding box
    x1, y1, x2, y2 = rec['bbox']
    
    # Log event
    face_auth.log_recognition(rec, frame, save_image=True)

# Add new face dynamically
face_auth.add_new_face(
    image_path='path/to/photo.jpg',
    person_id='P4',
    person_name='Bob Wilson'
)

# Reload faces without restart
face_auth.reload_faces()

# Get statistics
stats = face_auth.get_statistics()
print(f"Known faces: {stats['total_known_faces']}")
```

---

## 📸 Photo Requirements

For best results, known face photos should:

✅ **DO:**
- Use clear, front-facing photos
- Ensure good, even lighting
- Have one face per image
- Be at least 200x200 pixels
- Show the full face clearly
- Use JPG or PNG format

❌ **DON'T:**
- Use blurry or low-quality images
- Include multiple faces
- Have harsh shadows
- Use extreme angles
- Have faces partially covered

---

## 🔍 Troubleshooting

### Issue: "No module named 'face_recognition'"

**Solution:**
```bash
pip install face_recognition dlib cmake
```

On macOS, install cmake first:
```bash
brew install cmake
pip install dlib face_recognition
```

### Issue: "No face detected in image"

**Causes:**
- Poor lighting
- Face too small
- Face partially covered
- Extreme angle
- Low image quality

**Solution:**
- Use a clear, front-facing photo
- Ensure good lighting
- Minimum 200x200 pixels
- Face should be clearly visible

### Issue: Face recognition too slow

**Solution 1:** Use HOG model (CPU-optimized)
```python
model='hog'  # In face_recognition_auth.py
```

**Solution 2:** Process every N frames
```python
# Only run face recognition on key frames
if frame_count % 5 == 0:  # Every 5 frames
    recognitions = face_auth.recognize_faces(frame)
```

### Issue: False matches (wrong person recognized)

**Solution:** Lower the tolerance threshold
```python
face_tolerance=0.5  # Stricter (default is 0.6)
```

### Issue: Not recognizing known faces

**Solution:** Increase tolerance or improve face photos
```python
face_tolerance=0.7  # More lenient
```

---

## 🎓 Technical Details

### Face Recognition Algorithm

The module uses the `face_recognition` library which implements:

1. **Face Detection:** Detects faces using HOG (CPU) or CNN (GPU)
2. **Face Encoding:** Extracts 128-dimensional face embeddings using dlib's ResNet model
3. **Face Comparison:** Compares embeddings using Euclidean distance
4. **Matching:** Considers faces matching if distance ≤ tolerance threshold

### Performance

**HOG Model (CPU):**
- Detection: ~50-100ms per frame
- Encoding: ~100-200ms per face
- Comparison: <1ms per known face
- Total: ~5-10 FPS on modern CPU

**CNN Model (GPU):**
- Detection: ~100-300ms per frame  
- Encoding: ~50-100ms per face (GPU)
- Comparison: <1ms per known face
- Total: ~1-3 FPS with GPU acceleration

### Caching

Face encodings are cached to `known_faces/face_encodings_cache.pkl` for faster startup:
- First run: ~1-2 seconds per face
- Subsequent runs: <100ms total (loads from cache)
- Cache auto-rebuilds when new faces are added

---

## 📚 Integration Examples

### Example 1: Security Gate

```python
# Only count and allow authorized persons
counter = SimplifiedPersonCounter(
    enable_face_recognition=True,
    face_tolerance=0.5,  # Strict
    recount_hours=24
)

counter.require_face_for_counting = True  # Must have visible face
counter.run(camera_id=0)
```

### Example 2: Attendance System

```python
# Track who enters and exits
counter = SimplifiedPersonCounter(
    enable_face_recognition=True,
    face_tolerance=0.6,
    recount_hours=1  # Recount after 1 hour
)

counter.run(camera_id=0)
# Check data/face_recognition_logs/ for attendance records
```

### Example 3: Multi-Camera Security

```python
from applications.multi_camera_system import MultiCameraSystem

system = MultiCameraSystem(enable_face_recognition=True)
system.add_camera(camera_id=0, name='Entrance')
system.add_camera(camera_id='rtsp://192.168.1.64:8080', name='Exit')
system.run()
```

---

## 🔐 Security & Privacy

### Data Storage
- Face encodings are stored locally (not cloud)
- Photos saved in date-organized folders
- CSV logs contain timestamps and person IDs
- No data transmitted externally

### Privacy Considerations
- Obtain consent before capturing faces
- Secure the `known_faces/` directory
- Regularly review and clean logs
- Follow local data protection regulations (GDPR, etc.)

### Best Practices
- Limit known_faces directory access
- Use strong file permissions
- Regularly backup the database
- Document who is authorized
- Implement log retention policies

---

## 🆘 Support

**Common Commands:**

```bash
# Setup known faces
python utilities/setup_known_faces.py

# Run with face recognition
python main.py --face-recognition

# List known faces
cd known_faces && ls -la

# View logs
cat data/face_recognition_logs/2025-11-08/face_recognition_log.csv

# Clear cache
rm known_faces/face_encodings_cache.pkl

# Test face recognition
python -c "from utilities.face_recognition_auth import FaceRecognitionAuth; auth = FaceRecognitionAuth(); print(auth.get_statistics())"
```

**Need Help?**
- Check logs in `data/face_recognition_logs/`
- Review captured images for quality issues
- Adjust tolerance if too many false positives/negatives
- Ensure good lighting conditions

---

## 📄 License

This module is part of the Person Counter system.

---

## 🔄 Version History

- **v1.0** (2025-11-08): Initial release
  - Face recognition authorization
  - Known faces database
  - Setup utility
  - Logging and reporting
  - Integration with person counter

---

**Last Updated:** November 8, 2025

