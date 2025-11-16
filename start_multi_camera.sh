#!/bin/bash
# Multi-Camera Person Counter - Quick Start Guide
# ==================================================

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Multi-Camera Person Counter - Configuration Summary        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📹 CONFIGURED CAMERAS:"
echo "  • Camera 0: Laptop built-in camera (source: 0)"
echo "  • Camera 1: IP Camera at 192.168.1.3:8080"
echo "    └─ URL: http://root:root@192.168.1.3:8080/video"
echo ""
echo "✅ FEATURES ENABLED:"
echo "  • Cross-camera duplicate prevention"
echo "  • 24-hour recount window"
echo "  • Date-based storage (YYYY-MM-DD)"
echo "  • Perceptual hash duplicate detection"
echo "  • Thread-safe multi-camera operation"
echo ""
echo "📁 DATA STORAGE:"
echo "  • Location: data/YYYY-MM-DD/"
echo "  • CSV log: data/YYYY-MM-DD/events.csv"
echo "  • Images: data/YYYY-MM-DD/captures/cam_X/"
echo ""
echo "🚀 QUICK COMMANDS:"
echo ""
echo "1. Test cameras:"
echo "   python test_cameras.py"
echo ""
echo "2. Run multi-camera system:"
echo "   python applications/multi_camera_system.py"
echo ""
echo "3. Run single laptop camera:"
echo "   python main.py"
echo ""
echo "4. View this guide again:"
echo "   ./start_multi_camera.sh --help"
echo ""
echo "🎮 CONTROLS:"
echo "  • Press 'Q' in video window to quit"
echo "  • Ctrl+C for emergency stop"
echo ""
echo "📚 DOCUMENTATION:"
echo "  • MULTI_CAMERA_COMPLETE.md - Full setup guide"
echo "  • MULTI_CAMERA_SETUP.md - Troubleshooting"
echo "  • test_cameras.py - Camera diagnostics"
echo ""
echo "═══════════════════════════════════════════════════════════════"

# If --help or -h flag, just show info and exit
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    exit 0
fi

# Otherwise, run the test and start system
echo ""
read -p "Press ENTER to test cameras and start system (or Ctrl+C to cancel)..."

python test_cameras.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Cameras ready! Starting multi-camera system in 3 seconds..."
    sleep 3
    python applications/multi_camera_system.py
else
    echo ""
    echo "❌ Camera test failed. Please check configuration."
    exit 1
fi

