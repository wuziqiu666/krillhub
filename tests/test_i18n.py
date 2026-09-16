"""Dependency-free checks for pre-rendered languages and search metadata.

python3 -m unittest discover -s tests -p 'test_i18n.py' -v
"""
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
ORIGIN = json.loads((ROOT / 'locales/site.json').read_text())['origin']
PAGES = [('en', '', 'en'), ('zh', 'zh/', 'zh-Hans')]


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def find(self, tag, **attrs):
        return [a for t, a in self.elements if t == tag and all(a.get(k) == v for k, v in attrs.items())]


class LanguageContractTests(unittest.TestCase):
    def setUp(self):
        self.pages = {code: (PUBLIC / path / 'index.html').read_text(encoding='utf-8') for code, path, _ in PAGES}
        self.docs = {code: Document(text) for code, text in self.pages.items()}

    def test_generated_files_are_current(self):
        spec = importlib.util.spec_from_file_location('render_locales', ROOT / 'scripts/render_locales.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = module.outputs()
        self.assertEqual(expected, module.outputs(), 'Rendering must be deterministic')
        for path, content in expected.items():
            self.assertEqual(path.read_text(encoding='utf-8'), content, str(path))

    def test_static_language_and_self_canonical(self):
        for code, path, lang in PAGES:
            with self.subTest(code=code):
                doc = self.docs[code]
                self.assertEqual(doc.find('html')[0]['lang'], lang)
                self.assertEqual(doc.find('link', rel='canonical'), [{'rel': 'canonical', 'href': ORIGIN + '/' + path}])
                self.assertNotIn('{{', self.pages[code])
                self.assertNotIn('}}', self.pages[code])

    def test_alternates_are_complete_and_reciprocal(self):
        expected = {'en': ORIGIN + '/', 'zh-Hans': ORIGIN + '/zh/', 'x-default': ORIGIN + '/'}
        for doc in self.docs.values():
            links = doc.find('link', rel='alternate')
            self.assertEqual(len(links), 3)
            self.assertEqual({a['hreflang']: a['href'] for a in links}, expected)

    def test_localized_titles_descriptions_and_open_graph(self):
        for code, path, _ in PAGES:
            doc = self.docs[code]
            description = doc.find('meta', name='description')[0]['content']
            self.assertIn('krill' if code == 'en' else '磷虾', description)
            self.assertEqual(doc.find('meta', property='og:description')[0]['content'], description)
            self.assertEqual(doc.find('meta', property='og:url')[0]['content'], ORIGIN + '/' + path)
            self.assertNotIn('noindex', doc.find('meta', name='robots')[0]['content'])
        self.assertIn('<title>Krillhub — Interactive Krill Migration</title>', self.pages['en'])
        self.assertIn('<title>Krillhub · 微光洄游</title>', self.pages['zh'])

    def test_native_language_links_and_shared_assets_resolve(self):
        expected = {'en': ORIGIN + '/', 'zh-Hans': ORIGIN + '/zh/'}
        for code, path, lang in PAGES:
            doc = self.docs[code]
            base = ORIGIN + '/' + path
            links = [a for a in doc.find('a') if 'hreflang' in a]
            self.assertEqual(len(links), 2)
            self.assertEqual({a['hreflang']: urljoin(base, a['href']) for a in links}, expected)
            self.assertEqual([a['hreflang'] for a in links if a.get('aria-current') == 'page'], [lang])
            for tag, key in [('script', 'src'), ('link', 'href')]:
                for item in doc.find(tag):
                    if tag == 'link' and item.get('rel') != 'stylesheet':
                        continue
                    url = urlsplit(urljoin(base, item[key]))
                    self.assertEqual(url.netloc, urlsplit(ORIGIN).netloc)
                    self.assertTrue((PUBLIC / url.path.lstrip('/')).is_file(), url.path)

    def test_english_is_not_a_chinese_shell(self):
        # The native Chinese-language switch is intentionally named in Chinese.
        without_switch = re.sub(r'<nav class="language-switch".*?</nav>', '', self.pages['en'], flags=re.S)
        self.assertIsNone(re.search('[\u4e00-\u9fff]', without_switch))
        self.assertIn('Small lives.', self.pages['en'])
        self.assertIn('微小生命。', self.pages['zh'])
        self.assertIsNone(re.search('[\u4e00-\u9fff]', (PUBLIC / 'app.js').read_text()))

    def test_scene_art_is_shared_unchanged(self):
        defs = lambda text: re.search(r'<defs>(.*?)</defs>', text, re.S)[1]
        self.assertEqual(defs(self.pages['en']), defs(self.pages['zh']))
        self.assertEqual(defs(self.pages['en']), defs((ROOT / 'templates/index.html').read_text()))
        for text in self.pages.values():
            self.assertNotIn('<canvas', text)
            self.assertNotIn('<iframe', text)

    def test_runtime_messages_and_accessibility_are_localized(self):
        for code, _, _ in PAGES:
            catalog = json.loads((ROOT / f'locales/{code}.json').read_text())
            ocean = self.docs[code].find('main', id='ocean')[0]
            self.assertEqual({key.removeprefix('data-i18n-'): value for key, value in ocean.items() if key.startswith('data-i18n-')}, catalog['messages'])
            self.assertEqual(self.docs[code].find('button', id='help-button')[0]['aria-label'], catalog['text']['about'])
            self.assertTrue(self.docs[code].find('noscript'))
            for script in self.docs[code].find('script'):
                self.assertIn('src', script, 'Do not add executable inline scripts')
        app = (PUBLIC / 'app.js').read_text()
        for forbidden in ('navigator.language', 'localStorage.', 'document.cookie', 'fetch('):
            self.assertNotIn(forbidden, app)

    def test_sitemap_robots_and_not_found(self):
        tree = ET.fromstring((PUBLIC / 'sitemap.xml').read_text())
        locations = [n.text for n in tree.findall('{*}url/{*}loc')]
        self.assertEqual(locations, [ORIGIN + '/', ORIGIN + '/zh/'])
        robots = (PUBLIC / 'robots.txt').read_text()
        self.assertIn('Allow: /', robots)
        self.assertIn(f'Sitemap: {ORIGIN}/sitemap.xml', robots)
        error = Document((PUBLIC / '404.html').read_text())
        self.assertEqual(error.find('html')[0]['lang'], 'en')
        self.assertIn('noindex', error.find('meta', name='robots')[0]['content'])
        self.assertEqual({a['href'] for a in error.find('a')}, {'/', '/zh/'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
