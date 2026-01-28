import os
import glob
from moviepy import VideoFileClip, concatenate_videoclips

# Configuration
VIDEO_DIR = "videos"
OUTPUT_FILE = "outputs/terracube_demo_final.mp4"

def process_video():
    # Find the latest video file recorded by Playwright
    video_files = glob.glob(os.path.join(VIDEO_DIR, "*.webm"))
    if not video_files:
        print("No video files found.")
        return

    latest_video = max(video_files, key=os.path.getctime)
    print(f"Processing latest video: {latest_video}")

    try:
        # Load the clip
        clip = VideoFileClip(latest_video)
        
        # In a real scenario, we might want to trim pauses or add transitions
        # For now, we'll just convert it to mp4 for better compatibility
        final_clip = clip # We could add .subclip(start, end) here
        
        final_clip.write_videofile(OUTPUT_FILE, codec="libx264")
        print(f"Final video saved to: {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error processing video: {e}")

if __name__ == "__main__":
    process_video()
