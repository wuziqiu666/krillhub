"""SVG LOD and interaction regression suite, including the language tests.

python tests/smoke.py                 # actual local HTTP + CSP, preferred
python tests/smoke.py --in-memory     # DOM injection; URL tests explicitly skipped
CHROMIUM_EXECUTABLE can point at an installed Chromium browser.
"""
import unittest
import i18n_browser as harness


class SwarmTests(harness.LanguageBrowserTests):
    def scene(self, page):
        return page.locator('#scene').evaluate('el => ({...el.dataset})')

    def zoom(self, page, presses):
        page.locator('#scene').focus()
        for _ in range(abs(presses)):
            page.keyboard.press('=' if presses > 0 else '-')
        page.wait_for_timeout(30)

    def assert_population_conserved(self, page):
        counts = page.evaluate("""() => ({
          population: +document.querySelector('#scene').dataset.population,
          dots: [...document.querySelectorAll('.swarm-dots')].reduce((n,p) => n + (p.getAttribute('d').match(/M/g)||[]).length, 0),
          shapes: [...document.querySelectorAll('.swarm-shapes')].reduce((n,p) => n + (p.getAttribute('d').match(/M/g)||[]).length / 2, 0),
          detailed: document.querySelectorAll('.krill').length
        })""")
        self.assertEqual(counts['dots'] + counts['detailed'], counts['population'])
        self.assertEqual(counts['shapes'] + counts['detailed'], counts['population'])
        state = self.scene(page)
        self.assertLessEqual(counts['detailed'], int(state['detailLimit']))
        self.assertEqual(counts['detailed'], int(state['detailCount']))

    def test_population_and_bounded_svg_dom(self):
        for size, population, budget in [((1440, 900), 21600, 224), ((390, 844), 9600, 96)]:
            page = self.load('en', size)
            s = self.scene(page)
            self.assertEqual(int(s['population']), population)
            self.assertEqual(int(s['detailLimit']), budget)
            self.assertEqual(int(s['detailCount']), 0)
            self.assertLess(page.locator('#scene *').count(), 800)
            self.assertEqual(page.locator('canvas, iframe, video').count(), 0)
            self.assert_population_conserved(page)

    def test_zoom_limits_and_culling(self):
        page = self.load('en')
        self.zoom(page, -30)
        self.assertAlmostEqual(float(self.scene(page)['zoom']), .2)
        self.assertTrue(page.locator('#zoom-out').is_disabled())
        self.assertEqual(int(self.scene(page)['detailCount']), 0)
        self.assertEqual(page.locator('#lod-label').text_content(), 'SWARM')
        self.assert_population_conserved(page)
        self.zoom(page, 40)
        self.assertAlmostEqual(float(self.scene(page)['zoom']), 24)
        self.assertTrue(page.locator('#zoom-in').is_disabled())
        self.assertGreater(page.locator('.swarm-patch[display="none"]').count(), 0)
        self.assert_population_conserved(page)

    def test_crossfade_weights_are_continuous_monotonic(self):
        page = self.load('en')
        values = page.evaluate('Array.from({length: 801}, (_,i) => KrillSwarm.weights(i/10))')
        for key in ('shape', 'detail'):
            self.assertEqual(values[0][key], 0)
            self.assertEqual(values[-1][key], 1)
            for before, after in zip(values, values[1:]):
                self.assertGreaterEqual(after[key], before[key])
                self.assertLess(after[key] - before[key], .02)
                self.assertTrue(0 <= after[key] <= 1)

    def test_repeated_lod_transitions_conserve_every_identity(self):
        page = self.load('en')
        first = page.locator('.swarm-dots').first.get_attribute('d')
        for step in (5, 5, -7, 9, -18, 13, -5):
            self.zoom(page, step)
            self.assert_population_conserved(page)
        page.locator('#reset-button').click()
        page.wait_for_timeout(40)
        self.assertEqual(page.locator('.swarm-dots').first.get_attribute('d'), first)
        self.assertEqual(int(self.scene(page)['detailCount']), 0)

    def test_click_on_batched_speck_promotes_same_animal(self):
        page = self.load('en')
        self.zoom(page, -9)
        point = page.evaluate(r"""() => {
          for (const path of document.querySelectorAll('.swarm-dots')) {
            const matrix = path.getScreenCTM();
            for (const match of path.getAttribute('d').matchAll(/M(-?[\d.]+) (-?[\d.]+)/g)) {
              const p = new DOMPoint(+match[1], +match[2]).matrixTransform(matrix);
              if (p.x > 400 && p.x < 1050 && p.y > 300 && p.y < 650) return {x:p.x,y:p.y};
            }
          }
        }""")
        self.assertIsNotNone(point)
        page.mouse.click(point['x'], point['y'])
        self.assertEqual(self.scene(page)['mode'], 'follow')
        label = page.locator('#reticle-label').text_content()
        animal_id = int(label.split()[-1]) - 1
        selected = page.locator(f'.krill[data-krill-id="{animal_id}"]')
        self.assertEqual(selected.count(), 1)
        self.assertGreater(float(selected.get_attribute('data-detail')), .95)
        page.wait_for_function('id => { const n=document.querySelector(`.krill[data-krill-id="${id}"]`); if(!n) return false; const m=n.getScreenCTM(); return Math.abs(m.e-720)<.2 && Math.abs(m.f-450)<.2; }', arg=str(animal_id))
        matrix = selected.evaluate('el => {const m=el.getScreenCTM();return {x:m.e,y:m.f}}')
        self.assertAlmostEqual(matrix['x'], 720, delta=.2)
        self.assertAlmostEqual(matrix['y'], 450, delta=.2)
        page.locator('#pause-button').click()
        page.wait_for_timeout(180)
        self.assertEqual(page.locator('#reticle-label').text_content(), label)
        self.assertEqual(selected.count(), 1)
        self.assert_population_conserved(page)

    def test_detail_budget_exhaustion_keeps_silhouettes(self):
        page = self.load('en')
        hit_cap = False
        for _ in range(13):
            self.zoom(page, 1)
            self.assert_population_conserved(page)
            s = self.scene(page)
            hit_cap |= int(s['detailCount']) == int(s['detailLimit'])
        self.assertTrue(hit_cap, 'Exercise the detail-budget fallback, not just light scenes')

    def test_mobile_focus_and_rotation_preserve_population(self):
        page = self.load('zh', (390, 844), touch=True)
        page.locator('#focus-button').click()
        label = page.locator('#reticle-label').text_content()
        self.assertEqual(page.locator('#lod-label').text_content(), '近观')
        for size in ((844, 390), (320, 568), (390, 844)):
            page.set_viewport_size({'width': size[0], 'height': size[1]})
            page.wait_for_timeout(60)
            self.assertEqual(self.scene(page)['population'], '9600')
            self.assertEqual(page.locator('#reticle-label').text_content(), label)
            self.assert_population_conserved(page)

    def test_wheel_anchor_at_far_and_near_scale(self):
        page = self.load('en')
        x, y, base = 1050, 580, .9
        def world(s):
            z=float(s['zoom'])
            return (float(s['cameraX'])+(x-720)/(base*z), float(s['cameraY'])+(y-450)/(base*z))
        for step in (-5, 12):
            self.zoom(page, step)
            before = world(self.scene(page))
            page.mouse.move(x, y); page.mouse.wheel(0, -120); page.wait_for_timeout(70)
            for a,b in zip(before, world(self.scene(page))): self.assertAlmostEqual(a,b,delta=.15)

    def test_pause_dialog_and_visibility_stop_simulation(self):
        page = self.load('en')
        patch = page.locator('.swarm-patch').nth(15)
        first = patch.get_attribute('transform')
        page.wait_for_timeout(100)
        self.assertEqual(first, patch.get_attribute('transform'))
        page.locator('#pause-button').click(); page.wait_for_timeout(140)
        self.assertNotEqual(first, patch.get_attribute('transform'))
        page.locator('#help-button').click(); page.wait_for_timeout(50)
        first = patch.get_attribute('transform'); page.wait_for_timeout(100)
        self.assertEqual(first, patch.get_attribute('transform'))
        page.keyboard.press('Escape')
        page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
        first = patch.get_attribute('transform'); page.wait_for_timeout(150)
        self.assertEqual(first, patch.get_attribute('transform'))
        page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(150)
        self.assertNotEqual(first, patch.get_attribute('transform'))

    def test_native_button_space_single_toggle_and_dialog_keys(self):
        page = self.load('en')
        page.locator('#pause-button').focus(); page.keyboard.press('Space')
        self.assertEqual(self.scene(page)['motion'], 'playing')
        page.locator('#help-button').click()
        before = self.scene(page)['zoom']
        page.keyboard.press('f'); page.keyboard.press('+')
        self.assertEqual(self.scene(page)['zoom'], before)
        self.assertNotEqual(self.scene(page)['mode'], 'follow')

    def test_double_click_and_keyboard_reset(self):
        page = self.load('en')
        page.mouse.dblclick(1300, 230)
        self.assertGreaterEqual(float(self.scene(page)['zoom']), 2.5)
        page.keyboard.press('Home')
        s=self.scene(page)
        self.assertEqual(s['mode'], 'overview')
        self.assertEqual(float(s['zoom']), 1)
        self.assertEqual(float(s['cameraX']), 800)
        self.assertEqual(float(s['cameraY']), 500)

    def test_touch_cancel_releases_capture(self):
        page = self.load('en', (390,844), touch=True)
        cdp = page.context.new_cdp_session(page)
        for kind, points in [('touchStart',[{'x':160,'y':530,'id':1}]), ('touchMove',[{'x':220,'y':540,'id':1}]), ('touchCancel',[])]:
            cdp.send('Input.dispatchTouchEvent', {'type':kind, 'touchPoints':points})
        self.assertNotIn('dragging', page.locator('#scene').get_attribute('class') or '')
        self.assertLess(float(self.scene(page)['cameraX']), 1020)


if __name__ == '__main__':
    unittest.main(argv=[__file__, *harness.REMAINING], verbosity=2)
