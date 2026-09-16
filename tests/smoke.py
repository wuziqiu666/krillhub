"""Browser regression tests. Runtime assets have no Python/npm dependency.

python -m pip install playwright
python -m playwright install chromium
python tests/smoke.py

Use --in-memory when browser navigation is unavailable in a sandbox. That mode
checks the same HTML/CSS/JS through DOM injection, not HTTP/file asset loading.
CHROMIUM_EXECUTABLE optionally selects an already installed Chromium binary.
"""
import argparse
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
parser = argparse.ArgumentParser()
parser.add_argument('--in-memory', action='store_true')
ARGS, REMAINING = parser.parse_known_args()


class OceanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        options = {'headless': True}
        if os.environ.get('CHROMIUM_EXECUTABLE'):
            options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
        cls.browser = cls.playwright.chromium.launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.errors = []
        self.context = self.browser.new_context(
            viewport={'width': 1440, 'height': 900}, reduced_motion='reduce'
        )
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.load(self.page)

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], 'Unexpected JavaScript errors')

    def load(self, page):
        if ARGS.in_memory:
            html = (PUBLIC / 'index.html').read_text(encoding='utf-8')
            html = html.replace('<link rel="stylesheet" href="./style.css">', '')
            html = html.replace('<script src="./app.js" defer></script>', '')
            page.set_content(html)
            page.add_style_tag(path=str(PUBLIC / 'style.css'))
            page.add_script_tag(path=str(PUBLIC / 'app.js'))
        else:
            page.goto((PUBLIC / 'index.html').as_uri())
        page.wait_for_function("document.querySelector('#scene').dataset.motion !== undefined")
        page.wait_for_timeout(100)

    def camera(self):
        return self.page.evaluate("""() => {
          const s = document.querySelector('#scene');
          return {x: +s.dataset.cameraX, y: +s.dataset.cameraY,
                  zoom: +s.dataset.zoom, mode: s.dataset.mode};
        }""")

    def snapshot(self):
        return self.page.locator('#krill-mid > g').first.get_attribute('transform')

    def test_static_contract(self):
        html = (PUBLIC / 'index.html').read_text(encoding='utf-8')
        self.assertIn('src="./app.js" defer', html)
        self.assertIn('href="./style.css"', html)
        self.assertNotIn('<canvas', html)
        self.assertEqual(self.page.locator('canvas, iframe, video').count(), 0)
        self.assertGreater(self.page.locator('.krill').count(), 160)
        config = json.loads((ROOT / 'wrangler.workers.jsonc').read_text())
        self.assertEqual(config['assets']['directory'], './public')
        self.assertTrue((PUBLIC / '404.html').is_file())
        self.assertIn("script-src 'self'", (PUBLIC / '_headers').read_text())

    def test_reduced_motion_starts_paused(self):
        self.assertEqual(self.page.locator('#scene').get_attribute('data-motion'), 'paused')
        first = self.snapshot()
        self.page.wait_for_timeout(150)
        self.assertEqual(first, self.snapshot())

    def test_play_pause(self):
        first = self.snapshot()
        self.page.locator('#pause-button').click()
        self.page.wait_for_timeout(200)
        self.assertNotEqual(first, self.snapshot())
        self.page.locator('#pause-button').click()
        first = self.snapshot()
        self.page.wait_for_timeout(150)
        self.assertEqual(first, self.snapshot())

    def test_speed_cycle(self):
        button = self.page.locator('#speed-button')
        for expected in ['2×', '0.5×', '1×']:
            button.click()
            self.assertEqual(button.inner_text(), expected)

    def test_drag(self):
        before = self.camera()
        self.page.mouse.move(1100, 650)
        self.page.mouse.down()
        self.page.mouse.move(1200, 710, steps=8)
        self.page.mouse.up()
        self.assertLess(self.camera()['x'], before['x'] - 80)
        self.assertLess(self.camera()['y'], before['y'] - 50)
        self.assertNotIn('dragging', self.page.locator('#scene').get_attribute('class') or '')

    def test_wheel_zoom_preserves_anchor(self):
        x, y = 1100, 650
        before = self.camera()
        base = max(1440 / 1600, 900 / 1000)
        def unproject(c):
            return (c['x'] + (x - 720) / (base * c['zoom']),
                    c['y'] + (y - 450) / (base * c['zoom']))
        anchor = unproject(before)
        self.page.mouse.move(x, y)
        self.page.mouse.wheel(0, -180)
        self.page.wait_for_timeout(100)
        after = self.camera()
        self.assertGreater(after['zoom'], 1)
        for a, b in zip(anchor, unproject(after)):
            self.assertAlmostEqual(a, b, delta=.2)

    def test_zoom_limits(self):
        self.page.locator('#scene').focus()
        for _ in range(20):
            self.page.keyboard.press('=')
        self.assertAlmostEqual(self.camera()['zoom'], 4)
        self.assertTrue(self.page.locator('#zoom-in').is_disabled())
        for _ in range(25):
            self.page.keyboard.press('-')
        self.assertAlmostEqual(self.camera()['zoom'], .6)
        self.assertTrue(self.page.locator('#zoom-out').is_disabled())

    def test_focus_and_cancel(self):
        self.page.locator('#focus-button').click()
        self.assertEqual(self.camera()['mode'], 'follow')
        self.assertGreater(self.camera()['zoom'], 1)
        self.assertTrue(self.page.locator('#selection-card').is_visible())
        self.assertEqual(self.page.locator('#reticle').get_attribute('visibility'), 'visible')
        self.page.keyboard.press('Escape')
        self.assertEqual(self.camera()['mode'], 'free')
        self.assertTrue(self.page.locator('#selection-card').is_hidden())

    def test_click_animal(self):
        point = self.page.evaluate("""() => {
          for (const n of document.querySelectorAll('#krill-mid > g')) {
            const m = n.getScreenCTM();
            if (m.e > 650 && m.e < 1200 && m.f > 300 && m.f < 620)
              return {x: m.e, y: m.f};
          }
        }""")
        self.assertIsNotNone(point)
        self.page.mouse.click(point['x'], point['y'])
        self.assertEqual(self.camera()['mode'], 'follow')

    def test_double_click_detail(self):
        self.page.mouse.dblclick(1300, 230)
        self.assertGreaterEqual(self.camera()['zoom'], 2.5)
        self.assertEqual(self.camera()['mode'], 'free')

    def test_follow_moves_camera(self):
        self.page.locator('#focus-button').click()
        before = self.camera()
        self.page.locator('#pause-button').click()
        self.page.wait_for_timeout(300)
        self.assertEqual(self.camera()['mode'], 'follow')
        self.assertGreater(self.camera()['x'], before['x'])

    def test_reset(self):
        self.page.locator('#focus-button').click()
        self.page.locator('#reset-button').click()
        self.assertEqual(self.camera(), {'x': 800, 'y': 500, 'zoom': 1, 'mode': 'overview'})
        self.assertFalse(self.page.locator('body').evaluate("el => el.classList.contains('exploring')"))

    def test_keyboard(self):
        self.page.locator('#scene').focus()
        before = self.camera()['x']
        self.page.keyboard.press('ArrowRight')
        self.assertGreater(self.camera()['x'], before)
        self.page.keyboard.press('f')
        self.assertEqual(self.camera()['mode'], 'follow')
        self.page.keyboard.press('0')
        self.assertEqual(self.camera()['mode'], 'overview')
        self.page.keyboard.press('Space')
        self.assertEqual(self.page.locator('#scene').get_attribute('data-motion'), 'playing')

    def test_button_space_toggles_only_once(self):
        self.page.locator('#pause-button').focus()
        self.page.keyboard.press('Space')
        self.assertEqual(self.page.locator('#scene').get_attribute('data-motion'), 'playing')

    def test_immersive(self):
        self.page.locator('#immersive-button').click()
        self.assertTrue(self.page.locator('#exit-immersive').is_visible())
        self.assertTrue(self.page.locator('.header').evaluate('el => el.inert'))
        self.page.keyboard.press('i')
        self.assertTrue(self.page.locator('#exit-immersive').is_hidden())
        self.assertFalse(self.page.locator('.header').evaluate('el => el.inert'))

    def test_dialog_and_pause(self):
        self.page.locator('#pause-button').click()
        self.page.locator('#help-button').click()
        self.assertTrue(self.page.locator('#about-dialog').is_visible())
        first = self.snapshot()
        self.page.wait_for_timeout(150)
        self.assertEqual(first, self.snapshot())
        self.page.keyboard.press('Escape')
        self.assertFalse(self.page.locator('#about-dialog').is_visible())
        self.page.wait_for_timeout(150)
        self.assertNotEqual(first, self.snapshot())

    def test_responsive_layout(self):
        for width, height in [(390, 844), (320, 568), (844, 390), (768, 1024), (1920, 1080)]:
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({'width': width, 'height': height})
                self.page.wait_for_timeout(80)
                self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                box = self.page.locator('.camera-tools').bounding_box()
                self.assertGreaterEqual(box['x'], 0)
                self.assertLessEqual(box['x'] + box['width'], width + 1)
                self.assertLessEqual(box['y'] + box['height'], height)

    def test_touch_pinch_and_cancel(self):
        context = self.browser.new_context(viewport={'width': 390, 'height': 844},
                                           has_touch=True, is_mobile=True, reduced_motion='reduce')
        try:
            page = context.new_page()
            page.on('pageerror', lambda error: self.errors.append(str(error)))
            self.load(page)
            cdp = context.new_cdp_session(page)
            def touch(kind, points):
                cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': points})
            touch('touchStart', [{'x': 125, 'y': 540, 'id': 1}, {'x': 265, 'y': 540, 'id': 2}])
            touch('touchMove', [{'x': 65, 'y': 540, 'id': 1}, {'x': 325, 'y': 540, 'id': 2}])
            touch('touchEnd', [])
            page.wait_for_timeout(100)
            self.assertGreater(float(page.locator('#scene').get_attribute('data-zoom')), 1.5)
            before = float(page.locator('#scene').get_attribute('data-camera-x'))
            touch('touchStart', [{'x': 160, 'y': 540, 'id': 3}])
            touch('touchMove', [{'x': 220, 'y': 570, 'id': 3}])
            touch('touchCancel', [])
            page.wait_for_timeout(100)
            self.assertLess(float(page.locator('#scene').get_attribute('data-camera-x')), before)
            self.assertNotIn('dragging', page.locator('#scene').get_attribute('class') or '')
        finally:
            context.close()


if __name__ == '__main__':
    unittest.main(argv=[__file__, *REMAINING], verbosity=2)
