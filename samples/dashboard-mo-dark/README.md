# Get Jobs Auto · 数据看板 Dashboard 样板（mo-dark 深色主题）

Get Jobs Auto「数据看板」的纯静态样板：零框架、零构建、离线可开。业务场景为本地自动求职工具
（Boss直聘 / 51job / 智联 / 猎聘 四平台，扫码登录 + 自动投递 + 职位池 + 消息沟通），
所有数值为贴合业务的示例数据。

## 如何打开

直接双击 `index.html`（任意现代浏览器，无本地服务器依赖）。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `index.html` | 完整数据看板（顶栏 / 侧栏 / KPI / 内联 SVG 图表 / 明细表 / 登录状态） |
| `vendor/daisyui.css` | daisyUI 5.7.50 预编译 CSS（自 moh-ui 站点 vendor 本地化） |
| `vendor/utilities-patch.css` | moh-ui 工具类补丁层（纯 CSS 补 grid/flex/gap 等常用类） |
| `tokens.css` | mo-dark 主题变量覆盖层（`[data-theme="mo-dark"]`） |
| `screenshots/qa-desktop.png` | 1280×800 实测截图 |
| `screenshots/qa-mobile.png` | 390×844 实测截图 |
| `screenshots/qa_shot.py` | patchright QA 脚本（双视口截图 + console/404 检查） |

引用顺序：`daisyui.css` → `utilities-patch.css` → `tokens.css`，`<html data-theme="mo-dark">`。
不引任何外网 CDN，不使用图表库 / 照片 / emoji 图标。

## 结构要点

- **顶栏**：页面标题 + 时间范围分段控件（今天 / 7天(默认) / 30天 / 自定义）+「更新于 10:32」+ 通知铃铛（badge 计数 3，原生 popover 浮层）。
- **侧栏 220px**：品牌闪电 logo +「Get Jobs Auto / 自动化求职」；菜单 6 项（数据看板选中态 / 职位池 / 投递任务 / 消息沟通 / 登录中心 / 设置），单色 SVG 图标。
- **KPI ×4**：今日投递数 23、近30天累计投递 1,286、简历被查看率 38.5%、新沟通与面试邀约 9；等宽数字，正绿负红，每卡带 12px 口径说明。
- **图表区**：近 30 天投递趋势（内联 SVG 折线，2px 主色线、网格 8% 透明、面积 12% 透明、末端空心圆点、Y 轴从 0 起）；投递状态分布（primary/secondary/accent/neutral 四段进度条）；四平台投递占比（横向条形，0 起）。
- **明细表**：最近投递记录 8 行，状态用 badge-soft 软徽章（成功绿 / 处理中琥珀 / 中性灰），窄屏 `overflow-x` 横滑。
- **登录中心小卡**：四平台登录态状态点，智联过期给「扫码重连」次按钮，不喧宾夺主。
- **自定义时间范围**：原生 `<dialog>` + `showModal()`，Esc 关闭、焦点自动回触发按钮。
- **窄屏 ≤900px**：侧栏退化为顶部横向换行菜单、图表双列变单列、触控热区补到 44px。

## 35 项自检结果

**通过项 35 / 35，未过项 0。**

- A 基础（1–3）：字号阶 12/13/14/20/26 共 5 级；字重 400/600/700 共 3 个；KPI、数字列、图例、百分比全部 `tabular-nums`。
- B 表格（4–8）：窄屏表内横滑、页面不溢出；状态列 nowrap；时间/数字列右对齐、文本左对齐；仅行分隔线无斑马纹；折线 JS 含空态分支（数据为空时渲染「暂无数据」）。
- C 间距对齐（9–12）：8px 网格（4/8/12/16/24）；控件高 32px、同组 8px；dialog 表单单列对齐；卡片内边距 16px、内容边距统一。
- D 颜色（13–16）：正文近白 on 近黑，远高于 4.5:1；自定义样式全部走 `var(--color-*)`，无硬编码色值；主色只给品牌/选中/主按钮；无高饱和撞色。
- E 交互键盘（17–20）：全局 `:focus-visible` 2px 主色描边；无自定义装饰动画；Tab 焦点顺序与视觉顺序一致。
- F 弹层（21–25）：自定义范围用原生 dialog、通知用 popover API，焦点陷阱 / Esc / 焦点归还 / aria-labelledby / aria-expanded 均由原生行为支撑并已标注。
- G 禁则（26–30）：无渐变背景、无阴影堆叠（`--depth:1`）、无花哨 CTA、无 emoji 图标（▲▼ 为字符符号）；一屏区块 9 个（4 KPI + 3 图表 + 表格 + 登录卡）≤10。
- H 触控移动（31–33）：≤900px 下菜单/分段按钮/铃铛/主按钮热区 ≥44px；390px 实测 scrollWidth=390 无横向溢出；无 hover 独占信息。
- I 技术正确性（34–35）：patchright 双视口实测 console 无报错、无 404；1280 与 390 双视口布局无破损。

### 修复记录（共 1 轮迭代）

1. **移动端表格徽章竖排挤压**：状态列文字被挤成竖排 → 表格加 `min-width: 620px`、状态列 `white-space: nowrap`，窄屏改为表内横滑（页面 scrollWidth 仍等于视口宽）。
2. **中性灰徽章对比度不足**：daisyUI soft 徽章文字直接取纯色（neutral 26% 深灰），深底上不可读 → 在样式表覆盖 `.badge-soft.badge-neutral`：文字改用 `--color-neutral-content` 亮灰、背景 `color-mix(neutral-content 16%)`，保持中性灰语义且对比度达标。

复跑 QA：双视口无溢出、console 无报错、无 404，达到交付标准。

## 后续接入 React + Vite 前端

1. 安装依赖：`npm i daisyui`，在 `tailwind.config.js` 的 `plugins` 中引入 `require('daisyui')`。
2. 主题挂载：把 `tokens.css` 中的 `[data-theme="mo-dark"]` 变量块直接放进 daisyUI 配置的自定义主题
   （`daisyui: { themes: [{ 'mo-dark': { ... } }] }`），或保留 `tokens.css` 文件在入口 import；在根节点 `<html data-theme="mo-dark">` 切换主题。
3. 组件迁移：本样板的 class 结构（`stats` / `table` / `menu` / `badge` / `status` / `modal` / `progress`）
   可直接搬到 React JSX；侧栏、KPI、折线图拆成 `<SideNav />` `<KpiCard />` `<TrendChart />` 组件，
   折线 SVG 生成逻辑原样保留（vanilla JS，无图表库依赖）即可。
4. 弹层：`<dialog showModal>` 在 React 中用 `ref` + `showModal()` 调用；popover 用原生 `popovertarget` 属性，无需自写焦点陷阱。
5. 接真实数据：把 30 天投递数组、KPI、表格行替换为后端 API 返回；空态分支（JS 中 `if (!data.length)`）已预留。
