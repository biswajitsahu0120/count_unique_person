# Camera Display Layout

## Visual Layout of Each Camera Feed

```
┌─────────────────────────────────────────────────────────────────┐
│                                             📹 CAM_0            │ ← Camera name (top right)
│                                                                 │
│  ┌──────────────────────┐                                      │
│  │ PERSON DETECTION     │                                      │
│  │ STATS                │                                      │
│  ├──────────────────────┤                                      │
│  │ Total Unique:     3  │                                      │
│  │ In Frame Now:     1  │                                      │
│  │ Density:       LOW   │                                      │
│  │ FPS:          15.3   │                                      │
│  └──────────────────────┘                                      │
│                                                                 │
│              ┌─────────────┐                                   │
│              │   Person    │ ← Bounding box                    │
│              │    #3       │ ← Person count number             │
│              │             │                                   │
│              │             │                                   │
│              └─────────────┘                                   │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-Camera Layout (Split Screen)

```
┌──────────────────────────────┬──────────────────────────────┐
│                              │                              │
│    📹 CAM_0                  │    📹 CAM_1                  │
│                              │                              │
│  ┌───────────────┐           │  ┌───────────────┐          │
│  │ STATS         │           │  │ STATS         │          │
│  │ Total: 3      │           │  │ Total: 3      │          │
│  │ In Frame: 1   │           │  │ In Frame: 2   │          │
│  └───────────────┘           │  └───────────────┘          │
│                              │                              │
│      [Person 1]              │    [Person 2] [Person 3]    │
│                              │                              │
│                              │                              │
└──────────────────────────────┴──────────────────────────────┘
             GLOBAL: 3 unique | 3 in frame
```

## Display Elements

### Top Right Corner (NEW!)
- **📹 CAM_0** or **📹 CAM_1**
- Blue background with white border
- Large, easy to read
- Shows which camera feed you're viewing

### Top Left Corner
- Stats table with detection info:
  - Total Unique: Cumulative count across all cameras
  - In Frame Now: Current people visible
  - Density: EMPTY/LOW/MEDIUM/HIGH/CROWDED
  - FPS: Current processing speed

### People Detection
- Green boxes: Newly detected people
- Orange boxes: Previously counted people
- White text above box: Count number (#1, #2, #3, etc.)

### Bottom Bar (Multi-Camera)
- Shows global statistics
- Combined count across all cameras
- Yellow text on dark background

## Color Coding

- **Blue**: Camera name background
- **White**: Borders and labels
- **Green**: Newly counted person
- **Orange**: Previously counted person (in recount window)
- **Yellow**: Global stats
- **Red/Orange/Green**: Density indicators

## Camera Name Positioning

The camera name is automatically positioned:
- **X position**: Right side of frame - 20 pixels
- **Y position**: Top of frame + 15 pixels
- **Background**: Semi-transparent blue
- **Text**: White, bold, with emoji icon

This makes it easy to identify which camera you're looking at in multi-camera setups!

