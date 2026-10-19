# 登录中心扫码登录 —— patchright 可行性验证 Spike

> 本目录是**技术可行性验证（spike）**，与主应用完全隔离，不改动 `backend/`、`frontend/`、根 `requirements.txt` 等任何现有文件。
> 目标：用最小成本验证「patchright 持久化 context + storage_state」能否支撑 Boss 直聘扫码登录链路。
> 原则：**不绕过任何风控 / 验证码 / 滑块**；真实扫码一律留给真人。

---

## 1. 可行性结论（TL;DR）

| 验证项 | 结论 |
|---|---|
| patchright 安装与独立 chromium | ✅ 可行，不污染系统 Chrome/Edge |
| 反检测指纹（webdriver / WebGL / plugins） | ✅ 实测像真人，`navigator.webdriver=false` |
| 持久化 context 独立 user_data_dir | ✅ 可用，目录隔离 |
| storage_state 存取闭环（公开站点） | ✅ PASS（localStorage 可跨全新 context 恢复） |
| Boss 登录页可正常打开 + 二维码渲染 | ✅ 实测成功，已出截图 |
| 扫码成功 → 保存登录态 → 免登录重开 | ✅ **真人扫码实测通过**（2026-10-19）：verify-state 落地已登录首页，右上角显示本人头像+用户名 |
| 全程是否触发风控/滑块/安全验证 | ✅ 未触发，正常进入首页 |

**总体判断：patchright 路线技术可行，推荐作为 v2.0 登录中心的底层方案。** 2026-10-19 已完成真人扫码全链路闭环：wait-login 检测到登录 → `storage_state` 落盘 → 全新 headless 环境加载 `storage_state` 免登录打开 Boss（verify-state 落地 `https://www.zhipin.com/wuhan/` 已登录首页，右上角显示本人头像与用户名，exit 0），全程未触发滑块/安全验证。

> 本轮是以"持久化 profile 复用、自动登录"的方式触发成功（实测 cookie/URL 见 7.3）；**"全新匿名 profile 第一次扫码、强信号 `wt2` 当轮从无到有"这条主链路的现场判定，代码已就绪但本轮未在可见窗口完整复演**（用户选择先推送），列为下轮首要补验项（见 11.2）。

---

## 2. 环境与安装

- Python：`py -3.12`（实测 3.12.10），全程用此解释器。
- 仓库根：`C:\Users\28030\Desktop\豆包测试\GetJobs\get-jobs-auto`

### 2.1 安装命令（已实测）

```powershell
py -3.12 -m pip install patchright
# 国内直连 playwright CDN 会卡住（0 字节不动），必须走镜像：
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright"
py -3.12 -m patchright install chromium
```

### 2.2 实测版本号（已记录）

| 组件 | 版本 |
|---|---|
| patchright（pip 包） | **1.64.1**（`patchright/_repo_version.py`） |
| patchright 内置 pyee | 14.0.0 |
| Chromium 内核（独立下载，非系统 Chrome） | **156.0.8078.4**（playwright build **v1248**，目录 `chromium-1248`） |
| Chromium Headless Shell | 156.0.8078.4（build v1248，目录 `chromium_headless_shell-1248`） |
| FFmpeg | v1013 |

> 下载产物落在 `%LOCALAPPDATA%\ms-playwright\`，是 patchright 自己的独立内核，**不触碰用户系统 Chrome / Edge**。
> 依赖版本只在本 README 声明，**未写入根 requirements.txt**（红线要求）。

---

## 3. 目录结构与文件清单

```
spikes/login_patchright/
├── spike.py                       # 全部子命令入口（sync_api）
├── run-login.bat                  # Windows 双击/运行启动器：在用户桌面弹出可见浏览器等扫码（纯 ASCII）
├── README.md                      # 本文档
├── platforms-research.md          # 四平台登录调研 + v2.0 设计建议
├── .gitignore                     # 忽略 profiles/ state/ 与登录后截图
├── profiles/boss/                 # 持久化 user_data_dir（独立，绝不指向日常 Chrome）
├── state/
│   ├── fingerprint.json            # 反检测指纹实测输出
│   ├── public_storage_state.json  # 公开站点自测用 state（非敏感）
│   └── boss_storage_state.json     # 【登录成功后生成】Boss cookie+localStorage（敏感，已 gitignore）
└── screenshots/
    ├── boss_login.png             # Boss 登录页 + 扫码二维码截图（登录前，无个人信息，已纳入 git）
    └── verify_state.png           # 免登录校验截图（含本人头像，已 gitignore 不入库）
```

> `profiles/`、`state/` 内含会话凭证，已在 `.gitignore` 整体忽略。
> 截图默认整体忽略，仅保留 `boss_login.png`（登录前页面，无个人信息）作为证据；登录后截图 `verify_state.png` 可能含个人信息，故不入库。

---

## 4. 运行步骤（子命令）

统一在仓库根执行：

```powershell
# (0) 一次性：反检测指纹采集（自动开关浏览器，约 10 秒）
py -3.12 spikes\login_patchright\spike.py fingerprint

# (1) 公开站点 storage_state 存取闭环自测（无需登录，自动）
py -3.12 spikes\login_patchright\spike.py public-test

# (2) 打开 Boss 登录页并截图（自动切到扫码标签，自动关闭）
py -3.12 spikes\login_patchright\spike.py open-login

# (3) 【需真人扫码】打开登录页，等待扫码，自动检测成功并保存 state
py -3.12 spikes\login_patchright\spike.py wait-login --timeout 300

# (4) 校验已保存的 state 是否仍免登录（无头，自动）
py -3.12 spikes\login_patchright\spike.py verify-state
```

**Windows 桌面扫码（推荐真人用）**：直接双击 `run-login.bat`（或在「运行」对话框执行它），会在用户桌面弹出可见浏览器等扫码。**不要用后台/服务方式启动 GUI**——从 agent 后台 shell / `Start-Process` 拉起的浏览器窗口在用户桌面不可见（实测进程在 Session 1 仍无窗口，见第 10 节坑 5）。

退出码约定：`0` 成功；`public-test` 失败为 `1`；`wait-login` 超时为 `2`；`verify-state` 缺文件为 `3`、登录态失效为 `4`。

---

## 5. 各阶段脚本说明

脚本基于 **sync_api**（`from patchright.sync_api import sync_playwright`），关键 API 均已对照 site-packages 源码核实：

- `p.chromium.launch_persistent_context(user_data_dir, headless=..., viewport=...)` → 直接返回持久化 `BrowserContext`（无需再 `launch`）。
- `context.storage_state(path=...)` → 把 cookies + localStorage（+可选 IndexedDB）落盘为 JSON。
- `p.chromium.launch(headless=...)` → 起全新浏览器；`browser.new_context(storage_state=<json路径>)` → 无 cookie 共享的全新 context 里恢复登录态。

### 5.1 fingerprint
在持久化 context 里打开 `example.com`，`page.evaluate` 采集 `navigator.webdriver`、`window.chrome`、plugins、WebGL vendor/renderer、UA、屏幕、CPU/内存等，写入 `state/fingerprint.json`。

### 5.2 public-test
公开站点持久化闭环：
1. 持久化 context 打开 `https://example.com/`，写 `localStorage["__spike_persist_marker__"]`；
2. `context.storage_state(path=...)` 落盘；
3. **全新非持久化 context** 用 `new_context(storage_state=文件)` 加载，再读回该 key。
> localStorage 按 origin 隔离，三步都在 `https://example.com/` 同一 origin，保证可比。

### 5.3 open-login
`headless=False` 打开 `https://www.zhipin.com/web/user/?ka=header-login`，自动点击「APP扫码登录」标签切到二维码视图，截图到 `screenshots/boss_login.png`，打印落地 URL 与当前 cookie 名，然后关闭浏览器。

### 5.4 wait-login（等真人扫码）
打开登录页后进入轮询（每 2 秒一次，上限 `--timeout` 秒）：
- 记录登录前 baseline cookie 名集合；
- 每次轮询打印 URL 变化、对比 cookie 名变化；
- **强成功信号**：新 cookie 名集合中出现 `wt2`（不在 baseline）**且** URL 已离开登录路由 → 立即判定成功（不必等连续稳定）；
- **并列兜底信号**：URL 离开登录路由并连续 2 次稳定停留 → 也判定成功；
- 成功后 `context.storage_state(path=state/boss_storage_state.json)` 保存；超时则不保存并退出码 2。
- 判定细节与 `wt2`/`__zp_stoken__` 的来源、组合取舍见第 7.2 / 7.3 节。

### 5.5 verify-state
无头启动全新浏览器，`new_context(storage_state=state/boss_storage_state.json)` 加载，打开 Boss 首页：
- 若落地仍含 `/web/user` 等登录路由 → 判定登录态失效；
- 否则 → 判定免登录有效；
- 同时打印携带的 cookie 名与落地 URL，并截图 `screenshots/verify_state.png`。

---

## 6. 反检测指纹实测结果（example.com，已存 `state/fingerprint.json`）

| 指纹项 | 实测值 | 判定 |
|---|---|---|
| `navigator.webdriver` | **`false`** | ✅ 原生 playwright 此处为 `true`，patchright 已掩盖 |
| `window.chrome` 存在 | `true` | ✅ 像真 Chrome |
| `window.chrome.runtime` | `false` | ⚠ headless/独立内核常见，可接受；真 Chrome 普通窗口为 true，v2.0 可按需注入 |
| `navigator.plugins.length` | **5**（PDF Viewer / Chrome PDF Viewer / Chromium PDF Viewer / Edge PDF Viewer / WebKit built-in PDF） | ✅ 非空，不像无头浏览器 |
| `navigator.userAgent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/156.0.0.0 Safari/537.36` | ✅ 正常 Chrome UA |
| `navigator.languages` | `["zh-CN","zh"]` | ✅ |
| `navigator.platform` | `Win32` | ✅ |
| `navigator.hardwareConcurrency` / `deviceMemory` | 12 / 16 | ✅ 有真实硬件值 |
| WebGL vendor | `Google Inc. (AMD)` | ✅ |
| WebGL renderer | `ANGLE (AMD, AMD Radeon(TM) Graphics ... Direct3D11 ... D3D11)` | ✅ **真实 GPU 渲染器**，无头浏览器常暴露为 `Google SwiftShader`，patchright 未暴露该破绽 |

> 小坑记录：`screen` 字段里 devicePixelRatio 显示 undefined，是我脚本里误读了 `screen.devicePixelRatio`（应为 `window.devicePixelRatio`），不影响反检测结论，v2.0 修正即可。

**结论：patchright 默认的反检测已覆盖最容易被风控识别的几项（webdriver、plugins、WebGL），实测无明显破绽。**

---

## 7. Boss 登录成功判定依据

### 7.1 已实测观察到的（登录前 / 匿名态）
- 登录页 URL：`https://www.zhipin.com/web/user/?ka=header-login`（脚本落地后确认就是它）。
- 登录前匿名 cookie 名（**只记录名字，不记录值**）：`__a`, `__c`, `__g`, `__l`, `ab_guid`, `isOHPC`。
- 登录页有两个视图：默认「验证码登录/注册」（手机号+短信码），以及「APP扫码登录」标签（二维码）。二维码由 JS 动态渲染，截图时已正常出现。

### 7.2 wait-login 采用的判定信号（强信号 + 并列信号，组合防误判）
脚本每 2 秒轮询一次，判定登录成功的逻辑为：
1. **强信号 —— 核心会话 cookie `wt2` 新出现 且 URL 已离开登录路由**：`wt2` 不在登录前 baseline cookie 名集合里（=登录后才下发），同时当前 URL 已跳离 `/web/user`。命中即判定成功，不必再等 URL 连续稳定。
2. **并列信号（兜底）—— URL 离开登录路由并稳定停留**：当前 URL 不再包含 `/web/user`、`ka=header-login`，且仍在 `www.zhipin.com` 域内，并连续 ~4 秒（2 次轮询）保持，避免登录中跳转的瞬态误判。
3. **全程记录**：每次轮询打印 URL 变化，并在成功时打印「baseline 之外新出现的全部 cookie 名」，供真人扫码后回填精确清单。

> 为什么强信号是「`wt2` 且离开登录路由」的组合，而不是单看 `wt2`：
> 公开资料（见 7.3）显示 Boss 的风控 token `__zp_stoken__` 在**未登录页就会被页面 JS 种下**；而 `wt2` 是否也可能在某些未登录浏览时被预先种下并不确定。因此脚本要求 `wt2` 是「登录前没有、登录后才出现」（baseline 差分）**并且** URL 确已跳离登录页，双条件同时满足才判成功，避免把未登录态误判为已登录。这是本 spike 的取舍，已写进 `spike.py`。

### 7.3 真人扫码实测结果（2026-10-19，只记 cookie 名，绝不记值）

**A. 干净匿名 baseline（今日早些时候两次 wait-login，未登录态）**：`__a`, `__c`, `__g`, `__l`, `ab_guid`, `isOHPC` —— **不含 `wt2`**，与资料「wt2 存在=已登录」一致。

**B. 本轮成功时 wait-login 采到的 baseline（持久化 profile 已含登录态，复用）**：`HMACCOUNT_BFESS`, `__a`, `__zp_stoken__`, `ab_guid`, `bst`, `isOHPC`, `wbg`, `wt2`, `zp_at`。
- 注意：**`__zp_stoken__` 在未登录页就已出现**，印证资料"它由页面安全 JS 预先种下、会自动轮换"，不能单独作为登录判据；`bst`/`wbg`/`HMACCOUNT_BFESS` 也非登录凭证。

**C. 登录后相对 baseline 新增的 cookie**（兜底信号命中时打印）：`HMACCOUNT`, `Hm_lpvt_194df…`, `Hm_lvt_194df…`, `SERVERID`, `__c`, `__g`。
- `HMACCOUNT`/`Hm_*` 是统计/会话类 cookie，**不是登录凭证**；真正的会话凭证 `wt2`/`zp_at` 在本轮已处于 baseline（profile 复用），故未出现在"新增"列表里。

**D. verify-state 全新 headless context 携带的完整 cookie 名**：`HMACCOUNT`, `HMACCOUNT_BFESS`, `Hm_lpvt_…`, `Hm_lvt_…`, `SERVERID`, `__a`, `__c`, `__g`, `__zp_stoken__`, `ab_guid`, `bst`, `isOHPC`, `lastCity`, `wbg`, `wt2`, `zp_at`。
- **关键**：`wt2`、`zp_at`、`wbg` 在全新 headless 环境（仅加载 storage_state）下仍被携带并被服务端接受，证明 storage_state 确实恢复了登录态。

**E. 落地 URL（已登录）**：`https://www.zhipin.com/wuhan/?seoRefer=index`（按用户定位城市，首页右上角显示"消息 / 简历 / 用户名 + 头像"），未被重定向到 `/web/user`。截图 `screenshots/verify_state.png`（含本人头像，已 gitignore）。

**F. 风控**：本次登录与 verify-state 全程**未出现滑块、安全验证、环境异常（code 37）**。

> 与资料信号的对照：核心 cookie **`wt2`**、辅助 **`zp_at` / `wbg`**、风控 token **`__zp_stoken__`（未登录页就有）** 全部与 boss-agent-cli 官方文档（来源见下）吻合。
> 来源：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/troubleshooting.md ；仓库 https://github.com/can4hou6joeng4/boss-agent-cli

**两点重要结论（写进 v2.0 设计）**：
1. **本轮走的是"兜底信号"（URL 离开登录页稳定停留）**，因为 `wt2` 已在 baseline（profile 复用）。干净匿名 profile 第一次扫码时，`wt2` 才会在 baseline 之外"从无到有"地触发强信号——**该强信号分支代码已就绪，但本轮未在可见窗口完整复演，列为下轮补验**。
2. storage_state 全新 headless 注入在**单次只读验证**下成功且未触发 code 37；但调研 4.4 已提示：**生产中并发投递时，同一 `__zp_stoken__` 被浏览器与 HTTP 客户端并发使用会触发 code 37 环境锁**，因此投递内核仍建议以"持久化 profile 为唯一真相"，storage_state 只作登录后备份/迁移，不作为运行时多客户端注入通道。

---

## 8. storage_state 保存内容与位置建议

- 保存动作：`context.storage_state(path=...)`，内容为 **cookies + localStorage 快照**（v1.64 还可含 IndexedDB / OPFS / WebAuthn，spike 默认未开启）。
- spike 阶段明文落盘到：`spikes/login_patchright/state/boss_storage_state.json`。
- **红线提醒：这是明文 JSON，内含登录会话凭证，已加入 .gitignore 绝不入库。**

生产建议（v2.0）：
- **加密落盘**：用主应用已有的密钥（如 Ferner / 系统 DPAPI）加密后再写盘，运行时解密到内存。
- 存储位置：不要放仓库；放用户数据目录（如 `%APPDATA%/<app>/state/boss.enc.json`）。
- 区分两类凭证来源：本 spike 用的是"扫码后 storage_state 导出"；v2.0 可同时保留"持久化 user_data_dir 直接复用"作为兜底（profiles/boss 即此机制的实测样本）。
- 文档里**绝不粘贴真实 cookie/token 值**，只描述"是否已保存、保存了哪类（cookie/localStorage）"。

---

## 9. 登录态有效期如何观测

真实登录态已拿到（**T0 = 2026-10-19 17:38**，state 落盘时间），有效期按以下方法继续观测：
1. 扫码成功 → `wait-login` 保存 state，记下时间戳 T0。
2. 间隔不同时间（如 1 小时 / 1 天 / 3 天 / 7 天）各跑一次 `verify-state`：
   - 落地 URL 仍不在登录路由 → 登录态有效；
   - 被踢回 `/web/user` → 登录态失效，需重新扫码。
3. 把每次的 T、结果、携带的 cookie 名记录下来，即得到"Boss 扫码登录态实际存活时长"。
4. v2.0 据此决定：是否需要"临期前主动刷新"或"失效自动弹回扫码"的产品策略。

> 观测记录（每跑一次 verify-state 追加一行，格式：时间 | 落地 URL | 结果 | 关键 cookie 是否含 wt2）：
> - 2026-10-19 17:40 | `https://www.zhipin.com/wuhan/?seoRefer=index` | ✅ 有效（T0+2 分钟，含 wt2，头像/用户名正常） | —

---

## 10. 遇到的坑（已解决）

1. **pip 后 `patchright install chromium` 卡在 0 字节**：直连 playwright 官方 CDN 在国内不通。解决：先设 `$env:PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright"` 再装，秒下。
2. **`page.evaluate()` 只接受一个参数**：最初误传 `(expr, key, value)` 两个 Python 参数报 `takes from 2 to 3 positional arguments but 4 were given`。改为把多值打包成数组 `([k,v] => ..., [k,v])` 解决。
3. **PowerShell 把 pip/patchright 的 stderr 当成 NativeCommandError**：exit code 1 不代表失败，要以 stdout 里的 "Successfully installed / downloaded" 为准。
4. 登录页默认停在「验证码登录」视图，需主动点「APP扫码登录」标签才出二维码（脚本已自动点）。
5. **【关键】agent 后台 shell / `Start-Process` 拉起的 GUI 浏览器窗口在用户桌面不可见**：用后台任务（`run_in_background`）或 shell `Start-Process` 跑 `wait-login`，脚本日志正常（能打开页面、采到 baseline cookie），但**用户桌面看不到任何浏览器窗口**，真人无法扫码（实测进程虽在 `SessionId=1`，主窗口仍不在交互桌面）。连续两次 300 秒超时均因此。解决：**让浏览器从用户交互式桌面启动**——Windows 下直接双击 `run-login.bat`，或用「运行」对话框（Win+R）执行；桌面自动化里则用 `Win+R` 路径，不能用 shell 后台派生。
6. **bat 含中文、UTF-8 无 BOM 会被 cmd 按 GBK 误读**：`run-login.bat` 最初含中文 echo 且用 UTF-8 保存，`chcp 65001` 生效前的中文字节被按 GBK 解析，报"xxx 不是内部或外部命令"。解决：**启动器 bat 保持纯 ASCII（echo 全英文）**，中文引导信息交给 Python 在 `chcp 65001` 后输出；中文路径一律用 `%~dp0` 运行时展开，不手写中文。
7. **桌面自动化 `type` 输入中文路径会丢字符**：Win+R 里直接键入含中文的 bat 路径（`…\豆包测试\GetJobs\…`），中文段被输入法吞掉，只剩 ASCII 后半段；8.3 短路径对中文目录名也不转换（仍保留中文）。解决：在纯英文路径（如 `C:\Users\<用户>\`）放一个 **GBK 编码的转发 bat**（`call` 真正的中文路径脚本），Win+R 只键入纯英文路径。

---

## 11. 自检勾选清单 与 遗留问题清单

### 11.1 已自测通过（本次实测）
- [x] patchright 1.64.1 + 独立 chromium 156.0.8078.4 安装成功，不碰系统浏览器
- [x] `py_compile spike.py` 通过
- [x] 反检测指纹采集：`webdriver=false`、plugins=5、真实 WebGL GPU
- [x] 公开站点 storage_state 存取闭环：**PASS**（localStorage 跨全新 context 一致）
- [x] Boss 登录页真实打开，落地正确 URL，二维码截图 `screenshots/boss_login.png` 可见
- [x] **真人扫码 wait-login 成功**：检测到登录后自动保存 `state/boss_storage_state.json`（本轮走兜底信号，见 7.3）
- [x] **verify-state 全新 headless 环境加载 storage_state 免登录成功**：落地 `https://www.zhipin.com/wuhan/`，右上角显示本人头像+用户名，exit 0，截图 `verify_state.png`
- [x] 登录与校验全程**未触发滑块 / 安全验证 / 环境异常**
- [x] 桌面可见启动器 `run-login.bat` 验证可在用户桌面弹出浏览器（解决后台 GUI 不可见问题）
- [x] 所有命令带超时 / 自动关闭浏览器，无无限挂起
- [x] 敏感文件入库前双验证：`git check-ignore` + `git add -n` 确认 `profiles/`、`state/`、`verify_state.png` 均不入库
- [x] 未改动主应用任何文件（spike 完全隔离）

### 11.2 遗留问题（下轮继续）
- [ ] **【首要】干净匿名 profile 首次扫码、强信号 `wt2` 当场"从无到有"检测**：本轮是 profile 复用自动登录（走兜底信号），强信号分支代码已就绪但未在可见窗口完整复演。下轮需删除 `profiles/boss` 后在可见窗口真人扫一次，确认强信号当轮命中。
- [ ] **登录态实际存活时长**：T0=2026-10-19 17:38 已记录，按第 9 节在 1 小时/1 天/3 天/7 天多时点跑 verify-state。
- [ ] **持久化 user_data_dir 与 storage_state 两条路线哪条更稳**：storage_state 单次只读已验证；生产并发投递仍建议以持久化 profile 为唯一真相（避免 `__zp_stoken__` 双客户端并发触发 code 37，见调研 4.4），落地时需压测对比。
- [ ] **风控在不同账号 / IP / 频率下的表现**：本轮未触发不代表恒安全；遇到滑块/验证按红线**不绕过、只记录、转人工**。
- [ ] 其余三平台（51job / 智联 / 猎聘）登录与判定信号仍为公开资料，需各自实测（见第 12 节）。

---

## 12. 四平台登录调研整合

> 本节整合自同目录调研文件 `platforms-research.md`（调研日期 2026-10-19）。每平台列出：登录页 URL、扫码形式、登录成功判定信号/cookie 名、风控特点、需实测确认项。标注「需实测确认」者为公开资料无法确证、必须真人登录时观察的项。

### 12.1 四平台对照总表

| 维度 | Boss 直聘 zhipin | 前程无忧 51job | 智联招聘 zhaopin | 猎聘 liepin |
|---|---|---|---|---|
| **登录页 URL** | `https://www.zhipin.com/web/user/?ka=header-login`（已实测落地） | `https://login.51job.com/login.php?lang=c&from_domain=51job_web` | `https://passport.zhaopin.com/login` | `https://www.liepin.com/login` |
| **扫码形式** | **Boss 直聘 APP** 扫码（登录页「APP扫码登录」标签，已实测见二维码） | 求职者侧仅见手机/密码 tab，**扫码入口需实测确认**；企业侧 `eh.51job.com` 支持微信+APP扫码 | **微信扫码**（关注「智联校园招聘」公众号）；主站是否同微信扫码需实测 | **微信扫码**，首次扫码需绑手机号（`lpt.liepin.com/login/wx-bind`） |
| **成功判定信号 / cookie 名** | 核心 cookie **`wt2`** 存在=已登录；**`__zp_stoken__`**=页面 JS 维护风控 token；辅助 `wbg`、`zp_at` | **无公开 cookie 清单，需实测**；建议基线差分（先抓未登录基线 cookie 再对比） | 真正登录态 cookie 仅 **`at`（access token）+ `rt`（refresh token）**；**陷阱：未登录就有一堆 WAF cookie**（`Hm_*`/`sts_*`/`x-zp-client-id`/`sensorsdata*`/`ZP_OLD_FLAG`），必须基线差分判定 | 官方 MCP 授权页 `www.liepin.com/mcp/auth` 可取 **`x-user-token`** 请求头；浏览器内 web cookie 名**需实测** |
| **判定方法（可直接照搬）** | `wt2` 新出现（不在 baseline）且 URL 离开登录路由（本 spike 已实现，见 7.2） | 待实测后定，预计同基线差分 | **基线差分**：打开登录页先存 baseline cookie 集合，轮询命中 `at`/`rt` 且不在 baseline 才算真登录 | 待实测；web cookie 名未知 |
| **风控特点** | 四平台最重：`__zp_stoken__` 双客户端并发触发 code 37 环境锁；建议请求间隔 5–10s；有滑块/安全页 | 公开资料显示反爬弱于 Boss | 有滑块（带行为检测，CV 难过，须人过一次+profile 持久化免登）；Vue 事件委托合成 click 可能被吞 | 核心投递链路偏 IM（聊天气泡），纯 HTTP 自动化空间小 |
| **登录态有效期** | `wt2` 据 boss-agent-cli 经验可跨天复用，**具体天数需实测**；`__zp_stoken__` 易逝、页面自动轮换；失效返回 `AUTH_EXPIRED`/code 37 | 需实测 | at 短期 / rt 可刷新（双 token 结构），**具体时长需实测** | 需实测 |

### 12.2 来源链接（按调研文件引用）
- boss-agent-cli 诊断/登录态分层判定（wt2 / __zp_stoken__ / wbg / zp_at）：https://raw.githubusercontent.com/can4hou6joeng4/boss-agent-cli/master/docs/troubleshooting.md ；仓库 https://github.com/can4hou6joeng4/boss-agent-cli ；PyPI https://pypi.org/project/boss-agent-cli/
- patchright PyPI：https://pypi.org/project/patchright/ ；驱动仓库 https://github.com/Kaliiiiiiiiii-Vinyzu/patchright ；storage_state 机制同 Playwright 文档 https://playwright.dev/docs/auth
- 智联 at/rt cookie 与反爬实战（掘金，2026-06）：https://juejin.cn/post/7651998644058177542
- 智联微信扫码实证：https://passport.zhaopin.com/additional?appID=8b25de552a844b6c8493333ce98b9caf&redirectURL=...
- 猎聘微信扫码实证：https://wow.liepin.com/t1012621/01ab459c.html ；首次绑手机 https://lpt.liepin.com/login/wx-bind ；官方 MCP token https://www.liepin.com/mcp/auth
- 51job 登录页：https://login.51job.com/login.php ；企业侧扫码 https://eh.51job.com/Navigate.aspx
- Boss 桌面端扫码 FAQ：https://www.zhipin.com/desktop/faq/

### 12.3 四平台「需实测确认」项汇总（整合自调研第 5 节）
- [x] **Boss**：`wt2` 是否在匿名登录页预种——**已实测：匿名 baseline 不含 `wt2`，登录后才出现**；`?ka=header-login` 落地正常（见 7.3）。
- [ ] **Boss**：`wt2` 具体有效期天数（T0=2026-10-19 17:38 已记录，多时点观测中）。
- [ ] **51job**：求职者侧登录页是否有扫码入口；登录态 cookie 名清单（完全无公开资料，需抓包/基线差分实测）；有效期。
- [ ] **智联**：主站扫码是否同为微信扫码（仅子站实证）；`at`/`rt` 实际有效期。
- [ ] **猎聘**：浏览器内 web cookie 登录态名（仅有官方 MCP 的 `x-user-token` 形态）；web 登录态有效期。
- [ ] **共性**：各平台多账号/设备限制的具体表现；patchright 对国内招聘平台 WAF 的实际通过率（官方只背书国际指纹检测，国内平台无背书，且 issue 显示 Kasada 已能检测 patchright）。

> 说明：Boss 的 `wt2`/`__zp_stoken__` 已经本项目真人扫码实测确认（见 7.3，与开源项目 boss-agent-cli 资料一致）；其余三平台的成功判定 cookie 名大多仍缺失，v2.0 落地时统一采用「登录前 baseline cookie 差分」的通用判定框架（见 4.5 调研建议的 `detect_login_success(baseline_diff)`）。

---

## 13. 给 v2.0 正式登录中心的设计建议

1. **底层用 patchright + 独立 chromium**，不要用系统 Chrome（channel），profile 隔离、指纹干净。
2. **登录态双轨制**：优先 `storage_state` 加密文件（可移植、可备份、可在无头下复用）；以持久化 user_data_dir 作为兜底/兜底恢复。
3. **扫码登录交互流**：后端拉起可见浏览器 → 前端轮询后端"当前是否已登录" → 真人手机扫码 → 后端检测到成功并加密落盘 → 关浏览器。整个过程对用户只暴露"请用 App 扫码"。
4. **登录态健康检查子命令**固化为服务端定时任务，临期/失效自动通知重新扫码。
5. **绝不自动化绕过风控**：遇到滑块/验证码/二次校验就停下，转人工，记录日志。
6. **密钥管理**：state 文件加密密钥走主应用现有密钥体系，不硬编码、不入库。
