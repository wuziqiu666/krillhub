#!/usr/bin/env python3
"""Render checked-in language pages using only Python's standard library.

Run after editing templates/index.html or locales/*.json. Deployment serves
public/ directly and does NOT require Python, this script, or a build step.
Use --check in review/CI to reject missing translations and stale output.
"""
from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'\{\{([a-z_]+)\}\}')
PARAM = re.compile(r'\{(\w+)\}')


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def outputs() -> dict[Path, str]:
    config = load_json(ROOT / 'locales/site.json')
    origin = config['origin'].rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('origin must be an HTTPS origin without a path, query, or fragment')
    languages = config['languages']
    ids = [item['id'] for item in languages]
    paths = [item['path'] for item in languages]
    if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
        raise ValueError('Duplicate language IDs or paths')
    default = next(item for item in languages if item['id'] == config['default'])
    if default['path'] != '':
        raise ValueError('The default language must own the root URL')
    catalogs = {}
    for item in languages:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', item['id']):
            raise ValueError('Invalid catalogue ID')
        if not re.fullmatch(r'(?:[a-z0-9-]+/)*', item['path']):
            raise ValueError('Language paths must be relative directory paths with trailing slashes')
        if not re.fullmatch(r'[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*', item['lang']):
            raise ValueError('Invalid HTML language tag')
        catalogs[item['id']] = load_json(ROOT / f"locales/{item['id']}.json")
    reference = catalogs[default['id']]
    for code, catalog in catalogs.items():
        for section in ('text', 'messages'):
            if set(catalog[section]) != set(reference[section]):
                raise ValueError(f'{code}: translation keys differ in {section}')
            for key, value in catalog[section].items():
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f'{code}: empty or invalid translation: {key}')
                if PARAM.findall(value) != PARAM.findall(reference[section][key]):
                    # Use sets: translations may legitimately reorder parameters.
                    if set(PARAM.findall(value)) != set(PARAM.findall(reference[section][key])):
                        raise ValueError(f'{code}: placeholder mismatch: {key}')
    template = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
    generated = {}
    for current in languages:
        catalog = catalogs[current['id']]
        canonical = origin + '/' + current['path']
        metadata = [
            '  <meta name="robots" content="index, follow">',
            f'  <link rel="canonical" href="{escape(canonical)}">',
        ]
        for other in languages:
            metadata.append(f'  <link rel="alternate" hreflang="{escape(other["lang"])}" href="{escape(origin + "/" + other["path"])}">')
        metadata.extend([
            f'  <link rel="alternate" hreflang="x-default" href="{escape(origin + "/" + default["path"])}">',
            '  <meta property="og:type" content="website">',
            '  <meta property="og:site_name" content="Krillhub">',
            f'  <meta property="og:title" content="{escape(catalog["text"]["page_title"])}">',
            f'  <meta property="og:description" content="{escape(catalog["text"]["description"])}">',
            f'  <meta property="og:url" content="{escape(canonical)}">',
            f'  <meta property="og:locale" content="{escape(current["og_locale"])}">',
        ])
        for other in languages:
            if other['id'] != current['id']:
                metadata.append(f'  <meta property="og:locale:alternate" content="{escape(other["og_locale"])}">')
        nav = [f'        <nav class="language-switch" aria-label="{escape(catalog["text"]["language_label"])}">']
        for other in languages:
            relative = posixpath.relpath(other['path'] or '.', current['path'] or '.') + '/'
            selected = ' aria-current="page"' if other['id'] == current['id'] else ''
            nav.append(f'          <a href="{escape(relative)}" lang="{escape(other["lang"])}" hreflang="{escape(other["lang"])}" title="{escape(other["name"])}" aria-label="{escape(other["name"])}"{selected}>{escape(other["label"])}</a>')
        nav.append('        </nav>')
        messages = []
        for key, value in catalog['messages'].items():
            if not re.fullmatch(r'[a-z]+(?:-[a-z]+)*', key):
                raise ValueError('Invalid message attribute name')
            messages.append(f'    data-i18n-{key}="{escape(value)}"')
        assets = '../' * current['path'].count('/') or './'
        values = {**catalog['text'], 'lang': current['lang'], 'assets': assets}
        raw = {'metadata': '\n'.join(metadata), 'language_nav': '\n'.join(nav), 'messages': '\n'.join(messages)}

        def substitute(match: re.Match) -> str:
            key = match[1]
            if key in raw:
                return raw[key]
            if key not in values:
                raise ValueError(f'{current["id"]}: missing template value: {key}')
            return escape(values[key])

        rendered = TOKEN.sub(substitute, template)
        if '{{' in rendered or '}}' in rendered:
            raise ValueError('Unexpanded template token')
        generated[ROOT / 'public' / current['path'] / 'index.html'] = rendered
    urls = '\n'.join(f'  <url><loc>{xml_escape(origin + "/" + item["path"])}</loc></url>' for item in languages)
    generated[ROOT / 'public/sitemap.xml'] = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '\n</urlset>\n'
    generated[ROOT / 'public/robots.txt'] = f'User-agent: *\nAllow: /\n\nSitemap: {origin}/sitemap.xml\n'
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate without writing; exit nonzero for stale output')
    args = parser.parse_args()
    generated = outputs()  # Validate every language before changing any file.
    stale = []
    for path, content in generated.items():
        if path.is_file() and path.read_text(encoding='utf-8') == content:
            continue
        if args.check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8', newline='\n')
            print('Rendered', path.relative_to(ROOT))
    if stale:
        parser.exit(1, 'Stale generated files; run python3 scripts/render_locales.py:\n' + '\n'.join(stale) + '\n')
    print('Language pages and search metadata are up to date.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
