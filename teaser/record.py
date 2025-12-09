"""Record the teaser animation as MP4 using Playwright."""

from playwright.sync_api import sync_playwright
import time
import os
import shutil

def record_page(html_file: str, output_name: str):
    """Record a single HTML file."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1472, "height": 596},
            device_scale_factor=2,
            record_video_dir="./",
            record_video_size={"width": 2944, "height": 1192},
        )
        page = context.new_page()

        # Load the page
        page.goto(f"file:///Users/brentyi/tyro/teaser/{html_file}")

        # Wait for animation to complete
        time.sleep(15)

        # Get the video path before closing
        video_path = page.video.path()

        # Close to save the video
        context.close()
        browser.close()

        # Rename the video file
        if video_path and os.path.exists(video_path):
            new_path = f"/Users/brentyi/tyro/teaser/{output_name}.webm"
            shutil.move(video_path, new_path)
            print(f"Saved: {new_path}")

def main():
    record_page("dataclass.html", "dataclass")
    record_page("function.html", "function")
    print("All videos saved!")

if __name__ == "__main__":
    main()
