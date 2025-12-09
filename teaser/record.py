"""Record the teaser animation as MP4 using Playwright."""

from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="./",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Load the page
        page.goto(f"file:///Users/brentyi/tyro/teaser/index.html")

        # Wait for animation to complete (roughly 10 seconds should be enough)
        time.sleep(12)

        # Close to save the video
        context.close()
        browser.close()

    print("Video saved!")

if __name__ == "__main__":
    main()
