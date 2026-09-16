"""Dependency-free favicon and WebSite checks for checked-in static HTML.

python3 -m unittest discover -s tests -p 'test_search_metadata.py' -v
"""
import copy
import importlib.util
import json
from pathlib import Path
import re
import struct
import unittest
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
import zlib

from test_i18n import Document

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
CONFIG = json.loads((ROOT / 'locales/site.json').read_text(encoding='utf-8'))
ORIGIN = CONFIG['origin'].rstrip('/')
JSON_LD = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)


class SearchMetadataTests(unittest.TestCase):
    def pages(self):
        for language in CONFIG['languages']:
            path = PUBLIC / language['path'] / 'index.html'
            text = path.read_text(encoding='utf-8')
            yield path, text, Document(text)

    def test_one_static_website_node_with_shared_site_identity(self):
        for path, text, doc in self.pages():
            with self.subTest(path=path):
                scripts = doc.find('script', type='application/ld+json')
                self.assertEqual(scripts, [{'type': 'application/ld+json'}])
                blocks = JSON_LD.findall(text.split('</head>', 1)[0])
                self.assertEqual(len(blocks), 1)
                self.assertNotIn('&quot;', blocks[0])
                data = json.loads(blocks[0])
                self.assertEqual(data, {
                    '@context': 'https://schema.org', '@type': 'WebSite',
                    'name': 'Krillhub', 'url': ORIGIN + '/',
                })
                self.assertEqual(data['name'], doc.find('meta', property='og:site_name')[0]['content'])

    def test_website_url_tracks_site_configuration_not_locale(self):
        spec = importlib.util.spec_from_file_location('search_renderer', ROOT / 'scripts/render_locales.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        original_load = renderer.load_json
        config = copy.deepcopy(CONFIG)
        config['origin'] = 'https://metadata.example'

        def load(path):
            return config if path == ROOT / 'locales/site.json' else original_load(path)

        with patch.object(renderer, 'load_json', side_effect=load):
            rendered = renderer.outputs()
        for path, text in rendered.items():
            if path.suffix == '.html':
                self.assertEqual(json.loads(JSON_LD.search(text)[1])['url'], config['origin'] + '/')
                self.assertNotIn(ORIGIN, text)

    def test_favicon_resolves_to_same_file_over_https_and_file_preview(self):
        for path, _, doc in self.pages():
            with self.subTest(path=path):
                icons = doc.find('link', rel='icon')
                self.assertEqual(len(icons), 1)
                icon = icons[0]
                self.assertEqual(icon['type'], 'image/png')
                self.assertEqual(icon['sizes'], '96x96')
                page_url = ORIGIN + '/' + path.parent.relative_to(PUBLIC).as_posix().strip('.')
                page_url = page_url.rstrip('/') + '/'
                self.assertEqual(urljoin(page_url, icon['href']), ORIGIN + '/favicon.png')
                resolved = Path(urlsplit(urljoin(path.as_uri(), icon['href'])).path)
                self.assertEqual(resolved.resolve(), PUBLIC / 'favicon.png')
                self.assertTrue(resolved.is_file())

    def test_png_dimensions_checksums_and_pixel_stream(self):
        data = (PUBLIC / 'favicon.png').read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        offset, compressed, chunks = 8, bytearray(), []
        while offset < len(data):
            length = struct.unpack('>I', data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + length]
            crc = struct.unpack('>I', data[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(len(payload), length)
            self.assertEqual(zlib.crc32(kind + payload) & 0xffffffff, crc)
            chunks.append(kind)
            if kind == b'IHDR':
                self.assertEqual(struct.unpack('>IIBBBBB', payload), (96, 96, 8, 6, 0, 0, 0))
            elif kind == b'IDAT':
                compressed.extend(payload)
            offset += length + 12
        self.assertEqual(offset, len(data))
        self.assertEqual(chunks[0], b'IHDR')
        self.assertEqual(chunks[-1], b'IEND')
        pixels = zlib.decompress(compressed)
        self.assertEqual(len(pixels), 96 * (1 + 96 * 4))
        self.assertTrue(all(pixels[row * 385] in range(5) for row in range(96)))
        svg = ET.fromstring((PUBLIC / 'favicon.svg').read_text(encoding='utf-8'))
        self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertEqual(svg.attrib['viewBox'], '0 0 64 64')

    def test_json_ld_does_not_require_executable_inline_scripts_or_weaker_csp(self):
        for _, _, doc in self.pages():
            executable = []
            for script in doc.find('script'):
                if script.get('type') == 'application/ld+json':
                    self.assertNotIn('src', script)
                else:
                    self.assertIn('src', script)
                    self.assertIn('defer', script)
                    executable.append(Path(script['src']).name)
            self.assertEqual(executable, ['swarm.js', 'app.js'])
        headers = (PUBLIC / '_headers').read_text(encoding='utf-8')
        self.assertIn("script-src 'self';", headers)
        self.assertNotIn("'unsafe-inline'", headers)
        self.assertNotIn("'unsafe-eval'", headers)

    def test_home_page_and_favicon_are_not_blocked_in_robots(self):
        robots = RobotFileParser()
        robots.parse((PUBLIC / 'robots.txt').read_text(encoding='utf-8').splitlines())
        self.assertTrue(robots.can_fetch('Googlebot', ORIGIN + '/'))
        self.assertTrue(robots.can_fetch('Googlebot-Image', ORIGIN + '/favicon.png'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
