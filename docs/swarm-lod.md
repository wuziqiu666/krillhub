# Dense swarm / semantic zoom

## Visual contract

The scene remains an illustration, not a density estimate, migration model or measured ocean location. Bright specks are an artistic rendering choice, not a claim that every krill glows like a lamp. The population below describes the finite procedural world, not the number currently on screen.

- English remains `/`; Simplified Chinese remains `/zh/`. Both are generated static HTML.
- Camera range: **0.2–24× (20%–2,400%)**. Reset returns to the existing overview composition.
- The same logical animal becomes a short stroke, a silhouette and then the detailed SVG. Clicking a batched mark selects an existing animal, not a newly spawned replacement.
- Pan, wheel/pinch anchor, focus/follow, pause, speed, immersive mode, keyboard and reduced-motion behaviour remain available.

## Representation

`public/swarm.js` owns a seeded world with three flat parallax layers. At initial viewport widths above 650 CSS pixels it creates 36 patches × 600 animals = **21,600 logical animals**. At widths up to 650 pixels it creates 30 × 320 = **9,600**. This profile is selected once; resizing or rotating does not reseed the world.

Patches are elliptical concentrations with curved interiors, variable extents, overlapping ribbons and gaps. Each has its own drift speed and slow heading change. This is patch-level procedural motion, not an all-pairs flocking simulation; individual full-detail art has a small breathing deformation. At the finite world's boundary a patch fades before wrapping. A selected animal wrapping clears follow mode instead of sweeping the camera across the world.

The logical world is deliberately separate from SVG node allocation. Coordinates, size band and identity are stable for the life of a page. Geometry uses the same local origin and heading in all representations; camera transformations do not resample particles.

## Screen-space LOD

Thresholds use projected full-art length, including antennae, in **CSS pixels**, not the global zoom percentage or physical millimetres. Depth, viewport size and the animal's size band all affect the transition.

| Projected length | Representation |
| --- | --- |
| Below 7 px | Batched short strokes / specks |
| 7–16 px | Smoothstep crossfade from strokes to silhouettes |
| 16–32 px | Silhouettes |
| 32–64 px | Smoothstep crossfade into detailed SVG when allocated |
| Above 64 px | Detailed SVG when allocated; otherwise a silhouette |

There are three size bands per patch. Each band has two combined paths, one for strokes and one for silhouettes: **216 coarse paths on desktop or 180 on compact layouts** before viewport culling. The simple silhouette used in a promoted instance is exactly the geometry used in its former batch.

Ordinary detail allocation enters at 28 px and is retained down to 22 px; both boundaries are below the detail crossfade, avoiding an abrupt art swap. A selected animal has priority even before it reaches the detail threshold. Its proxy still respects stroke/silhouette weights while the camera moves toward it.

The small SWARM / SHAPES / DETAIL label is only a scale hint. It uses hysteresis and does not imply that every layer switches simultaneously. All strings are localized, including the help text and range.

## Budget and continuity

The near-instance pool is capped at **224 desktop / 96 compact**. This is a cap on allocated individual SVG groups, not a promise of a particular frame rate. Each instance reuses the existing `#krill-art`; far animals do not each have a DOM node. A pooled group is reused after release.

Priority is selected animal, retained eligible instances, then new eligible instances. Offscreen patches are hidden. Candidates are screened against a padded viewport so an animal is usually already represented before it enters the visible edge. Animals that cannot obtain a near slot **remain in the batch** as silhouettes. Lower-detail fallback sacrifices detail, not population.

On promotion, the animal is excluded from both batch paths and represented by its individual proxy/art pair. On demotion it returns to the same paths with its original identity and coordinates. This prevents double-drawing and avoids losing density at the budget ceiling. Membership changes rebuild only affected paths; ordinary drift transforms the patches rather than rebuilding thousands of path strings each frame.

Repeated rendering with an unchanged camera, selection and simulation time is skipped. Unchanged layer transforms are not rewritten. Simulation and all animated art share the existing animation clock: pause, reduced-motion startup, hidden-document handling and the modal dialog apply to the entire scene. The animation scheduler does not create a second loop when follow mode clears during an update.

## Files and maintenance

- `public/swarm.js`: seeded patches, batched geometry, LOD weights, viewport culling, picking, detail pool.
- `public/app.js`: camera, input, animation clock and localized UI; no per-particle SVG loop.
- `templates/index.html`, `locales/en.json`, `locales/zh.json`: shared markup, scale hints, explanation and translations.
- `public/index.html`, `public/zh/index.html`: checked-in generated pages. Run `python3 scripts/render_locales.py` after editing source files.
- `tests/smoke.py`: LOD/interaction checks plus inherited language tests; `tests/i18n_browser.py` also runs independently.

The deployment command and security headers are unchanged. `swarm.js` is a same-origin deferred script placed before `app.js`; there are no CDN, package, WebGL, Canvas, Worker-entrypoint or runtime API dependencies.

Browser API references: [SVG use](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/use) and [requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame).

## Validation — 2026-09-16

The source and generated files passed `node --check` for both scripts, `render_locales.py --check` and **9 static tests**. Browser tests were run in separate groups in local Chromium: **12 LOD/interaction tests + 6 language tests passed**. Three real-navigation language tests were explicitly skipped.

LOD coverage includes logical population conservation across repeated zooms, bounded instance counts, budget exhaustion without lost silhouettes, smooth monotonic crossfade weights, selecting an existing batched speck, following its ID into detail, camera anchoring, culling, both zoom limits, pause/modal/visibility handling, touch cancellation, native button Space behaviour and mobile rotation without reseeding. Language coverage includes English/Chinese controls, focus, playback, fullscreen failure messages and layouts at 320×568, 390×844, 768×1024, 844×390 and 1440×900.

The browser loaded the exact HTML/CSS/JS through DOM injection (`--in-memory`). Direct local HTTP navigation returned `ERR_BLOCKED_BY_ADMINISTRATOR` in this environment. Therefore these results do **not** validate actual HTTP asset loading, Cloudflare CSP/routing, native language-link navigation, Google indexing, Safari/Firefox, real touch hardware, battery use or long-running device performance. No fixed FPS claim is made. Deployment and device acceptance remain separate steps.
