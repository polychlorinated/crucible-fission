# Crucible Fission - FFmpeg QA Report & Alternative Solutions

## 🔍 Current Implementation Analysis

### How FFmpeg is Currently Used

The app uses FFmpeg in **3 locations** via subprocess calls:

1. **`video.py:35`** - `normalize_video()` - Normalizes input to H.264/AAC
2. **`video.py:148`** - `extract_clip()` - Extracts moment clips (5s/15s versions)
3. **`video.py:213`** - `create_vertical_version()` - Creates 9:16 vertical videos
4. **`transcription.py:46`** - Audio extraction for Whisper

### Issues Found

#### 1. **Subprocess is Brittle**
```python
result = subprocess.run(cmd, capture_output=True, text=True)
```
- No check if `ffmpeg` binary exists before calling
- No PATH verification
- Silent failures with generic error messages

#### 2. **Unused Dependency**
- `requirements.txt` has `ffmpeg-python==0.2.0` but code uses raw subprocess
- Either use the Python wrapper or remove it

#### 3. **No Railway-Specific Handling**
- Railway free tier has memory limits (512MB-1GB)
- FFmpeg can OOM-kill on large videos
- No fallback strategy if FFmpeg fails

#### 4. **Missing Error Context**
```python
except:
    return 0  # In get_video_duration()
```
- Silent failures hide root cause
- Can't debug "not working" without logs

---

## 🛠️ Alternative SDKs/Libraries

### Option 1: imageio-ffmpeg (Recommended for Railway)
**Best for:** Bundled binary, no system dependency

```python
from imageio_ffmpeg import get_ffmpeg_exe
import subprocess

# Get bundled FFmpeg path
ffmpeg_path = get_ffmpeg_exe()

cmd = [ffmpeg_path, '-i', video_path, ...]
```

**Pros:**
- Bundles FFmpeg binary (~5MB)
- No apt-get install needed
- Works on Railway/Vercel/any container

**Cons:**
- Slightly larger deploy bundle
- Still subprocess-based

**Install:**
```bash
pip install imageio-ffmpeg
```

---

### Option 2: moviepy (Recommended for Code Clarity)
**Best for:** Pythonic API, easier maintenance

```python
from moviepy.editor import VideoFileClip

# Extract clip
clip = VideoFileClip(video_path).subclip(start, end)
clip = clip.resize(width=480)
clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
clip.close()
```

**Pros:**
- Clean Python API (no subprocess)
- Handles FFmpeg internally
- Better error messages

**Cons:**
- Higher memory usage
- Slower (Python overhead)
- Still needs FFmpeg installed

**Install:**
```bash
pip install moviepy
```

---

### Option 3: opencv-python (No FFmpeg Required)
**Best for:** Lightweight, pure Python alternative

```python
import cv2

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
start_frame = int(start_time * fps)
end_frame = int((start_time + duration) * fps)

# Read and write frames
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
for _ in range(end_frame - start_frame):
    ret, frame = cap.read()
    if not ret:
        break
    out.write(frame)

out.release()
cap.release()
```

**Pros:**
- No FFmpeg binary needed
- Pure Python + numpy
- Fast frame-by-frame processing

**Cons:**
- No built-in audio handling (video only)
- Codec support varies by platform
- More verbose code

**Install:**
```bash
pip install opencv-python
```

---

### Option 4: Cloud Transcoding Service (Most Reliable)
**Best for:** Production reliability, no infrastructure concerns

| Service | Pricing | Pros |
|---------|---------|------|
| **Mux** | $0.04/min encoding | Simple API, webhooks |
| **Cloudflare Stream** | $1/1000 min | Cheap, fast, no egress |
| **AWS Elemental** | Pay per use | Enterprise-grade |
| **Shotstack** | Free tier 100/mo | Purpose-built for clips |

**Example (Shotstack):**
```python
import requests

response = requests.post(
    "https://api.shotstack.io/v1/render",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "timeline": {
            "tracks": [{
                "clips": [{
                    "asset": {
                        "type": "video",
                        "src": video_url,
                        "trim": start_time,
                        "length": 15
                    }
                }]
            }]
        },
        "output": {"format": "mp4", "resolution": "sd"}
    }
)
```

**Pros:**
- Zero infrastructure issues
- Handles any video format
- Scales automatically

**Cons:**
- Costs money
- Async (need webhook handling)
- Adds latency

---

## 🎯 My Recommendation

### For Railway (Immediate Fix)

Use **`imageio-ffmpeg`** - it's a drop-in replacement that bundles FFmpeg:

1. Replace in `requirements.txt`:
   ```
   ffmpeg-python==0.2.0
   ```
   With:
   ```
   imageio-ffmpeg==0.4.9
   ```

2. Update `video.py` imports:
   ```python
   from imageio_ffmpeg import get_ffmpeg_exe
   
   FFMPEG_PATH = get_ffmpeg_exe()
   ```

3. Replace all `'ffmpeg'` in cmd lists with `FFMPEG_PATH`

This will fix "FFmpeg not found" issues on Railway.

### For Long-term Stability

Consider **Shotstack** or **Mux** if video processing becomes critical - the cost ($0.04/min) is worth eliminating infrastructure headaches.

---

## 🐛 Debugging "Isn't Working"

To diagnose the actual error, add this logging to `video.py`:

```python
async def normalize_video(video_path: str, output_path: str) -> bool:
    from imageio_ffmpeg import get_ffmpeg_exe
    
    ffmpeg_path = get_ffmpeg_exe()
    print(f"Using FFmpeg: {ffmpeg_path}")
    print(f"Input exists: {os.path.exists(video_path)}")
    print(f"Input size: {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
    
    cmd = [
        ffmpeg_path,
        '-y',
        '-i', video_path,
        # ... rest of args
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"FFmpeg exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"FFmpeg stderr:\n{result.stderr}")
        return False
    
    print(f"Output exists: {os.path.exists(output_path)}")
    return True
```

This will reveal:
- Is FFmpeg binary found?
- Is input file accessible?
- What is the actual FFmpeg error?
- Is output being created?

---

## 📝 Implementation Priority

1. **Today:** Add `imageio-ffmpeg`, deploy, test
2. **This week:** Add detailed logging to diagnose issues
3. **Next sprint:** Evaluate cloud transcoding if issues persist

Want me to implement the `imageio-ffmpeg` fix now?
