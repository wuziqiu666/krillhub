"""Playwright language/interaction regression tests.

python -m pip install playwright
python -m playwright install chromium
python tests/i18n_browser.py

--in-memory is for restricted sandboxes: inject the same HTML/CSS/JS, and
explicitly skip actual URL navigation. It does not verify HTTP, CSP, Cloudflare
routing, search-engine indexing, or a real device. The default runs over local
HTTP, with the static CSP from public/_headers applied by the test server.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from threading import Thread
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
parser = argparse.ArgumentParser()
parser.add_argument('--in-memory', action='store_true')
parser.add_argument('--screenshots', type=Path)
ARGS, REMAINING = parser.parse_known_args()
CATALOGS = {code: json.loads((ROOT / f'locales/{code}.json').read_text()) for code in ('en', 'zh')}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        for line in (PUBLIC / '_headers').read_text().splitlines():
            if line.strip().startswith('Content-Security-Policy:'):
                self.send_header('Content-Security-Policy', line.split(':', 1)[1].strip())
        super().end_headers()


class LanguageBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        options = {'headless': True}
        if os.environ.get('CHROMIUM_EXECUTABLE'):
            options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
        cls.browser = cls.playwright.chromium.launch(**options)
        cls.server = None
        if not ARGS.in_memory:
            cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(PUBLIC)))
            Thread(target=cls.server.serve_forever, daemon=True).start()
            cls.origin = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def setUp(self):
        self.contexts = []
        self.errors = []

    def tearDown(self):
        for context in self.contexts:
            context.close()
        self.assertEqual(self.errors, [], 'Unexpected JavaScript errors')

    def load(self, code, size=(1440, 900), javascript=True, touch=False):
        context = self.browser.new_context(
            viewport={'width': size[0], 'height': size[1]}, reduced_motion='reduce',
            locale='zh-CN' if code == 'en' else 'en-US', java_script_enabled=javascript,
            has_touch=touch, is_mobile=touch,
        )
        self.contexts.append(context)
        page = context.new_page()
        page.set_default_timeout(5000)
        page.on('pageerror', lambda error: self.errors.append(str(error)))
        path = 'index.html' if code == 'en' else 'zh/index.html'
        if ARGS.in_memory:
            text = (PUBLIC / path).read_text()
            text = re.sub(r'<link rel="stylesheet"[^>]+>', '', text)
            text = re.sub(r'<script src="[^\"]+" defer></script>', '', text)
            page.set_content(text)
            page.add_style_tag(path=str(PUBLIC / 'style.css'))
            if javascript:
                page.add_script_tag(path=str(PUBLIC / 'app.js'))
        else:
            response = page.goto(self.origin + ('/' if code == 'en' else '/zh/'))
            self.assertEqual(response.status, 200)
        if javascript:
            page.wait_for_function("document.querySelector('#scene').dataset.motion === 'paused'")
        page.evaluate('document.fonts.ready')
        page.wait_for_timeout(100)
        return page

    def test_explicit_language_and_initial_reduced_motion(self):
        for code, lang in [('en', 'en'), ('zh', 'zh-Hans')]:
            page = self.load(code)
            self.assertEqual(page.locator('html').get_attribute('lang'), lang)
            self.assertEqual(page.title(), CATALOGS[code]['text']['page_title'])
            self.assertGreater(page.locator('.krill').count(), 160)
            self.assertEqual(page.locator('#pause-button').get_attribute('aria-label'), CATALOGS[code]['messages']['play'])
            animal = page.locator('#krill-mid > g').first
            first = animal.get_attribute('transform')
            page.wait_for_timeout(80)
            self.assertEqual(first, animal.get_attribute('transform'))

    def test_translated_play_pause_and_speed(self):
        for code in ('en', 'zh'):
            page = self.load(code)
            messages = CATALOGS[code]['messages']
            animal = page.locator('#krill-mid > g').first
            first = animal.get_attribute('transform')
            page.locator('#pause-button').click()
            page.wait_for_timeout(100)
            self.assertNotEqual(first, animal.get_attribute('transform'))
            self.assertEqual(page.locator('#pause-button').get_attribute('aria-label'), messages['pause'])
            self.assertEqual(page.locator('#motion-label').inner_text(), messages['motion-playing'])
            page.locator('#pause-button').click()
            self.assertEqual(page.locator('#motion-label').inner_text(), messages['motion-paused'])
            for speed in (2, .5, 1):
                page.locator('#speed-button').click()
                text = messages['speed'].replace('{speed}', str(speed))
                self.assertEqual(page.locator('#speed-button').get_attribute('aria-label'), text)

    def test_translated_focus_reset_and_immersive(self):
        for code in ('en', 'zh'):
            page = self.load(code)
            messages = CATALOGS[code]['messages']
            page.locator('#focus-button').click()
            self.assertEqual(page.locator('#scene').get_attribute('data-mode'), 'follow')
            label = page.locator('#reticle-label').text_content()
            self.assertEqual(page.locator('#selection-label').inner_text(), messages['following'].replace('{label}', label))
            page.locator('#unfollow-button').click()
            expect(page.locator('#selection-card')).to_be_hidden()
            page.locator('#reset-button').click()
            self.assertEqual(page.locator('#scene').get_attribute('data-mode'), 'overview')
            page.locator('#immersive-button').click()
            self.assertEqual(page.locator('#immersive-button').get_attribute('aria-label'), messages['exit-immersive'])
            self.assertTrue(page.locator('.header').evaluate('el => el.inert'))
            page.keyboard.press('Escape')
            self.assertEqual(page.locator('#immersive-button').get_attribute('aria-label'), messages['enter-immersive'])

    def test_dialog_and_fullscreen_failure_messages(self):
        for code in ('en', 'zh'):
            page = self.load(code)
            page.locator('#help-button').click()
            expect(page.locator('#about-dialog')).to_be_visible()
            self.assertEqual(page.locator('#about-title').inner_text(), CATALOGS[code]['text']['about_title'])
            page.keyboard.press('Escape')
            page.evaluate("() => { document.documentElement.requestFullscreen = () => Promise.reject(new Error('Test rejection')); }")
            page.locator('#fullscreen-button').evaluate('el => el.click()')
            expect(page.locator('#toast')).to_have_text(CATALOGS[code]['messages']['fullscreen-unavailable'])

    def test_responsive_layout_and_language_controls(self):
        for code in ('en', 'zh'):
            for size in ((320, 568), (390, 844), (768, 1024), (844, 390), (1440, 900)):
                with self.subTest(code=code, size=size):
                    page = self.load(code, size)
                    sizes = page.evaluate('({scroll:document.documentElement.scrollWidth, viewport:innerWidth})')
                    self.assertLessEqual(sizes['scroll'], sizes['viewport'], str(sizes))
                    for selector in ('.language-switch', '.header-actions', '.brand', '.camera-tools'):
                        box = page.locator(selector).bounding_box()
                        self.assertGreaterEqual(box['x'], 0, selector)
                        self.assertLessEqual(box['x'] + box['width'], size[0] + 1, selector)
                        self.assertLessEqual(box['y'] + box['height'], size[1] + 1, selector)
                    brand = page.locator('.brand').bounding_box()
                    actions = page.locator('.header-actions').bounding_box()
                    self.assertLessEqual(brand['x'] + brand['width'], actions['x'])
                    self.assertEqual(page.locator('#help-button').get_attribute('aria-label'), CATALOGS[code]['text']['about'])
                    if ARGS.screenshots and size in ((390, 844), (1440, 900)):
                        ARGS.screenshots.mkdir(parents=True, exist_ok=True)
                        name = 'mobile' if size[0] == 390 else 'desktop'
                        page.screenshot(path=str(ARGS.screenshots / f'{code}-{name}.png'))
                    page.close()

    def test_pan_zoom_keyboard_and_touch(self):
        for code in ('en', 'zh'):
            page = self.load(code)
            camera = lambda: page.locator('#scene').evaluate('el => ({x:+el.dataset.cameraX, zoom:+el.dataset.zoom, mode:el.dataset.mode})')
            before = camera()
            page.mouse.move(1100, 650)
            page.mouse.down()
            page.mouse.move(1200, 710, steps=5)
            page.mouse.up()
            self.assertLess(camera()['x'], before['x'])
            page.mouse.wheel(0, -180)
            page.wait_for_timeout(80)
            self.assertGreater(camera()['zoom'], 1)
            page.locator('#scene').focus()
            page.keyboard.press('f')
            self.assertEqual(camera()['mode'], 'follow')
            page.keyboard.press('0')
            self.assertEqual(camera()['mode'], 'overview')
            mobile = self.load(code, (390, 844), touch=True)
            cdp = mobile.context.new_cdp_session(mobile)
            cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':125,'y':540,'id':1},{'x':265,'y':540,'id':2}]})
            cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':65,'y':540,'id':1},{'x':325,'y':540,'id':2}]})
            cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
            self.assertGreater(float(mobile.locator('#scene').get_attribute('data-zoom')), 1.5)

    @unittest.skipIf(ARGS.in_memory, 'Disabled-JS browser loading requires HTTP mode; static source is checked separately')
    def test_content_exists_without_javascript(self):
        for code in ('en', 'zh'):
            page = self.load(code, javascript=False)
            self.assertEqual(page.locator('#page-title').inner_text().replace('\n', ''), CATALOGS[code]['text']['hero_one'] + CATALOGS[code]['text']['hero_two'])
            self.assertEqual(page.locator('.language-switch a').count(), 2)
            expect(page.locator('.noscript')).to_be_visible()
            self.assertEqual(page.locator('#krill-mid > g').count(), 0)

    @unittest.skipIf(ARGS.in_memory, 'Actual HTTP navigation is unavailable in in-memory mode')
    def test_native_language_navigation_and_back(self):
        page = self.load('en')
        page.locator('.language-switch a[hreflang="zh-Hans"]').click()
        page.wait_for_url(self.origin + '/zh/')
        self.assertEqual(page.title(), CATALOGS['zh']['text']['page_title'])
        page.locator('.language-switch a[hreflang="en"]').focus()
        page.keyboard.press('Enter')
        page.wait_for_url(self.origin + '/')
        self.assertEqual(page.title(), CATALOGS['en']['text']['page_title'])
        page.go_back()
        self.assertEqual(urlsplit(page.url).path, '/zh/')

    @unittest.skipIf(ARGS.in_memory, 'Actual no-JS navigation requires HTTP mode')
    def test_language_navigation_without_javascript(self):
        page = self.load('en', javascript=False)
        page.locator('.language-switch a[hreflang="zh-Hans"]').click()
        page.wait_for_url(self.origin + '/zh/')
        self.assertEqual(page.title(), CATALOGS['zh']['text']['page_title'])


if __name__ == '__main__':
    unittest.main(argv=[__file__, *REMAINING], verbosity=2)
