# Krillhub 多语言与搜索收录

## 本次更新

本更新基于仓库 `wuziqiu666/krillhub` 的提交 `1d5db147d3564dba25e58f81d53a0c811e27a72d`。提供可应用的 Git 补丁和更新文件；不表示已经提交 GitHub、部署 Cloudflare 或提交 Google Search Console。仓库原有 README、LICENSE、部署配置和 CSP 保持不变。

| 页面 | 地址 | HTML 语言 |
| --- | --- | --- |
| 默认英文 | `https://krillhub.com/` | `en` |
| 简体中文 | `https://krillhub.com/zh/` | `zh-Hans` |

右上角的 `EN / 中文` 是普通网页链接，可通过键盘访问。语言由 URL 决定，不按 IP、浏览器语言或存储偏好自动跳转，也不设置语言 Cookie。切换语言会打开另一页面，动画与视角从初始状态开始。

两个版本都包含完整静态 HTML：标题、介绍、SVG 说明、控件、提示、无障碍标签、帮助弹窗及无脚本提示均已本地化。播放、暂停、速度、聚焦跟随、沉浸模式及全屏失败消息也使用当前页面的语言。SVG 图元与动画、平移、缩放和跟随算法共用；未引入框架或在线翻译服务。

英文首页不再先输出中文、等待 JavaScript 翻译。JavaScript 仍是播放动画和操作海洋场景的必要条件。404 页以英文为主，并提供中文说明和两个语言的首页链接。

## 应用更新

请在仓库根目录操作，先提交或妥善保存其他修改。下载 `krillhub-i18n.patch` 到仓库根目录后：

```sh
git apply --check krillhub-i18n.patch
# 只有上一步成功时，才执行：
git apply krillhub-i18n.patch
git diff --stat
git diff
```

若检查失败，不要强制覆盖；先对照当前分支和补丁基线解决冲突。更新文件 ZIP 是上述补丁的另一种交付形式，只包含变更/新增文件，不是完整仓库。使用其中一种方式即可，不要重复应用。解压覆盖也应先检查并保存现有修改。

审阅后，按常规 Git 流程提交变更并推送。不要把下载的补丁本身、临时截图或 Python `__pycache__` 一并加入版本控制。

## 维护方式

```text
locales/site.json             # 正式域名、默认语言和语言列表
locales/en.json               # 英文静态文案及动态消息
locales/zh.json               # 中文静态文案及动态消息
templates/index.html         # 共用 HTML 和 SVG 模板
scripts/render_locales.py    # 可选的静态生成/校验工具
public/index.html           # 已生成的英文页面
public/zh/index.html        # 已生成的中文页面
public/app.js               # 共用动画与交互
public/style.css            # 共用样式及语言切换控件
public/sitemap.xml         # 两个正式页面的站点地图
public/robots.txt          # 爬虫与站点地图声明
```

修改文案或共用页面时，编辑 `locales/*.json` 或 `templates/index.html`，再使用 Python 3.10+（仅标准库）：

```sh
python3 scripts/render_locales.py
python3 scripts/render_locales.py --check
```

生成器检查翻译键、占位符、语言路径、正式域名和未替换模板字段。将源文件与生成结果一起提交。不要只修改 `public/index.html` 或 `public/zh/index.html`，下次生成会覆盖手工修改。

增加其他语言时，复制一份完整词典，翻译全部 `text` 与 `messages` 字段，在 `locales/site.json` 添加语言、路径、显示名称和 Open Graph locale，然后重新生成。生成器会相应更新导航、页面 alternate 标签与站点地图；测试当前显式覆盖中英文，增加语言时也需扩展测试覆盖。若删除语言，需要另行删除旧的生成目录，生成器不会自动删除文件。

`locales/site.json` 的正式 origin 当前为 `https://krillhub.com`。改用其他正式域名时，修改此处并重新生成。预览域名不是本配置中的 canonical；上线前应确认正式域名确实能够访问。

## Cloudflare 部署

部署直接使用已生成的 `public/`，不需要在 Cloudflare 安装 Python、执行生成器或增加前端构建步骤。

Workers Deploy command 保持：

```sh
npx wrangler@4 deploy --config wrangler.workers.jsonc
```

原配置的 `assets.directory` 仍为 `./public`。文件夹索引由静态资源路由处理，不需要为 `/zh/` 新增 Worker JavaScript 后端。Pages 仍使用 `None` 框架、`exit 0` 构建命令和 `public` 输出目录。

部署后实际检查 `/`、`/zh/`、`/robots.txt`、`/sitemap.xml`，同时检查 `/zh` 的规范化跳转和不存在的路径返回 404；测试桌面和手机的语言链接、帮助弹窗、拖动及捏合操作。不要把测试服务器的行为等同于 Cloudflare 线上行为。

参考：[Workers HTML 路由](https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/)、[Pages 静态 HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)。

## Google 搜索

每个语言页面有自己的标题、description、canonical 和 Open Graph 元信息。英文 canonical 指向 `/`，中文指向 `/zh/`，并不是把中文版 canonical 指向英文。两页都声明相同且互相对应的 `hreflang="en"`、`hreflang="zh-Hans"`，`x-default` 指向英文首页。站点地图列出两个正式 URL，robots.txt 声明站点地图位置。

这里使用 HTML alternate 标签表达语言对应关系，没有再在 HTTP Link 响应头或 sitemap 中重复维护同一套 hreflang。

正式部署后，在 Google Search Console 验证 `krillhub.com` 的所有权，在站点地图报告中提交 `https://krillhub.com/sitemap.xml`，并用网址检查工具检查两个首页。应确保正式页面返回 200、没有 `noindex` 或外部访问限制。Search Console 验证记录、账号权限、DNS 设置及提交操作不包含在此代码更新中。

多语言页面、hreflang 和 sitemap 有助于提供可发现的语言版本，但不保证收录、排名、搜索结果展示语言或立即更新。Google 会根据可见内容等信号判断页面语言；不能只改 `html lang` 而保持中文内容不变。

参考：
- [Google：管理多语言网站](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites)
- [Google：本地化版本与 hreflang](https://developers.google.com/search/docs/specialty/international/localized-versions)
- [Google：构建和提交站点地图](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Google：请求重新抓取](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)

## 检查与测试记录

静态检查不需要额外 Python 包：

```sh
python3 scripts/render_locales.py --check
python3 -m unittest discover -s tests -p 'test_i18n.py' -v
node --check public/app.js
```

浏览器测试的 Playwright 仅为可选开发依赖：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install playwright
python -m playwright install chromium
python tests/i18n_browser.py
```

Windows 可使用 `.venv\Scripts\activate`。已有 Chromium 时，可通过 `CHROMIUM_EXECUTABLE` 环境变量指定可执行文件。

本次执行记录（2026-09-16）：9 项静态检查通过；浏览器使用 `--in-memory` 模式，6 项测试通过，3 项跳过。通过项覆盖两个语言的初始化与减少动态效果、播放/暂停/速度、聚焦/取消/复位、沉浸模式、说明弹窗、模拟全屏失败消息、拖动、滚轮缩放、键盘和模拟触屏捏合。响应式检查覆盖 320×568、390×844、768×1024、844×390、1440×900。

测试环境禁止浏览器访问本地 HTTP 页面，因此使用同一份 HTML/CSS/JS 的内存注入测试，而不是通过 HTTP 或 file 协议加载。跳过项为：关闭 JavaScript 的实际页面加载、无 JavaScript 的原生语言链接跳转、原生语言跳转与浏览器后退。静态源文件检查确认本地化文字已直接存在于 HTML，但这不等于上述浏览器测试已经完成。

未验证线上 Cloudflare 路由/响应头/CSP、实际搜索收录、Safari、Firefox 或真实手机兼容性。原有 `tests/smoke.py` 未在本轮重新执行。默认浏览器测试命令支持本地 HTTP 模式，需在允许导航的开发环境中补跑；这也不替代线上验收。
