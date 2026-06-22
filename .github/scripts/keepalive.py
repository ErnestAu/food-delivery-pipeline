import os
import time
from playwright.sync_api import sync_playwright

APP_URL = os.environ["APP_URL"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(APP_URL, timeout=60_000)

        try:
            page.get_by_text("get this app back up", exact=False).click(timeout=8_000)
            print("App was asleep — clicked the wake button.")
        except Exception:
            print("App appears to already be awake.")

        time.sleep(15)  # let it boot + register an active session
        browser.close()
        print("Ping complete.")


if __name__ == "__main__":
    main()