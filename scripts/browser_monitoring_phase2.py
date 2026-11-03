"""Optional real-browser rendering check after verify_phase2.py.

Uses requirements-browser.txt and an installed Edge (--channel msedge) or Chromium.
Credentials remain in the local browser context; screenshots are ignored artifacts.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main(channel=None):
    env={line.split('=',1)[0]:line.split('=',1)[1] for line in Path('.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#')}
    proof=json.loads(Path('data/phase2-verification.json').read_text())
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,**({'channel':channel} if channel else {}))
        try:
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.goto('http://localhost:3000/login')
            page.locator('input[name="user"]').fill(env['GRAFANA_ADMIN_USER'])
            page.locator('input[name="password"]').fill(env['GRAFANA_ADMIN_PASSWORD'])
            page.get_by_role('button',name='Log in',exact=True).click()
            page.wait_for_url(lambda url:'/login' not in url,timeout=30000)
            page.goto('http://localhost:3000/d/grievance-phase2')
            expect(page.get_by_text('API requests / second',exact=True)).to_be_visible(timeout=30000)
            expect(page.locator('canvas').first).to_be_visible(timeout=30000)
            page.screenshot(path='data/phase2-grafana.png',full_page=True)
            print('PASS Grafana dashboard renders charts in a real browser')
            page.goto('http://localhost:16686/trace/'+proof['trace_id'])
            expect(page.get_by_text('agent.investigator',exact=False).first).to_be_visible(timeout=30000)
            expect(page.get_by_text('result.store',exact=False).first).to_be_visible(timeout=30000)
            page.screenshot(path='data/phase2-jaeger.png',full_page=True)
            print('PASS Jaeger displays the verified end-to-end trace in a real browser')
        finally:
            browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--channel',default=None)
    main(parser.parse_args().channel)
