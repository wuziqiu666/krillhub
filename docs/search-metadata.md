# Favicon and site name

## Implementation

`public/favicon.png` is the crawlable 96×96 RGBA favicon. Its artwork is extracted from the original embedded icon; `public/favicon.svg` preserves that vector source. Both language pages resolve their favicon link to the same `/favicon.png`. Relative asset paths also preserve direct `file://` previews. The PNG is committed, so deployment needs no image tooling.

`templates/index.html` references the PNG. `scripts/render_locales.py` emits one static `application/ld+json` data block in each language page's head:

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Krillhub",
  "url": "https://krillhub.com/"
}
```

The URL comes from `locales/site.json`, not the current language path. English `/` and Chinese `/zh/` describe the same website. Their separate self-canonical URLs and reciprocal `hreflang` links remain unchanged. There is no invented search endpoint, SearchAction, alternate brand name, or organization metadata.

JSON is serialized as script data, with HTML-sensitive characters escaped as Unicode sequences. It is not an executable inline script. Existing executable scripts remain external; `public/_headers` and its restrictive CSP are unchanged.

## Maintenance

After changing the template, locale text, or origin:

```sh
python3 scripts/render_locales.py
python3 scripts/render_locales.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

After deliberately changing the SVG artwork, regenerate the PNG with the optional development tool CairoSVG (not a deployment dependency):

```sh
python3 -m pip install cairosvg
python3 -m cairosvg public/favicon.svg --output-width 96 --output-height 96 -o public/favicon.png
```

Keep `/favicon.png` stable rather than adding a content hash or changing the URL frequently. Commit the source SVG, PNG, and any regenerated HTML together.

## Deployment and search verification

A Git commit is not proof of a successful Cloudflare deployment or Google indexing. After deployment, confirm that `/` and `/zh/` contain the JSON-LD in the original HTML and that `/favicon.png` returns HTTP 200 with an image/png content type, rather than an HTML fallback. Keep the homepage and favicon crawlable.

Use Schema Markup Validator for site-name markup and Search Console URL Inspection for the live homepage. Google's Rich Results Test does not support site names; absence of a rich-result item there is not a failure of this WebSite declaration. Google chooses the displayed site name and favicon, and their appearance is not guaranteed or immediate.

Official references: [Google favicon guidance](https://developers.google.com/search/docs/appearance/favicon-in-search), [Google site-name guidance](https://developers.google.com/search/docs/appearance/site-names).
