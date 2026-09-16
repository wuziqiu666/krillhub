# krillhub · 微光洄游

**Small lives. Endless tides.**

为 `krillhub.com` 制作的磷虾迁徙动态插画：深蓝海水、珊瑚粉色虾群、柔和光束、漂浮微粒与远处冰影。用纯 HTML、CSS、原生 JavaScript 和 SVG 实现，无框架、无构建步骤、无运行时第三方依赖。

画面是一种艺术表达，不是物种行为、海域、水深或迁徙规律的科学模拟。2.5D 来自平面图层的位移、缩放、遮挡和速度差；没有 Canvas、WebGL、Three.js、透视投影或 3D 模型。

## 已实现

- 手绘 SVG 磷虾与复用图元，分层虾群、独立游动相位、循环迁徙轨迹与水下光影。
- 鼠标 / 单指拖动；滚轮 / 双指捏合缩放；以指针位置为缩放锚点；缩放范围 60%–400%。
- 点击磷虾聚焦并跟随；一键选取可见磷虾；双击局部近观；取消跟随和返回全景。
- 暂停 / 播放，0.5×、1×、2× 动画速度；沉浸模式；浏览器支持时提供全屏。
- 手机、平板和桌面布局；键盘操作、可见焦点、原生说明对话框。
- 尊重 `prefers-reduced-motion`：默认静止，用户仍可手动播放。页面隐藏或打开说明时停止推进动画。
- 无登录、分析脚本、远程字体或外部图片。页面脚本不发起 API 请求。

## 操作

| 操作 | 鼠标 / 触摸 | 键盘 |
| --- | --- | --- |
| 平移 | 拖动 / 单指拖动 | 方向键；Shift 加快 |
| 缩放 | 滚轮 / 双指捏合 / ± 按钮 | `+` / `-` |
| 聚焦跟随 | 点击磷虾 / 聚焦虾群按钮 | `F` |
| 局部近观 | 双击画面 | — |
| 返回全景 | 复位按钮 | `0` / `Home` |
| 取消跟随 | 跟随提示中的 × | `Esc` |
| 暂停 / 播放 | 左下角播放按钮 | `Space` |
| 沉浸 / 退出沉浸 | 右上角眼睛 / 退出沉浸按钮 | `I`；`Esc` 可退出 |

说明对话框打开时，快捷键不会干扰对话框操作；按钮获得焦点时，空格保留原生按钮行为。

## 目录

```text
public/
  index.html       # 页面结构、SVG 图元与场景图层
  style.css        # 视觉样式、响应式布局、减少动态效果设置
  app.js           # 动画、摄像机、鼠标/触摸/键盘交互
  404.html         # 静态 404 页面
  _headers         # Cloudflare 静态资源响应头与 CSP
wrangler.workers.jsonc
README.md
tests/smoke.py      # 可选的 Playwright 浏览器回归测试
LICENSE            # 保留仓库原有许可证
```

## 本地预览

直接用浏览器打开 `public/index.html`，或在仓库根目录启动任意静态 HTTP 服务，例如：

```sh
python3 -m http.server 8080 --directory public
# 浏览器打开 http://localhost:8080
```

无需 `npm install` 或前端构建。Python 仅用于这个可选的本地 HTTP 服务，并不是网站的运行时依赖。Cloudflare 专用的 `_headers` 不会被普通 Python HTTP 服务自动应用。

## Cloudflare Pages

连接此 GitHub 仓库，使用下面的配置：

| 配置 | 值 |
| --- | --- |
| Production branch | `main` |
| Framework preset | `None` |
| Root directory | 仓库根目录 |
| Build command | `exit 0` |
| Build output directory | `public` |

只发布 `public/`，不要把仓库根目录当作发布目录。也可以使用 Wrangler 直接上传：

```sh
npx wrangler@4 login
npx wrangler@4 pages deploy public --project-name krillhub
```

项目首次上传可能需要按提示创建或选择 Pages 项目。部署完成后再在该项目中配置自定义域名 `krillhub.com`。

官方说明：[Cloudflare Pages — Static HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)。

## Cloudflare Workers Static Assets

本项目不需要 Worker JavaScript 入口，只需要静态资源配置：

```sh
# 本地预览
npx wrangler@4 dev --config wrangler.workers.jsonc

# 登录后部署
npx wrangler@4 login
npx wrangler@4 deploy --config wrangler.workers.jsonc
```

配置中的 `assets.directory` 指向 `./public`。选择 Workers 的 Git 构建时，无需前端构建步骤，Deploy command 使用：

```sh
npx wrangler@4 deploy --config wrangler.workers.jsonc
```

文件特意命名为 `wrangler.workers.jsonc`，避免 Pages 将 Workers 配置当成默认的 Pages 配置读取。不要把 `pages_build_output_dir` 加进这份 Workers 配置。

官方说明：[Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)；[静态资源配置](https://developers.cloudflare.com/workers/static-assets/binding/)；[自定义 404](https://developers.cloudflare.com/workers/static-assets/routing/static-site-generation/)。

**仓库内仅准备代码和部署配置，不代表已经完成 Cloudflare 部署、Git 集成授权或 DNS / 域名绑定。** 配置没有写入账号 ID、API Token 或域名路由。

## 响应头

`public/_headers` 对静态资源设置 CSP、禁止 MIME 嗅探、不发送 Referer、禁用相机/麦克风/地理位置权限，并要求缓存重验证。HTML 不包含内联脚本、内联样式或事件处理器，JavaScript 和 CSS 从同源文件加载。全屏功能没有被权限策略禁用。

添加第三方脚本、远程图片、API 请求或分析服务前，需要同步评估并修改 CSP。不要通过直接关闭 CSP 来解决资源加载问题。Cloudflare 规则或额外注入脚本也应与 CSP 一起验证。

官方说明：[Workers 静态资源响应头](https://developers.cloudflare.com/workers/static-assets/headers/)。

## 测试

测试工具是可选的开发依赖，不参与站点部署。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install playwright
python -m playwright install chromium
python tests/smoke.py
```

Windows 可使用 `.venv\Scripts\activate` 激活虚拟环境。若已有 Chromium，可以通过 `CHROMIUM_EXECUTABLE` 指定可执行文件。

2026-09-16 本地 Chromium 回归结果：**18 项通过**。覆盖 SVG 初始化、静态文件契约、减少动态效果、暂停/播放、速度切换、拖动、滚轮锚点、缩放上下限、点击与按钮聚焦、跟随移动、双击、复位、键盘、原生按钮空格行为、沉浸模式、对话框暂停，以及双指缩放与触摸取消。布局覆盖 320×568、390×844、768×1024、844×390 和 1920×1080。

此次执行使用 `python tests/smoke.py --in-memory`：受测试容器浏览器导航限制，直接将同一份 HTML/CSS/JS 注入 Chromium 进行交互验证。**这不等于通过 HTTP/file 协议加载资产、Cloudflare 响应头或真实设备兼容性已经验证。** 未执行 Cloudflare 线上部署验收，也未在 Safari、Firefox 或真实手机上测试。后续部署后应复查网络面板、CSP、404 状态码与实际手机手势。

## 修改画面

`index.html` 的 `krill-art` 是磷虾的 SVG 图元；`app.js` 的 `schools` 定义图层数量、体型、分布与游速；`limits` 定义摄像机范围。桌面和手机采用不同的初始虾群数量，不会因窗口缩放反复重建场景。调整 `data-depth` 可改变平面视差，调整 CSS 变量可改变界面配色。

许可证沿用仓库现有 `LICENSE`。
