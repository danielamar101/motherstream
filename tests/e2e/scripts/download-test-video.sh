#!/bin/bash
# Download multiple test videos for stress testing
# Each user will get a different video for variety

VIDEO_DIR="../videos"
mkdir -p "$VIDEO_DIR"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║    🎬 Downloading Test Videos for Motherstream Stress Tests   ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Array of test videos (small, freely available)
declare -A VIDEOS=(
    ["video1"]="https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_30fps_normal.mp4"
    ["video2"]="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
    ["video3"]="https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
)

SUCCESS_COUNT=0
TOTAL_COUNT=${#VIDEOS[@]}

for video_name in "${!VIDEOS[@]}"; do
    VIDEO_URL="${VIDEOS[$video_name]}"
    VIDEO_FILE="$VIDEO_DIR/${video_name}.mp4"
    
    echo "📥 Downloading $video_name..."
    echo "   Source: $VIDEO_URL"
    echo "   Destination: $VIDEO_FILE"
    
    if [ -f "$VIDEO_FILE" ]; then
        echo "   ✅ Already exists (skipping)"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        if wget -q -O "$VIDEO_FILE" "$VIDEO_URL" 2>/dev/null; then
            SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
            echo "   ✅ Downloaded ($SIZE)"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo "   ⚠️  Download failed (will try alternative)"
            rm -f "$VIDEO_FILE"
        fi
    fi
    echo ""
done

echo "════════════════════════════════════════════════════════════════"
echo ""

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo "✅ Successfully downloaded/verified $SUCCESS_COUNT video(s)!"
    echo ""
    echo "📁 Videos available:"
    for video in "$VIDEO_DIR"/*.mp4; do
        if [ -f "$video" ]; then
            SIZE=$(du -h "$video" | cut -f1)
            NAME=$(basename "$video")
            echo "   • $NAME ($SIZE)"
            
            # Get video info if ffprobe is available
            if command -v ffprobe &> /dev/null; then
                DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$video" 2>/dev/null | xargs printf "%.0f")
                echo "     Duration: ${DURATION}s"
            fi
        fi
    done
    
    echo ""
    echo "🎉 Ready to run stress tests!"
    echo ""
    echo "Each of the 10 test users will stream a different video."
    echo ""
    echo "Quick start:"
    echo "  cd .."
    echo "  ./quick-test.sh"
    echo ""
    echo "Full test:"
    echo "  ./motherstream-stress-test.sh all"
    echo ""
else
    echo "❌ No videos were downloaded successfully!"
    echo ""
    echo "💡 Alternative options:"
    echo ""
    echo "1. Use your own videos:"
    echo "   cp /path/to/your/video*.mp4 $VIDEO_DIR/"
    echo ""
    echo "2. Try manual download:"
    echo "   wget https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_30fps_normal.mp4 -O $VIDEO_DIR/video1.mp4"
    echo ""
    exit 1
fi

