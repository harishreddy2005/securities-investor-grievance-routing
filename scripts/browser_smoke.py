"""Check the date/prior-complaint form regressions in a real browser.

Install requirements-browser.txt, then run against the running app:
python scripts/browser_smoke.py --channel msedge
Or install Playwright Chromium and omit --channel.
"""
import argparse
from datetime import date, timedelta

from playwright.sync_api import expect, sync_playwright


def run(base_url, channel=None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({"channel": channel} if channel else {}))
        try:
            page = browser.new_page()
            page.goto(base_url)
            posts = []
            page.on("request", lambda request: posts.append(request.post_data_json)
                    if request.method == "POST" and request.url.endswith("/api/v1/grievances") else None)
            prior, reply = page.locator("#prior-date"), page.locator("#reply-date")
            checkbox, submit, status = page.locator("#approached"), page.locator("#submit"), page.locator("#status")
            expect(prior).to_be_disabled()
            expect(reply).to_be_disabled()
            checkbox.check()
            prior.fill((date.today()-timedelta(days=10)).isoformat())
            reply.fill((date.today()-timedelta(days=2)).isoformat())
            page.locator("#reply").select_option("unsatisfactory")
            checkbox.uncheck()
            expect(prior).to_be_disabled()
            expect(prior).to_have_value("")
            expect(reply).to_have_value("")
            expect(page.locator("#reply")).to_have_value("none")
            print("PASS prior complaint fields disabled and cleared when unchecked")

            checkbox.check()
            prior.fill("1202-01-01")
            submit.click()
            expect(status).to_contain_text("1900")
            assert not posts, "Ancient date reached the queue submission endpoint"
            prior.fill((date.today()+timedelta(days=1)).isoformat())
            submit.click()
            expect(status).to_contain_text("today")
            assert not posts, "Future date reached the queue submission endpoint"
            prior.fill((date.today()-timedelta(days=2)).isoformat())
            reply.fill((date.today()-timedelta(days=10)).isoformat())
            submit.click()
            expect(status).to_contain_text("before the complaint date")
            assert not posts, "Reversed dates reached the queue submission endpoint"
            print("PASS ancient, future, and reversed dates blocked before submission")

            checkbox.uncheck()
            submit.click()
            expect(page.locator("#result")).to_be_visible(timeout=90000)
            expect(page.locator("#result h2")).to_contain_text("Reserve Bank of India")
            expect(page.locator("#result")).to_contain_text("First complain in writing to the bank")
            assert len(posts) == 1
            assert posts[0]["approached_entity_first"] is False
            assert not {"entity_complaint_date", "entity_response_date", "entity_response"} & posts[0].keys()
            print("PASS unchecked form submits without stale prior details and renders RBI result")

            def reject(route):
                route.fulfill(status=422, json={"detail": [{"loc": ["body", "entity_complaint_date"],
                    "type": "value_error", "msg": "Value error, Enter a date on or after 1 January 1900"}]})
            page.route("**/api/v1/grievances", reject)
            submit.click()
            expect(status).to_have_text("Complaint date: Enter a date on or after 1 January 1900")
            print("PASS backend validation errors display readable field messages")
            print("PASS browser form regression smoke")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args()
    run(args.base_url, args.channel)
