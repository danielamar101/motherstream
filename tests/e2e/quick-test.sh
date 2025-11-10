#!/bin/bash
# Quick test runner - runs a fast stress test to verify setup

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║              🚀 QUICK E2E TEST (30 seconds) 🚀                 ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if video exists
if [ ! -f "videos/test-video.mp4" ]; then
    echo "❌ Test video not found!"
    echo ""
    echo "Download it first:"
    echo "  ./scripts/download-test-video.sh"
    echo ""
    echo "Or use your own video:"
    echo "  cp /path/to/video.mp4 videos/test-video.mp4"
    echo ""
    exit 1
fi

echo "✅ Test video found"
echo "🎬 Running simultaneous connection test..."
echo ""

# Run the simultaneous test (fastest scenario)
./motherstream-stress-test.sh simultaneous

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║                    ✅ QUICK TEST COMPLETE! ✅                   ║"
echo "║                                                                ║"
echo "║  Your setup is working! Ready for comprehensive tests.         ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📚 Next steps:"
echo "  • Run full test suite:  ./motherstream-stress-test.sh all"
echo "  • Run orderly test:     ./motherstream-stress-test.sh orderly"
echo "  • Run chaos mode:       ./motherstream-stress-test.sh chaos"
echo ""
echo "📖 See README.md for complete documentation"
echo ""

