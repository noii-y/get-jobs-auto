# 登录中心扫码登录 · patchright spike 资料调研

> 调研日期：2026-10-19。调研范围：boss-agent-cli 设计、patchright 官方 API、四平台（Boss 直聘 / 前程无忧 51job / 智联招聘 / 猎聘）扫码登录与登录态判定。
> 本文只做资料调研与不登录观察，未做任何真实登录、未绕过任何风控。标注「需实测确认」的条目均为本次无法从公开资料确证的项。

---

## 1. boss-agent-cli 可借鉴设计点

官方文档：https://can4hou6joeng4.github.io/boss-agent-cli/ ；源码仓库：https://github.com/can4hou6joeng4/boss-agent-cli （MIT，2.1k star）；PyPI：https://pypi.org/project/boss-agent-cli/ （调研时最新 1.18.0，2026-07-29 发布）。

### 1.1 整体原则（「低风险、合规默认」）
- 核心不变量（来源：README https://github.com/can4hou6joeng4/boss-agent-cli ）：
  - stdout 仅 JSON 信封 `{ok, data, pagination, error, hints}`；stderr 仅日志；exit 0/1；
  - 错误信封统一带 `code` + `recoverable` + `recovery_action`，可程序化恢复；
  - 命中平台风险码 / 安全页 → **立即停止当前 workflow，保存 checkpoint**，由用户显式恢复，不无界换通道重试；
  - 所有状态本地存储：登录态、缓存、简历、候选池都在 `~/.boss-agent/`，数据不离本机。
- 技术栈：Python ≥ 3.10、Click、httpx（高斯延迟节流）、patchright（仅用于用户主动登录 / 导出）、cryptography（Fernet）、sqlite3 WAL。
- 安装约定：`uv tool install boss-agent-cli` 后需 `patchright install chromium`（浏览器内核与 CLI 分离，镜像/CI 刻意不含浏览器内核）。

### 1.2 登录链路设计（AuthManager + login/status/logout/doctor）
来源：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/troubleshooting.md 与 README。

- **登录态加密**：`AuthManager` 使用 **Fernet + PBKDF2 机器绑定加密**（README 「技术架构」一节原文：「用户主动登录态（Fernet + PBKDF2 机器绑定加密）」）。机器绑定的含义：凭据换机器后无法解密，doctor 报 `auth_session 损坏 → boss logout && boss login`。
- **登录流程**（`boss login`）：
  1. 默认先扫描本机 CDP Chrome 的所有 browser context，找到第一个带 BOSS 登录态（`wt2`）的 context 即复用，**不导航登录页、不轮询等待**；
  2. 复用时在终端打印「账号指纹」——登录态 cookie 值的**不可逆哈希前缀**（如 `context 2/2，账号指纹 c26a7f01`），不泄露 cookie 本身，用于多账号/多窗口场景人工核对；
  3. 复用后用浏览器自身会话做**一次只读探测**（用户信息接口）：通过才落盘；服务端已失效则不落盘，自动转强制重登；
  4. `boss login --cdp --force`：不扫描、不复用，先清掉当前 context 内**目标平台域**的 cookie（其他站点不动），再打开登录页重新扫码；
  5. 页签清理只作用于本次调用新建的页面，不碰用户已打开的页签。
- **登录态分层判定**（对 BOSS）：
  - `wt2` 存在 + `__zp_stoken__` 存在 = 完整可用；
  - `wt2` 存在 + `__zp_stoken__` 缺失 = 部分登录态（二维码/Cookie 提取只拿到一半），`__zp_stoken__` 需由真实页面 JS 生成；
  - `wt2` 缺失 = 无效，需 `logout && login`。
- **状态命令分层**：
  - `boss status` 默认**只检查本地加密凭据与分层健康，不请求真实平台**（避免探测本身触发风控）；
  - `boss status --live` / `boss doctor --live-probe` 才做低频只读在线验证，需显式开启。

### 1.3 doctor 检查项清单（可直接照搬到 v2.0）
来源：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/troubleshooting.md

| 类别 | 检查项 | 说明 |
|---|---|---|
| 环境 | `python` | 版本 ≥ 3.10 |
| 环境 | `patchright` / `patchright_chromium` | 包已装；Chromium + headless shell 修订版已装，Windows 同时检查 `%LOCALAPPDATA%\ms-playwright` |
| 凭据 | `credential_file` | 登录态文件存在可读 |
| 凭据 | `auth_session` | 登录态可解密（机器绑定校验） |
| 凭据 | `cookie_presence` / `wt2_presence` | Cookie 与核心 cookie 存在 |
| 凭据 | `stoken_presence` / `stoken_freshness` | `__zp_stoken__` 是否生成、是否可能过期 |
| 凭据 | `auth_token_quality` | wt2/stoken 组合状态机（完整/部分/无效） |
| 凭据 | `cookie_completeness` | 辅助凭据（wbg / zp_at） |
| 通道 | `cdp` | Chrome 调试端口可连 |
| 风控 | `cdp_risk_lock` | 只读本地锁文件，不连浏览器不联网 |
| 通道 | `browser_channel` | CDP 兼容通道状态 |
| 网络 | `network` | zhipin.com 可访问 |
| 能力 | `candidate_search_health` 等 | 只读能力前置条件 |

### 1.4 风控处理与 checkpoint 机制（v2.0 最该抄的部分）
来源：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/platform-risk.md 与 troubleshooting.md。

- **错误码分类**（与 Agent 约定）：
  - `AUTH_REQUIRED` / `AUTH_EXPIRED` / `TOKEN_REFRESH_FAILED` → 可自动恢复，动作 `boss login`；
  - `RATE_LIMITED` → 等待后重试；
  - `ENVIRONMENT_RISK`（recoverable=false）→ **立即停止自动化，不自动重登、不刷新、不重试**，保留专用 profile，用户在官方页面手动确认后再继续；
  - `ACCOUNT_RISK` → 停止 workflow，保留 run_id/checkpoint，处理后显式恢复；
  - `BROWSER_SESSION_NOT_FOUND` / `CDP_UNAVAILABLE` → 通道问题，跑 doctor。
- **stoken 风控锁（cdp_risk_lock）**：BOSS 的 `__zp_stoken__` 由页面安全脚本维护。当同一 stoken 被 httpx 与浏览器两个客户端并发使用，平台标记 code 37 环境异常。其解法值得借鉴：
  - 锁文件只存 `__zp_stoken__` 的 **SHA-256 摘要 + 时间戳**，不存原值；
  - 每次浏览器请求前从本机 CDP 读 cookie 算摘要：摘要没变 → 本地拒绝，请求根本不发出；摘要变了（页面已换新 stoken）→ 自动删锁继续；
  - 锁文件损坏/误记时由用户执行 `boss clean --risk-lock`，**Agent 不得自行执行**。
- **通道隔离**（v2.0 设计直接参考）：
  - 专用 profile 通道（crawl、research、新登录）：必须用独立 user_data_dir，不得污染用户日常 Chrome profile；
  - 现有浏览器只读通道（`--browser-source existing-browser`）：只复用已打开的目标页，不导航、不新建 context、不注入 cookie；不可用即返回 `BROWSER_SESSION_NOT_FOUND`，**不降级**到 headless 或临时 profile；
  - 严格锁定通道（`stored-cookie`）：只连指定 CDP 端点，fail-closed，不可用即 `CDP_UNAVAILABLE`，禁止降级；
  - 默认 `auto` 通道降级链：CDP → headless。
- **脱敏纪律**：Cookie、Token、`__zp_stoken__`、`security_id`、联系方式不得进入日志、错误、导出、fixture、公开 PR；Issue 模板强制脱敏。
- **预算控制**：搜索请求跨进程串行预留 5–10 秒请求窗口（SQLite 持久预算）；不得用清缓存/多开进程绕过预算。
- **配置目录**：`~/.boss-agent/config.json`（运行模式、请求间隔、日志级别、CDP 地址、导出目录、平台/角色）；支持 `--data-dir` 按项目隔离。

---

## 2. patchright 官方资料

PyPI：https://pypi.org/project/patchright/ （调研时最新 **1.64.1，2026-10-16 发布**）；驱动仓库：https://github.com/Kaliiiiiiiiii-Vinyzu/patchright 。

### 2.1 基本事实
- Python 支持：**Python ≥ 3.10**，同步 `patchright.sync_api` 与异步 `patchright.async_api` 两套 API，与 Playwright 一一对应，**drop-in replacement**（`import` 从 playwright 换成 patchright 即可）。
- **只 patch Chromium 内核**，Firefox / WebKit 不支持（官方原文）。
- 安装：`pip install patchright` 后必须 `patchright install chromium`（缺 headless shell 再补 `patchright install chromium-headless-shell`）；浏览器内核默认落在 Playwright 同一缓存目录 `%LOCALAPPDATA%\ms-playwright`（Windows）——boss-agent-cli doctor 正是检查该目录。
- License：Apache-2.0。

### 2.2 官方推荐「完全不可检测」配置（与 v2.0 直接相关）
官方 Best Practice（PyPI README 原文）：
```python
playwright.chromium.launch_persistent_context(
    user_data_dir="...",
    channel="chrome",      # 用本机真实 Google Chrome，而非自带 Chromium
    headless=False,
    no_viewport=True,
    # 不要自定义 headers / user_agent
)
```
要点：
- 推荐用 `channel="chrome"`（真实 Chrome）而非自带 Chromium，以避免指纹注入痕迹；可 `patchright install chrome` 安装，或用本机已装 Chrome；
- **不要自定义 UA / 额外 headers**（会破坏指纹一致性）；
- 持久化用 `launch_persistent_context` + `user_data_dir`。

### 2.3 反检测原理（官方列出的 patch 点）
- **Runtime.enable 泄漏**（最大补丁）：patchright 避免使用 `Runtime.enable`，改用隔离 ExecutionContext 执行 JS；
- **Console.enable 泄漏**：直接禁用 Console API —— 代价是 `page.on("console")` 收不到日志，调试时需用 JS logger；
- **命令行参数泄漏**：加 `--disable-blink-features=AutomationControlled`、移除 `--enable-automation`、移除 `--disable-popup-blocking` / `--disable-component-update` / `--disable-default-apps` / `--disable-extensions` 等自动化特征参数；
- **Closed Shadow Roots**：可直接对 closed shadow root 内元素用普通 locator / XPath；
- 官方宣称通过 Brotector / Cloudflare / Kasada / Akamai / DataDome / Fingerprint.com / CreepJS / Sannysoft 等指纹检测。

### 2.4 与 Playwright 的 API 差异（仅扩展，不破坏）
官方文档：除下列新增参数外，API 与 Playwright 完全一致（官方指向 Playwright 文档 https://playwright.dev/docs/api/ ）：
- `evaluate` / `evaluate_handle` / `evaluate_all` 新增 `isolated_context: bool = True` 参数，选择在 Main 还是 Isolated ExecutionContext 执行。
- **storage_state 机制与 Playwright 相同**：`context.storage_state(path="state.json")` 导出 cookie + localStorage；新建 context 时 `browser.new_context(storage_state="state.json")` 恢复。（Playwright 官方文档：https://playwright.dev/docs/auth 、https://playwright.dev/docs/api/class-browsercontext#browser-context-storage-state ）

### 2.5 已知局限 / 风险（官方 issue 与文档）
- 有 issue 报告 **Kasada 已能检测 patchright**（2025-06，https://github.com/Kaliiiiiiiiii-Vinyzu/patchright/issues/96 ）——反检测是猫鼠游戏，不能视为永久免疫；
- 代理场景下 **WebRTC 泄漏真实 IP**（issue #128）；
- 第三方观察称 patchright 会破坏 proxy auth（CloakBrowser README，https://github.com/HotOpenSourcing/CloakBrowser ）；
- 官方 Disclaimer：教育用途、按现状提供、维护方不担责；Playwright 代码库升级后可能出 bug，修复需数日。

---

## 3. 四平台登录调研

### 3.1 Boss 直聘（zhipin.com）
- **登录页 URL**：`https://www.zhipin.com/web/user`（社区自动化文章实证：`driver.get("https://www.zhipin.com/web/user")` 后用户 2 分钟内手动完成登录——https://developer.cloud.tencent.com/information/... ）；带来源参数的变体 `https://www.zhipin.com/web/user/?ka=header-login`（从首页右上角登录按钮跳转，参数名需实测确认）。
- **扫码入口**：登录页默认展示二维码，用「BOSS直聘 APP」扫码；官方 FAQ 确认扫码流程及二维码加载异常处理（https://www.zhipin.com/desktop/faq/ 、https://www.zhipin.com/faq/app/1/ ）。二维码本身有有效期，加载失败有 request error / timeout 提示。
- **登录成功判定信号**（来自 boss-agent-cli 官方文档，高可信）：
  - 核心 cookie **`wt2`** 存在 = 已登录；缺失 = 未登录；
  - **`__zp_stoken__`** = 页面安全脚本维护的风控 token，未登录页就会种下，需由真实页面 JS 刷新；`wt2` 有但 `__zp_stoken__` 缺 = 部分登录态；
  - 辅助 cookie：`wbg`、`zp_at`；
  - 来源：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/troubleshooting.md 。
- **登录态有效期 / 过期表现**：`wt2` 有效期较长（按 boss-agent-cli 经验可跨天复用，具体天数需实测确认）；`__zp_stoken__` 是易逝 token，页面内会自动轮换；服务端失效时接口返回 `AUTH_EXPIRED`；环境异常时返回 code 37（ENVIRONMENT_RISK）。
- **反爬 / 风控特点**：四平台中最重——`__zp_stoken__` 双重客户端并发使用会触发 code 37 环境锁；职位列表请求建议 5–10 秒间隔；有滑块/安全页（平台风险边界文档）。
- **多账号/设备限制**：多 context 复用时取「第一个带登录态的 context」；官方建议账号与设备/IP 绑定使用，不建议频繁切换账号（需实测确认）。

### 3.2 前程无忧 51job（51job.com）
- **登录页 URL**：`https://login.51job.com/login.php?lang=c&from_domain=51job_web`（已实际访问观察：页面提供「手机号登录/注册」「账号密码登录」两个 tab，手机号支持 +86 等国际区号）。
- **扫码入口**：求职者侧登录页本次观察到的文本只有手机/密码两个 tab；**二维码扫码入口是否存在于该登录页（通常为登录卡片右上角小图标）需实测确认**。企业侧（eh.51job.com/Navigate.aspx）明确提供「微信扫码 + 前程无忧 APP 扫码」登录——https://eh.51job.com/Navigate.aspx 。
- **登录成功判定信号**：**需实测确认**。公开资料未见权威 cookie 名清单；隐私条款仅泛述「通过 cookie 登录」（https://www.51job.com/bo/pdf/51Job_2021_09_16.pdf ）。建议 spike 时先抓未登录基线 cookie，再对比登录后新增 cookie（参照智联的基线法，见 3.3）。
- **登录态有效期**：需实测确认。
- **反爬特点**：公开资料显示其反爬强度弱于 Boss（社区 Playwright 教程可较直接地操作，https://blog.51cto.com/goku0623/8561466 ）。
- **多账号限制**：需实测确认。

### 3.3 智联招聘（zhaopin.com）
- **登录页 URL**：`https://passport.zhaopin.com/login`（本次实测可访问，提供手机号+短信验证码登录；校园等子站走 `passport.zhaopin.com/additional?appID=...&redirectURL=...` 变体）。
- **扫码入口**：**微信扫码**——用微信关注「智联校园招聘」公众号完成扫码登录（实证：https://passport.zhaopin.com/additional?... 页面文案「qrcode 请使用微信【扫一扫】关注「智联校园招聘」公众号完成登录」）。求职者主站是否同样为微信扫码需实测确认（区别于 Boss 的 APP 内扫码）。
- **登录成功判定信号**（社区实战文章，2026-06，https://juejin.cn/post/7651998644058177542 ）：
  - 真正登录态 cookie 只有两个：**`at`（access token，32 位随机串）+ `rt`（refresh token，32 位随机串）**，非 httpOnly（前端可读）；
  - **关键陷阱**：未登录时浏览器就会种下一堆 WAF/追踪 cookie（`Hm_*`、`sts_*`、`x-zp-client-id`、`sensorsdata*`、`ZP_OLD_FLAG`），只判断「有没有 cookie」会**假成功**；
  - **可靠判定法 = 基线差分**：打开登录页前先记录基线 cookie 名集合，之后轮询，命中 `at`/`rt` 且**不在基线集合**才算真登录。
- **登录态有效期**：at/rt 双 token 结构暗示 at 短期、rt 可刷新；具体时长需实测确认。
- **反爬特点**：有滑块验证码（带行为检测，社区实测 CV 无法自动过，必须人过一次 + profile 持久化免登）；Vue + 事件委托，合成 click 可能被吞（需 mouse.move+原生 click+轮询 DOM 三连发）；投递结果判定要拦 XHR 响应而不是看 HTML。
- **多账号限制**：需实测确认。

### 3.4 猎聘（liepin.com）
- **登录页 URL**：`https://www.liepin.com/login`（本次实测可访问：手机号 +86 + 短信验证码登录）。
- **扫码入口**：**微信扫码登录**（实证：https://wow.liepin.com/t1012621/01ab459c.html 页面「请使用微信扫描二维码登录猎聘 / 微信扫码登录」）；**首次微信扫码需绑定手机号**（https://lpt.liepin.com/login/wx-bind 「首次扫码登录需要绑定手机号，以后可以使用该手机号快速登录」）。
- **登录成功判定信号**：
  - 猎聘官方 MCP 授权页 `https://www.liepin.com/mcp/auth` 可获取 **`x-user-token`** 请求头作为 API 凭据（第三方自动化向导引用：https://skillhub.cloud.tencent.com/skills/liepin-auto-apply-wizard ）——这是官方认可的程序化登录态形态；
  - Web cookie 层面的登录态 cookie 名（替代 `x-user-token` 的浏览器内凭据）**需实测确认**。
- **登录态有效期 / 过期表现**：需实测确认。
- **反爬特点**：第三方项目记录猎聘求职侧投递多为「招聘者 IM 介导」（点开聊天气泡），自动化投递被有意不支持（https://raw.githubusercontent.com/HA7CH/job-pro/HEAD/docs/auto-apply.md ）——说明其核心动作链路偏 IM，纯 HTTP 自动化空间小。
- **多账号限制**：需实测确认。

---

## 4. v2.0 登录中心设计建议输入

### 4.1 登录态文件路径规划
参照 boss-agent-cli 的 `~/.boss-agent/` 约定，建议本项目采用**项目内、平台隔离**布局：
```
get-jobs-auto/
├─ data/                         # 运行期数据，gitignore
│  ├─ auth/
│  │  ├─ zhipin.enc              # 加密后的登录态（Fernet/DPAPI 密文）
│  │  ├─ zhipin.meta.json        # 明文元信息：登录时间、账号指纹hash、状态、stoken摘要
│  │  ├─ 51job.enc / .meta.json
│  │  ├─ zhaopin.enc / .meta.json
│  │  └─ liepin.enc / .meta.json
│  ├─ profiles/                   # 持久化浏览器 user_data_dir（每平台一个）
│  │  ├─ zhipin/
│  │  ├─ 51job/
│  │  ├─ zhaopin/
│  │  └─ liepin/
│  └─ risk-locks/                 # 各平台风控锁文件（只存摘要）
```
要点：密文与元信息分离；meta 里只存「账号指纹」（cookie 不可逆哈希前缀，借鉴 boss-agent-cli 多窗口核对设计），不存原值。

### 4.2 加密方案对比（Windows 环境）
| 方案 | 优点 | 缺点 | 建议 |
|---|---|---|---|
| **Windows DPAPI**（`win32crypt.CryptProtectData` / Python `pywin32` 或 `ctypes`） | 系统原生，密钥绑定当前 Windows 用户 + 机器，零密钥管理；无需存主密码；解密无需任何用户输入 | 强 Windows 绑定，换机器/换 Windows 用户即不可解密；跨平台（未来 macOS）要另写分支；依赖额外包 | 本机工具首选 |
| **cryptography Fernet + PBKDF2**（boss-agent-cli 同款） | 纯 Python 跨平台；可「机器绑定派生」（用机器特征+固定 salt 做 PBKDF2 派生密钥）实现近似 DPAPI 的零交互 | 机器绑定是自实现的，强度不如 DPAPI 原生；需自己处理密钥派生细节 | 想跨平台一致时选它 |
| keyring（系统钥匙串） | 语义好 | 登录态是批量 cookie 而非单 key，不合适 | 不推荐 |

建议：v2.0 先实现 **DPAPI（Windows）优先 + Fernet 回退** 的加密抽象层；参照 boss-agent-cli 的做法把「机器绑定」做成 doctor 可检查项（`auth_session` 检查项），解密失败即提示重新登录。

### 4.3 过期如何提示
- 分层判定（照搬 boss-agent-cli）：`status` 命令默认**只读本地密文做离线判定**（文件存在 / 可解密 / 核心 cookie 名存在），不发任何网络请求；
- `status --live` 显式做一次低频只读探测（各平台「我的主页/用户信息接口」）；
- 过期/失效时输出结构化提示：哪个平台、哪一层失效（如 Boss：`wt2 缺失 → 需重新扫码` / `__zp_stoken__ 缺失 → 页面内刷新即可`）；
- 命中风控类错误（环境异常/安全页）时，明确提示「停止自动化，浏览器留着别关，人工打开该平台页面确认」，并写 risk-lock 文件，锁定期内拒绝自动重试。

### 4.4 user_data_dir 与 storage_state 两条路线取舍
- **路线 A：launch_persistent_context(user_data_dir=...) 为唯一真相**（推荐 v2.0 主路线）。
  - 优点：与 patchright 官方推荐配置一致（channel="chrome" + 持久 profile）；登录态、指纹、页面安全脚本状态（如 Boss 的 `__zp_stoken__`）全部由浏览器自己维护，不需要程序提取/注入 cookie；天然规避「httpx 与浏览器并发同一 stoken」这类 boss-agent-cli 踩过的坑（platform-risk.md）；
  - 缺点：无法 headless 复用同一 profile（Chrome 单实例锁），投递内核与登录中心必须共用同一个 profile 目录约定；
- **路线 B：storage_state(json) 导出 cookie/localStorage 再注入新 context**。
  - 优点：可无头、可多 context 并发、状态文件可移植；
  - 缺点：对 Boss 这类 `__zp_stoken__` 由页面 JS 动态维护、且严禁两客户端并发的平台，导出注入等于复刻「双重客户端」风控（code 37）；智联的 at/rt 虽然是静态 token，但基线差分判定要重做。
- **结论建议**：登录中心与投递内核**共用同一个持久化 profile（路线 A）**，storage_state 仅作为「登录完成后备份一份加密导出」的补充手段（便于审计/换机迁移），不作为运行时注入通道。

### 4.5 四平台管理：命名 / 隔离 / 并发
- **命名**：平台 id 固定小写 `zhipin / 51job / zhaopin / liepin`，与目录、文件名、命令参数一一对应（借鉴 boss-agent-cli 的 `--platform` 全局选项 + Platform 注册表）；
- **隔离**：每平台独立 user_data_dir（见 4.1），登录中心一次只操作一个平台一个窗口；多账号时同平台允许「profile-账号名」二级目录，doctor 打印账号指纹供人工核对；
- **并发限制**：四平台串行轮转，单平台请求间隔 ≥ 5–10 秒（Boss 官方建议量级）；任意平台命中风控立即全局暂停该平台，写 risk-lock，等待人工确认；
- **统一抽象**：定义 `PlatformLoginAdapter` 接口（`login_page_url / detect_login_success(baseline_diff) / live_probe / core_cookies`），四平台各一份实现；新增平台走准入评估（boss-agent-cli docs/research/platforms/README.md 的做法）。

---

## 5. 高不确定项清单（「需实测确认」）

1. 51job 求职者侧登录页是否有扫码入口（本次只观察到手机/密码 tab）；其登录态 cookie 名清单完全无公开资料。
2. 智联主站扫码是否同为微信扫码（仅子站实证）；at/rt 的实际有效期。
3. 猎聘浏览器内 web cookie 登录态名（仅有官方 MCP 的 x-user-token 形态）；猎聘 web 登录态有效期。
4. Boss `wt2` 的具体有效期天数；`?ka=header-login` 参数现状。
5. 各平台多账号/设备限制的具体表现（公开资料不足）。
6. patchright 对四平台风控的实际通过率（官方宣称通过的是国际指纹检测，国内招聘平台 WAF 无官方背书；issue 显示 Kasada 已能检测它）。

---

## 6. 关键来源 URL 清单

- boss-agent-cli 官网：https://can4hou6joeng4.github.io/boss-agent-cli/
- boss-agent-cli 仓库：https://github.com/can4hou6joeng4/boss-agent-cli
- README（技术架构/配置/存储）：https://github.com/can4hou6joeng4/boss-agent-cli
- 平台风险边界：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/platform-risk.md
- 诊断与排障（doctor 检查项/登录流程/风控锁/错误码）：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/troubleshooting.md
- 快速上手：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/getting-started.md
- PyPI boss-agent-cli：https://pypi.org/project/boss-agent-cli/
- patchright PyPI：https://pypi.org/project/patchright/
- patchright 驱动仓库：https://github.com/Kaliiiiiiiiii-Vinyzu/patchright
- patchright Kasada 检测 issue：https://github.com/Kaliiiiiiiiii-Vinyzu/patchright/issues/96
- Playwright storage_state 文档：https://playwright.dev/docs/auth
- Boss 登录页社区实证：https://developer.cloud.tencent.com/information/具有自动完成功能的Java%20JComboBox-article
- Boss 桌面端扫码 FAQ：https://www.zhipin.com/desktop/faq/
- 51job 登录页：https://login.51job.com/login.php?lang=c&from_domain=51job_web
- 51job 企业侧扫码登录：https://eh.51job.com/Navigate.aspx
- 智联登录页：https://passport.zhaopin.com/login
- 智联微信扫码登录实证：https://passport.zhaopin.com/additional?appID=8b25de552a844b6c8493333ce98b9caf&redirectURL=http%3A%2F%2Fxiaoyuan.zhaopin.com%2Fscrd%2Fdelivery%2Frecord
- 智联 at/rt cookie 与反爬实战：https://juejin.cn/post/7651998644058177542
- 猎聘登录页：https://www.liepin.com/login
- 猎聘微信扫码登录实证：https://wow.liepin.com/t1012621/01ab459c.html
- 猎聘首次扫码绑手机：https://lpt.liepin.com/login/wx-bind
- 猎聘 x-user-token 官方授权页：https://www.liepin.com/mcp/auth
- 猎聘投递 IM 介导说明：https://raw.githubusercontent.com/HA7CH/job-pro/HEAD/docs/auto-apply.md
