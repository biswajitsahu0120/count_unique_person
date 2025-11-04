# 🎯 Person Counter - 24 Hour Recount

A simplified person detection and counting system that counts unique people entering the camera frame with a 24-hour recount window.

## ✨ Features

- ✅ Detects unique people entering the frame
- ✅ Captures photos automatically
- ✅ Does NOT recount same person for 24 hours
- ✅ After 24 hours, same person can be counted again
- ✅ Organizes results by date (CSV and photos)
- ✅ Real-time display with detection boxes
- ✅ Automatic logging

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Webcam

### Installation & Run

```bash
# Navigate to project
cd count_unique_person

# Setup (first time only)
bash utilities/setup.sh

# Run the counter
bash start_simple.sh
```

Or manually:
```bash
source .venv/bin/activate
python applications/simple_counter.py
```

## 📁 Data Organization

Results are organized by date:
```
data/
└── 2025-11-03/              (Today's date)
    ├── events.csv           (Detection log)
    └── captures/            (Photos)
        ├── person_001_id_1_141530.jpg
        ├── person_002_id_2_141545.jpg
        └── ...
```

## 📊 CSV Format

```
timestamp,person_id,image_path,confidence,count_number
2025-11-03 14:15:30,1,data/2025-11-03/captures/person_001_id_1_141530.jpg,0.95,1
2025-11-03 14:15:45,2,data/2025-11-03/captures/person_002_id_2_141545.jpg,0.92,2
```

## ⏱️ 24-Hour Recount Logic

- **First detection**: Person counted and photo captured
- **Within 24 hours**: Same person NOT recounted
- **After 24 hours**: Same person counted again as new entry
- **New folder daily**: Results organized by date

## ⏹️ Stop

Press **'q'** on keyboard while running

## 📊 Output

**On screen:**
- Live video with detection boxes
- Total unique people count
- FPS counter
- Current date

**Saved files:**
- `data/{date}/events.csv` - Detection log
- `data/{date}/captures/` - Person photos

## 🛠️ System Requirements

- Python 3.8+
- 4GB RAM
- Webcam
- ~2GB disk for models/data

## 📝 Notes

- YOLOv8 nano model used (lightweight)
- 24-hour window resets for each person after recount
- Each day creates automatic date folder
- No configuration needed - just run!

---

**Status**: Ready to use  
**Version**: 1.0  
**Date**: November 3, 2025

# count_unique_person
