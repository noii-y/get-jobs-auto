# Get Jobs Auto

> 自动化求职投递工具，支持 Boss直聘 / 51job / 智联招聘 / 猎聘 四平台串行投递，真实浏览器接管，实时监控，无人值守。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react" alt="React 18">
  <img src="https://img.shields.io/badge/DrissionPage-4.1-orange" alt="DrissionPage">
  <img src="https://img.shields.io/badge/平台-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platforms">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

---

## 这是什么？

求职季海投职位是一件枯燥且耗时的事情：打开每个招聘网站、重复搜索、逐个点击、复制粘贴打招呼语……每天可能要花上一两个小时。

**Get Jobs Auto** 把这个过程完全自动化了。它接管你电脑上的 Chrome 浏览器，像真人一样搜索职位、筛选条件、打开详情、点击投递，同时在 Web 界面上实时展示进度和日志。你只需要登录一次招聘网站，之后每天喝杯咖啡的时间就能完成投递。

## 为什么选它？

| 特性 | 说明 |
|------|------|
| **真实浏览器** | 基于 DrissionPage 接管你日常使用的 Chrome，而非独立无头浏览器，反爬特征极低 |
| **四平台串行** | Boss直聘 → 51job → 智联 → 猎聘，一键启动，自动切换，互不干扰 |
| **实时监控** | SSE 实时推送日志和进度，每个平台的当前页码、职位、公司、操作一目了然 |
| **智能过滤** | 公司黑名单 + 21 个风险关键词背调（培训贷、押金、外包等），自动跳过不靠谱的公司 |
| **失败重试** | 单职位偶发失败自动刷新重试，平台启动失败自动重试，不遗漏每一个机会 |
| **暂停/继续** | 随时暂停某个平台，处理完事情后继续，不影响其他平台 |
| **AI 打招呼** | 支持 OpenAI 兼容接口，根据职位描述生成个性化问候语 |
| **无人值守** | 内置定时任务，每天固定时间自动投递；支持企业微信通知 |
| **数据本地** | 所有数据存储在本地 SQLite，不上传任何服务器，账号安全有保障 |
| **跨平台** | 支持 Windows / macOS / Linux，一键启动脚本自动检测环境 |

## 快速开始

### 环境要求

- **Python 3.12**（必须是 3.12，3.13 部分依赖不兼容）
- **Google Chrome** 或 **Microsoft Edge** 浏览器
- Node.js 18+（仅前端开发需要，普通使用不需要）

### 一键启动

**Windows：**

下载本项目后，双击项目根目录的 `start.bat`。

**macOS / Linux：**

```bash
chmod +x start.sh
./start.sh
```

脚本会自动检测 Python 3.12、安装依赖、检测浏览器，启动后自动打开管理页面（http://127.0.0.1:8888）。

### 手动启动

```bash
# 1. 安装后端依赖
cd backend
pip install -r requirements.txt

# 2. 启动服务
python run.py

# 3. 浏览器访问
# http://127.0.0.1:8888
```

首次启动时，系统会自动打开一个独立的 Chrome 窗口。在其中登录各招聘平台后，回到管理页面即可开始投递。登录态会自动保存，下次无需重复登录。

> **想用自己日常的 Chrome？** 可以用调试模式启动 Chrome（保留你已有的登录态）：
> - Windows：双击 `start-chrome.bat`
> - macOS：`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222`
> - Linux：`google-chrome --remote-debugging-port=9222`

详细使用说明见 [Wiki](../../wiki) 或下方的[使用指南](#使用指南)。

## 系统架构

```
┌──────────────────────────────────────────────┐
│            浏览器 (Chrome / Edge)              │
│         端口 9222 调试模式 或 自动启动          │
└───────────────────┬──────────────────────────┘
                    │ CDP 协议
┌───────────────────▼──────────────────────────┐
│          后端服务 (FastAPI :8888)              │
│  API 层 │ 任务调度 │ 批量管理 │ 平台 Runner    │
│  SSE 实时推送 │ SQLite 本地存储 │ AI/通知服务   │
└───────────────────┬──────────────────────────┘
                    │ HTTP / SSE
┌───────────────────▼──────────────────────────┐
│         前端 SPA (React + TypeScript)          │
│  单平台投递 / 全平台一键投递 / 历史记录 /       │
│  投递结果 / 定时任务 / 黑名单 / 系统设置        │
└──────────────────────────────────────────────┘
```

### 工作流程

1. 用户在 Web 界面配置关键词、城市、页数等参数
2. 后端通过 DrissionPage 连接 Chrome，自动搜索职位列表
3. 逐个打开职位详情，执行打招呼/投递操作
4. 每个职位的结果（成功/失败/跳过）实时推送到前端并保存到数据库
5. 全平台模式下，一个平台完成后自动切换到下一个
6. 所有平台完成后，汇总展示投递统计

## 使用指南

### 全平台一键投递

1. 进入「全平台一键投递」页面
2. 勾选目标平台（支持全选/全不选）
3. 输入统一关键词、城市、最大页数
4. 点击「一键投递」
5. 实时查看各平台状态，可单独暂停/继续/停止
6. 完成后查看投递结果汇总

### 单平台投递

适合需要精细控制单个平台的场景，支持多平台并行投递。

### 定时任务

配置每天固定时间自动投递，支持选择星期、立即执行、启用/禁用。

### 公司背调

投递前自动检测公司名称和职位描述中的风险关键词：

- **高风险**：培训贷、培训费、交钱、贷款、押金、轻松赚钱
- **中风险**：保证金、分期、无责底薪、高薪诚聘、月入过万、无需经验
- **低风险**：外包、劳务派遣、金融信息服务、投资管理等

可自定义添加关键词。高风险公司自动跳过。

### 投递记录

支持按平台、状态筛选，导出 CSV / Excel，包含成功率、平台分布、投递趋势等统计图表。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + Uvicorn |
| 浏览器自动化 | DrissionPage（接管真实 Chrome，CDP 协议） |
| 数据库 | SQLite + SQLAlchemy 2.0 |
| 定时任务 | APScheduler |
| 实时推送 | SSE（Server-Sent Events） |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 数据导出 | openpyxl（Excel） |

## 项目结构

```
get-jobs-auto/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由
│   │   ├── core/             # 浏览器管理、调度器、批量管理、SSE
│   │   ├── platforms/        # 四平台 Runner（boss/job51/zhilian/liepin）
│   │   ├── services/         # AI、通知、背调、黑名单
│   │   ├── config.py         # 配置管理
│   │   ├── database.py       # 数据库初始化
│   │   └── main.py           # FastAPI 入口
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py                # 启动入口
├── frontend/
│   ├── src/                  # React 前端源码
│   └── dist/                 # 构建产物（后端直接托管）
├── portable/                 # Windows 便携版（运行时从 Release 下载）
├── start.bat                 # Windows 一键启动
├── start.sh                  # macOS/Linux 一键启动
├── start-chrome.bat          # Windows Chrome 调试模式
└── README.md
```

## 常见问题

**Q: 会被招聘网站封号吗？**
A: 本工具使用真实浏览器操作，反爬特征极低，但仍建议合理控制投递频率和页数，避免短时间内大量操作。

**Q: 需要一直开着电脑吗？**
A: 投递期间需要保持电脑和 Chrome 运行。可以使用定时任务功能，设置每天固定时间自动投递。

**Q: 支持哪些操作系统？**
A: Windows、macOS、Linux 均支持。Windows 还提供免安装 Python 的便携版。

**Q: 我的账号密码安全吗？**
A: 本工具不存储、不上传你的账号密码。登录态保存在本地浏览器 profile 中，所有数据仅存储在本地 SQLite 数据库。

**Q: 招聘网站改版了怎么办？**
A: 各平台的页面选择器集中在 `backend/app/platforms/` 目录下，修改对应 Runner 的选择器即可。欢迎提交 PR 适配新版本。

## 贡献

欢迎提交 Issue 和 Pull Request！

- 发现 bug 或有功能建议，请开 Issue
- 适配了新的页面改版，请提交 PR
- 提交 PR 前请确保代码能正常运行

## 致谢

- [loks666/get_jobs](https://github.com/loks666/get_jobs) — 此系统是基于get_jobs的重做，更适合无环境配置能力的小白同学，非常感谢loks666大神给予的灵感，他和他的团队做了很多了不起的项目，欢迎各位去逛一逛他的空间


## 免责声明

本工具仅供学习和个人使用，使用时请遵守各招聘平台的用户协议和相关法律法规。使用者需自行承担因使用本工具产生的一切风险和责任。作者不对任何账号封禁、数据丢失或其他损失负责。

## License

[MIT](LICENSE)

---

<p align="center">
  如果这个项目对你有帮助，请给我一个 ⭐️ Star，这是我持续维护的最大动力！
</p>