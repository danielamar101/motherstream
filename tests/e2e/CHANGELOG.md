# E2E Stress Test Changelog

## ✨ **Enhancements - Multiple Videos & Auto User Creation**

### New Features

#### 🎬 **Multiple Video Support**
- Each of the 10 test users now streams a **different video**
- Videos are automatically cycled (User 1 → Video 1, User 2 → Video 2, etc.)
- More realistic testing with variety
- Script automatically discovers all videos in `videos/` directory
- Supports: `.mp4`, `.avi`, `.mkv`, `.mov` formats

#### 👥 **Automatic User Creation via API**
- Test users are now **automatically created** via API
- No manual user setup required!
- Creates 10 users: `stresstest1@motherstream.test` through `stresstest10@motherstream.test`
- Each user gets:
  - Unique email: `stresstestN@motherstream.test`
  - Unique DJ name: `StressTestDJ_N`
  - Unique stream key: `stress_test_user_N`
  - Password: `TestPass123!N`
- User data saved to `logs/test-users.json` for reference
- Users are reused on subsequent runs (idempotent)

### Updated Download Script

The `download-test-video.sh` script now downloads **3 different videos**:
- `video1.mp4` - Big Buck Bunny (full quality)
- `video2.mp4` - Big Buck Bunny (compressed)
- `video3.mp4` - Big Buck Bunny (360p short)

This provides variety for the 10 concurrent users (videos cycle: 1,2,3,1,2,3,1,2,3,1).

### Benefits

1. **More Realistic Testing**
   - Different video content simulates real-world usage
   - Different video sizes/bitrates test bandwidth handling
   - Easier to identify which user is which by video

2. **Zero Manual Setup**
   - Just run `./scripts/download-test-video.sh` once
   - Then `./motherstream-stress-test.sh` handles everything
   - Users are created automatically on first run
   - No database manual entry needed

3. **Better Debugging**
   - Each user streams different content
   - Easy to visually identify which stream is which
   - User data logged to `logs/test-users.json`

### Usage

```bash
cd tests/e2e

# Download videos (first time only)
./scripts/download-test-video.sh

# Run test - users created automatically!
./quick-test.sh
```

### Output Example

```
[API] Creating user 1: stresstest1@motherstream.test / StressTestDJ_1
[SUCCESS] ✓ User 1 ready: StressTestDJ_1 (key: stress_test_user_1)
[API] Creating user 2: stresstest2@motherstream.test / StressTestDJ_2
[SUCCESS] ✓ User 2 ready: StressTestDJ_2 (key: stress_test_user_2)
...
[SUCCESS] Created/verified 10 test users
[INFO] User data saved to: logs/test-users.json

Found 3 video(s)
  Video 1: video1.mp4
  Video 2: video2.mp4
  Video 3: video3.mp4

[STREAM] User 1 starting stream (duration: 25s, video: video1.mp4, key: stress_test_user_1)
[STREAM] User 2 starting stream (duration: 25s, video: video2.mp4, key: stress_test_user_2)
[STREAM] User 3 starting stream (duration: 25s, video: video3.mp4, key: stress_test_user_3)
```

### Video Distribution

With 10 users and 3 videos:
- Users 1, 4, 7, 10 → `video1.mp4`
- Users 2, 5, 8 → `video2.mp4`
- Users 3, 6, 9 → `video3.mp4`

### Migration Notes

**No breaking changes!** The script is fully backward compatible:
- If only one video exists, all users use that video
- If users already exist in database, they are reused
- Manual user setup still works if preferred

### Technical Details

**Video Discovery:**
- Scans `videos/` directory for all `.mp4`, `.avi`, `.mkv`, `.mov` files
- Sorts alphabetically for consistent user-to-video mapping
- Logs which videos are found

**User Creation:**
- POSTs to `/api/users/register` endpoint
- Handles "already exists" gracefully (idempotent)
- Rate limited (0.5s between requests)
- Saves user data to JSON for debugging

**Video Assignment:**
- Uses modulo arithmetic: `video_index = user_id % num_videos`
- Ensures even distribution
- Predictable and deterministic

### Future Enhancements

Potential future additions:
- [ ] Option to use random videos per user
- [ ] Support for video playlists
- [ ] Different video per scenario
- [ ] Video quality settings per user
- [ ] User cleanup command

---

**Version:** Enhanced  
**Date:** 2025-11-10  
**Status:** ✅ Production Ready

