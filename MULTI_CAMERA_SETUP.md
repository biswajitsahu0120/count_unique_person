# Multi-Camera Person Counting System

## Overview
This system allows you to count unique people across multiple cameras simultaneously with cross-camera tracking using face embeddings.

## Camera Configuration

### Camera 1: Laptop Camera (Built-in)
- **Source**: `0` (default camera index)
- **Type**: Local USB/built-in camera
- **No authentication required**

### Camera 2: IP Camera (192.168.1.3:8080)
- **IP Address**: 192.168.1.3
- **Port**: 8080
- **Username**: root
- **Password**: root
- **URL Format**: `http://root:root@192.168.1.3:8080/video`

## Quick Start

### Step 1: Test Camera Connections
Before running the full system, test if both cameras are accessible:

```bash
python test_cameras.py
```

This will:
- Connect to each camera
- Display a test frame for 2 seconds
- Show resolution and FPS info
- Report which cameras are working

### Step 2: Run Multi-Camera System
If all cameras passed the test:

```bash
python applications/multi_camera_system.py
```

Or use the main menu:
```bash
python main.py
# Select option for multi-camera (if available)
```

## Features

### Cross-Camera Tracking
- **Shared Embedding Database**: All cameras share the same person database
- **No Double Counting**: A person counted in Camera 1 won't be counted again in Camera 2
- **24-Hour Recount Window**: After 24 hours, the same person can be counted again

### Display
- **Mosaic View**: All camera feeds shown in a grid layout
- **Global Statistics**: Total unique count across all cameras
- **Per-Camera Stats**: Individual counts displayed on each feed

### Storage
- **Date-Based Folders**: Data organized by date (YYYY-MM-DD)
- **Separate Captures**: Each camera has its own capture subfolder
- **Unified CSV Log**: Single events.csv with camera_id column

## Troubleshooting

### IP Camera Connection Issues

#### Problem: "Failed to connect to IP Camera"
**Solutions:**
1. **Check network connectivity**:
   ```bash
   ping 192.168.1.3
   ```

2. **Test camera URL in browser**:
   Open `http://192.168.1.3:8080/video` in your browser
   Enter username: `root`, password: `root`

3. **Check if camera is on same network**:
   - Your laptop and camera must be on the same WiFi/LAN
   - Verify IP address hasn't changed

4. **Try different URL formats**:
   - MJPEG: `http://root:root@192.168.1.3:8080/video`
   - RTSP: `rtsp://root:root@192.168.1.3:8080/stream`
   - H.264: `http://root:root@192.168.1.3:8080/h264`

5. **Firewall settings**:
   - Ensure port 8080 is not blocked
   - Temporarily disable firewall to test

#### Problem: "Camera connected but no frames"
**Solutions:**
1. Check camera stream format (MJPEG vs H.264)
2. Update OpenCV: `pip install --upgrade opencv-python`
3. Try alternative stream path: `/video.cgi` or `/mjpeg`

#### Problem: "Authentication failed"
**Solutions:**
1. Verify username and password are correct
2. Check if camera uses different auth mechanism
3. Try URL without auth first: `http://192.168.1.3:8080/video`

### Laptop Camera Issues

#### Problem: "Failed to open laptop camera"
**Solutions:**
1. **Check camera permissions**:
   - macOS: System Preferences → Security & Privacy → Camera
   - Grant permission to Terminal/Python

2. **Close other apps using camera**:
   - Zoom, Skype, FaceTime, etc.

3. **Try different camera index**:
   Change `source: 0` to `source: 1` in config

### Performance Issues

#### Problem: "Lag or low FPS"
**Solutions:**
1. **Reduce number of cameras**: Start with 1-2 cameras
2. **Lower resolution**: Edit camera settings to reduce stream resolution
3. **Use smaller model**: Change to `yolov8n.pt` (nano) instead of medium/large
4. **Skip frames**: Process every 2nd or 3rd frame

#### Problem: "High CPU usage"
**Solutions:**
1. Reduce confidence threshold to get fewer detections
2. Process frames at lower FPS (e.g., 10 FPS instead of 30)
3. Consider using GPU if available

## Advanced Configuration

### Adding More Cameras
Edit `applications/multi_camera_system.py`:

```python
camera_configs = [
    {'id': 'cam_0', 'source': 0, 'name': 'Laptop Camera'},
    {'id': 'cam_1', 'source': 'http://root:root@192.168.1.3:8080/video', 'name': 'IP Camera'},
    {'id': 'cam_2', 'source': 'rtsp://admin:pass@192.168.1.10:554/stream', 'name': 'Entrance'},
    {'id': 'cam_3', 'source': 1, 'name': 'USB Camera'},
]
```

### Customizing Display Layout
The system automatically adjusts layout based on camera count:
- 1 camera: Full screen
- 2 cameras: 2x1 grid
- 3-4 cameras: 2x2 grid
- 5-6 cameras: 3x2 grid

### Changing Recount Window
To change from 24 hours to different duration, edit `multi_camera_system.py`:

```python
counter = AdvancedPersonCounter(
    model_name='yolov8n.pt',
    confidence_threshold=0.5,
    recount_hours=8,  # Change from 24 to 8 hours
    camera_id=cam_id
)
```

## Data Storage Structure

```
data/
└── 2025-11-06/
    ├── events.csv                 # Unified event log
    └── captures/
        ├── cam_0/                 # Laptop camera captures
        │   ├── person_001_...jpg
        │   └── person_002_...jpg
        └── cam_1/                 # IP camera captures
            ├── person_001_...jpg
            └── person_003_...jpg
```

## CSV Format

```csv
timestamp,person_id,camera_id,image_path
2025-11-06 14:32:15,1,cam_0,captures/cam_0/person_001_id_1_143215.jpg
2025-11-06 14:33:42,2,cam_1,captures/cam_1/person_002_id_2_143342.jpg
```

## Network Diagram

```
Your Network (192.168.1.x)
│
├── Laptop (192.168.1.x)
│   └── Running Python script
│       ├── Camera 0: Built-in webcam
│       └── Connecting to Camera 1 via HTTP
│
└── IP Camera (192.168.1.3:8080)
    └── Streaming video via HTTP
```

## Security Notes

⚠️ **Important**: The camera credentials are in plain text in the code. For production:
1. Use environment variables:
   ```python
   import os
   CAM_USER = os.getenv('CAMERA_USER', 'root')
   CAM_PASS = os.getenv('CAMERA_PASS', 'root')
   source = f'http://{CAM_USER}:{CAM_PASS}@192.168.1.3:8080/video'
   ```

2. Or use a config file (add to .gitignore):
   ```python
   import json
   with open('camera_config.json') as f:
       config = json.load(f)
   ```

## Support

If you encounter issues:
1. Run `python test_cameras.py` to diagnose
2. Check logs in console for error messages
3. Verify network connectivity with `ping`
4. Test camera URL in web browser first
5. Check camera manufacturer documentation for correct stream URL

## Controls

- **Q**: Quit application
- **Ctrl+C**: Emergency stop

## Performance Benchmarks

| Setup | Expected FPS | CPU Usage |
|-------|--------------|-----------|
| 1 camera (laptop) | 15-20 | 40-60% |
| 2 cameras | 10-15 | 70-90% |
| 3+ cameras | 5-10 | 95%+ |

*Benchmarks on MacBook Air M1, may vary on different hardware*

