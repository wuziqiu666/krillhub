# Krillhub · 微光洄游

**Small lives. Endless tides.**

为 `krillhub.com` 制作的交互式磷虾群动态插画。纯 HTML、CSS、原生 JavaScript 和 SVG，无框架、无构建步骤、无运行时第三方依赖；没有 Canvas、WebGL、3D 模型、远程字体、分析脚本或 API 请求。许可证沿用仓库原有 `LICENSE`。

## 从虾群到个体

支持 **20%–2,400%** 缩放。远景是密集的微点和短线，中景显现简化轮廓，近景渐变为原有精细 SVG 磷虾。桌面配置有 **21,600 个逻辑个体**，窄屏配置有 **9,600 个**；这是程序化世界的视觉配置，不是当前可见数、实测密度或生态模拟。

每个微点保留身份和位置，点击可聚焦并跟随。远景用合并 SVG 路径，近景实例有上限，超出预算的个体继续保留简化轮廓，不会凭空消失。视差、群落漂移和少量形变均作用于平面图形。

英文首页：`/`；简体中文：`/zh/`。两页均为完整静态 HTML，右上角可直接切换，不进行语言猜测或自动跳转。包含独立标题、描述、canonical、hreflang、站点地图和 robots.txt。详见 [多语言维护](docs/multilingual.md) 和 [虾群 LOD 实现与验证](docs/swarm-lod.md)。

## 操作

| 功能 | 操作 |
| --- | --- |
| 平移 | 鼠标 / 单指拖动；方向键，Shift 加快 |
| 缩放 | 滚轮 / 双指捏合；`+` / `-`；底部 ± 按钮 |
| 聚焦跟随 | 点击微点、轮廓或磷虾；聚焦按钮；`F` |
| 局部近观 | 双击画面 |
| 返回全景 / 取消跟随 | `0` 或 `Home` / `Esc` |
| 暂停 / 播放 | 播放按钮；`Space` |
| 速度 / 沉浸模式 | 0.5×、1×、2×；`I` 切换沉浸 |

尊重 `prefers-reduced-motion`：默认暂停，用户仍可手动播放。页面隐藏或说明对话框打开时停止推进动画。按钮焦点上的空格保留原生行为。浏览器支持时提供全屏。

## 本地预览

```sh
python3 -m http.server 8080 --directory public
# 打开 http://localhost:8080
```

也可直接打开 `public/index.html`。普通静态服务器不会自动应用 Cloudflare `_headers`。

## Cloudflare 部署

只发布 `public/`，不要发布仓库根目录。

**Workers Git 集成**：构建命令留空，根目录为仓库根目录，生产分支 `main`，Deploy command 保持：

```sh
npx wrangler@4 deploy --config wrangler.workers.jsonc
```

本地 Workers 预览：

```sh
npx wrangler@4 dev --config wrangler.workers.jsonc
```

**Pages Git 集成**：Framework preset 为 `None`，Build command 为 `exit 0`，Build output directory 为 `public`，生产分支 `main`。也可在登录 Wrangler 后上传：

```sh
npx wrangler@4 pages deploy public --project-name krillhub
```

配置中没有账号 ID、Token 或域名路由。提交代码不代表 Cloudflare 部署成功、域名已绑定或 Google 已收录。部署后需要单独验证页面、响应头、404 状态码与实际手机手势；Google Search Console 由站点所有者验证和提交站点地图。

官方参考：[Pages 静态 HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)、[Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)。

## 修改与测试

`templates/index.html` 是共享页面模板，`locales/*.json` 是翻译来源。修改后重新生成并提交 `public/` 的结果；部署端不需要 Python。

```sh
python3 scripts/render_locales.py
python3 scripts/render_locales.py --check
node --check public/swarm.js
node --check public/app.js
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 可选开发依赖，不参与部署
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/smoke.py
```

`tests/smoke.py` 包含 LOD、交互和语言回归；`tests/i18n_browser.py` 可单独验证语言行为。受限环境可加 `--in-memory`，但该模式不验证真实 HTTP、CSP 或 URL 跳转。`CHROMIUM_EXECUTABLE` 可指定已有 Chromium。

2026-09-16 本轮分组验证：**9 项静态检查 + 12 项 LOD/交互 + 6 项语言浏览器测试通过**；3 项实际导航测试跳过。生成文件检查和两个 JS 语法检查通过。浏览器验证使用 Chromium 内存注入；未完成 Cloudflare 线上、Safari、Firefox 或真实手机验收。详情见 LOD 文档。

`public/swarm.js` 管理群落、固定个体身份、合并路径、视口裁剪和近景实例池；`public/app.js` 管理摄像机、手势和播放。SVG 图元仍在共享模板中；安全响应头仍在 `public/_headers`。加入第三方服务前需要同步评估 CSP，不应直接关闭安全策略。
