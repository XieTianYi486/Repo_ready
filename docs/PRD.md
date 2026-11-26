# RepoReady · Git 仓库接入体检 — PRD 与实施计划

> 版本：v1.0（已确认）｜日期：2026-11-26｜交付形态：本地一键启动 + GitHub 仓库
> 一句话：输入公开 GitHub / Gitee 仓库链接，自动完成接入前体检，输出可解释的接入就绪度评分、五维可视化和按优先级排序的风险清单。

---

## 1. 背景与目标

48 小时实战题要求做一个"Git 仓库接入体检"工具：用户只需粘贴公开仓库链接，工具自动识别 README、依赖清单、启动脚本、Windows 专用脚本、硬编码路径、密钥与敏感信息，并给出接入就绪度评分和主要风险清单。加分项是结合 AI 给出评分或接入建议。

**产品目标**
1. 核心链路可稳定跑通：URL → 安全拉取快照 → 六类检测 → 确定性评分 → 可视化报告。
2. 评分**可解释、可复现**：每个维度有规则、证据和扣分原因；AI 不参与主评分。
3. 演示效果完整：深色工程仪表盘、评分环、五维条形仪表、可筛选风险表、脱敏证据、JSON/Markdown 导出。
4. 工程可信：限流兜底、体积/文件数上限、路径穿越防护、绝不执行仓库代码、密钥只落脱敏结果。
5. 文档达标：README 含更新跟踪设计；AI_USAGE.md 含至少 1 条真实的"AI 答错被抓到"记录。

**非目标（明确不做）**
- 不支持私有仓库（即使 Token 可见也主动拒绝，避免把私有代码送入分析/AI）。
- 不做依赖漏洞库比对、完整 SAST、许可证合规审计。
- 不执行仓库中的任何脚本/构建命令。
- 不实现文件级增量扫描（按题意做设计说明；代码层只实现"按 commit 的报告缓存"）。
- 不做 Docker / Vercel 交付（用户已确认仅本地一键启动）。

---

## 2. 题目要求 → 产品能力映射

| 题目要求 | 产品实现 | 验收标准 |
|---|---|---|
| Web 页面输入公开仓库链接，至少 GitHub | 首页大输入框，自动识别 GitHub / Gitee；解析 `.git`、`/tree/<branch>`、SSH 形式 | 合法链接均可扫描；非法/非白名单链接给出明确中文错误 |
| README 完整度 | 存在性、长度、章节覆盖（安装/使用/配置/API/许可）、代码块、徽章、截图 | 输出 0–100 子分 + 缺失章节清单 |
| 依赖清单完整度 | 识别 15+ 生态清单/锁文件，解析 package.json / pyproject / requirements；报告生态与解析错误 | 输出清单列表、锁文件状态、子分与风险 |
| 启动脚本完整度 | package.json scripts、Makefile、Dockerfile/Compose、Procfile、README 运行命令 | 输出启动路径清单、推断的一键启动命令、子分 |
| Windows 专用脚本 | 扫描 `.bat/.cmd/.ps1/.vbs`，识别用途、是否被 README 引用、危险模式 | 输出清单 + 跨平台风险；计入跨平台维度 |
| 硬编码路径 | Windows 盘符、`/Users/`、`/home/`、UNC、`/opt` 等部署路径；区分代码/配置/文档 | 输出文件、行号、片段、按规则分组；URL 等误报被排除 |
| 密钥与敏感信息 | `sk-`、`AKID`、`LTAI`、AKIA、`Bearer`、私钥、`.env` 入库、高频 Token、泛化凭据+熵 | 高危项一条风险一条证据；所有密钥**脱敏**；已知假密钥 fixture 不误报 |
| 可视化 | 评分环、五维条形仪表、维度卡、严重度 KPI、风险表、Windows/路径/密钥面板 | 桌面与窄屏可用；筛选、展开、跳转源码行；数值有文本等价视图 |
| 接入就绪度评分 | 确定性 100 分制、等级 A–F、封顶规则、公式可展开 | 同一快照重复扫描分数完全一致；规则版本可追踪 |
| 主要风险清单 | 严重度 critical/high/medium/low，分类、文件行号、建议、规则 ID、排序 | 可按严重度/分类筛选、搜索；Top 风险置顶 |
| 加分项 AI | Anthropic + OpenAI 兼容双适配器；AI 参考分（独立标注）+ 接入建议；无 Key 自动降级 | AI 失败不影响报告；AI 结果经 Pydantic 校验；请求不含明文密钥/源码全文 |
| 更新跟踪（设计） | 轻量实现 commit 缓存 + 检查更新；README 写生产级增量方案 | README 覆盖四问：发现更新/避免全量/commit 标注/限流兜底 |
| AI_USAGE.md | 工具清单、验证方法、至少 1 条真实 AI 错误记录 | 记录可复现、含原因与修正 |

---

## 3. 已确认决策

| 项 | 决策 |
|---|---|
| 技术栈 | 后端 Python 3.12 + FastAPI + Pydantic v2 + httpx（同步客户端，扫描跑在受限线程池）；前端 React + TypeScript + Vite + Tailwind CSS |
| 平台 | GitHub + Gitee（适配器接口预留扩展） |
| AI | Anthropic Claude SDK + OpenAI 兼容接口双适配器；可选启用，自动降级规则建议 |
| AI 参考分 | **包含**：独立标注、不影响确定性主评分 |
| UI | 深色工程仪表盘，中文界面 |
| 更新跟踪 | 轻量实现（同 commit 秒回缓存、新 commit 重扫、检查更新按钮）+ README 完整设计 |
| 交付 | 本地一键启动（`start.bat` / `start.sh`），运行时由 FastAPI 托管前端构建产物 |
| Git | 我负责 `git init`、.gitignore、分阶段 commit；用户创建 GitHub 远程仓库后推送 |
| 凭据 | 用户已有 GitHub Token / Gitee Token / AI Key，稍后写入本地 `.env`；代码必须无凭据也能跑 |
| 项目名 | **RepoReady**（英文标识）＋「Git 仓库接入体检」中文名 |
| 评分权重 | **均衡版**：README 20 / 依赖 15 / 启动 20 / 跨平台 15 / 安全 30 |
| 加分项 | **GitHub Actions CI + README 截图**（不做额外 demo 仓库与英文 README；测试 fixture 仍保留） |

---

## 4. 核心用户流程

```
首页
 ├─ 粘贴链接 → 平台识别徽章 → [开始体检]
 │    └─ 扫描页：解析链接 → 获取仓库信息 → 下载快照 → 六类检测 → 计算评分 → 生成报告
 │         ├─ 失败：中文错误卡（限流/私有/超大/网络），保留重试入口
 │         └─ 成功：报告页
 └─ 最近扫描（本地缓存列表），点击直达历史报告

报告页
 ├─ 头部：仓库信息、commit、分析时间、耗时、分支
 ├─ 评分区：总分环 + 等级/结论 + 五维条形仪表 + 严重度 KPI
 ├─ 维度卡 ×5：分数、状态、关键证据、详情锚点
 ├─ 风险清单：严重度/分类筛选 + 搜索 + 展开证据（源码行链接）
 ├─ 仓库画像：README / 依赖 / 启动 / Windows 脚本 / 硬编码路径 / 密钥（脱敏）
 ├─ AI 建议：自动生成（若启用）/ 重试 / 未配置引导；独立"AI 参考分"
 ├─ 更新状态：检查更新 → 有新提交则提示"基于旧 commit"并可重扫
 └─ 操作：复制分享链接、导出 JSON、导出 Markdown、重新体检
```

---

## 5. 功能需求

### P0（必须跑通）

| ID | 功能 | 说明 |
|---|---|---|
| F1 | 仓库链接解析 | GitHub/Gitee、HTTPS/SSH、`.git`、`/tree/<branch>`、trailing slash；严格域名白名单 |
| F2 | 安全快照拉取 | 平台 API 取元数据 + HEAD；按 commit SHA 下载归档；体积/文件数/超时限制；路径穿越防护；临时目录清理 |
| F3 | README 分析 | 存在性、长度、章节、代码块、徽章/截图，输出缺失项 |
| F4 | 依赖分析 | 15+ 生态清单；解析核心清单；锁文件；多种清单聚合 |
| F5 | 启动路径分析 | 包脚本、Makefile、Docker、Procfile、README 命令；推断建议启动命令 |
| F6 | Windows 脚本盘点 | 扩展名、用途、README 引用、危险模式；跨平台风险 |
| F7 | 硬编码路径扫描 | 6 类规则 + URL/占位符过滤；按文件/规则聚合；源码行链接 |
| F8 | 密钥扫描 | 20+ 规则 + 泛化熵检测 + 占位符白名单；`.env` 入库、`.gitignore` 检查；全量脱敏 |
| F9 | 确定性评分 | 五维加权、等级、封顶；公式与扣分理由可见 |
| F10 | 风险清单 | 严重度/分类/建议/规则 ID/证据；排序与筛选 |
| F11 | 可视化报告 | 评分环、五维横向条形仪表、维度卡、严重度 KPI 瓦片、风险表、各检测面板；深色主题 |
| F12 | 报告缓存与更新 | 同 repo+commit 命中缓存；规则版本失效；检查更新接口；前后 commit 标注 |
| F13 | 报告导出 | JSON 与 Markdown（含脱敏证据、评分、风险 Top N） |

### P1（加分与体验）

| ID | 功能 | 说明 |
|---|---|---|
| F14 | AI 接入建议 | 双适配器、结构化输出、参考评分、失败降级 |
| F15 | 扫描进度 | 真实阶段轮询，展示耗时与当前步骤 |
| F16 | 最近扫描 | 本地索引，首页快速回访 |
| F17 | 规则版建议 | 无论 AI 是否启用，都基于风险生成"下一步动作" |
| F18 | 仓库画像 | 语言分布、CI、测试、License、活跃度（信息展示，不额外加权） |

### P2（已选加分项，时间允许时完成）

- **GitHub Actions CI**：push/PR 自动跑 pytest + 前端 `tsc`/build（已选定）。
- **README 截图**：首页与报告页真实截图（已选定）。
- AI_USAGE 里的提示词摘录与截图。
- `ruff` + `eslint` 基础质量门禁（不阻塞交付）。

---

## 6. 检测规则与评分

### 6.1 快照拉取

**平台适配器接口**：`parse_url`、`fetch_meta`、`fetch_head`、`archive_url`、`blob_url`。

**GitHub**
1. `GET https://api.github.com/repos/{owner}/{repo}`（可选 `Authorization: Bearer $GITHUB_TOKEN`）→ 默认分支、私有标记、描述、stars、语言、license、pushed_at、archived、size。
2. `GET /repos/{o}/{r}/branches/{branch}`（或 `/commits/{branch}`）→ HEAD SHA、提交信息、日期。
3. 归档：`https://codeload.github.com/{o}/{r}/tar.gz/{sha}`（实测 200，不占 API 配额；根目录 `{repo}-{sha}/`）。
4. `git ls-remote` 仅作可选兜底；本机实测 GitHub 连接可能被重置，不作为主链路。

**Gitee**
1. `GET https://gitee.com/api/v5/repos/{o}/{r}`（可选 `?access_token=$GITEE_TOKEN`）→ 默认分支、private、描述、stars、language、license（字符串）、pushed_at。
2. `GET /repos/{o}/{r}/branches/{branch}` → HEAD SHA、提交信息、日期。
3. 归档：`https://gitee.com/{o}/{r}/repository/archive/{sha}.zip`（实测 GET 302→`blazearchive` 签名地址后 200；**禁止 HEAD**，会 405；根目录 `{repo}-{sha}/`）。
4. 兜底：`git clone --depth 1 --single-branch --branch {branch}`（Gitee 实测可用），再取 `rev-parse HEAD`；仅在归档失败时启用，仍需体积/时间上限。

**统一防护**
- 仅允许 host：`github.com / www.github.com / gitee.com / www.gitee.com`；API 与归档 host 固定；重定向终点必须仍在白名单。
- 拒绝 private 仓库（metadata.private=true）。
- 压缩包 ≤ 50MB；解压总量 ≤ 200MB；文件数 ≤ 5000；单文件扫描 ≤ 512KB；总文本扫描 ≤ 20MB；扫描墙钟 ≤ 180s。
- 解压仅接受普通文件：拒绝绝对路径、`..`、反斜杠路径、符号链接、设备文件；统一 POSIX 路径；解压到系统临时目录，`finally` 清理。
- 跳过 `.git node_modules vendor dist build out target .venv venv __pycache__ .tox .next coverage` 等目录；二进制按扩展名 + NUL 字节判断。
- 错误映射：INVALID_URL / UNSUPPORTED_PLATFORM / REPO_NOT_FOUND / PRIVATE_REPO / RATE_LIMITED / ARCHIVE_TOO_LARGE / TOO_MANY_FILES / DOWNLOAD_FAILED / EXTRACT_FAILED / SCAN_TIMEOUT。
- HTTP 重试：429/5xx/网络错误最多 2 次指数退避 + 抖动；尊重 `Retry-After` / `X-RateLimit-Reset`；归档 GET 2 次。

### 6.2 README 完整度（权重 20）

**信号**
- 根目录 `README`（大小写不敏感，`.md/.markdown/.rst/.txt` 或无扩展名）。
- 长度 ≥ 500 字符；标题层级数量；代码块（``` 与缩进）；图片/徽章。
- 章节关键词（中英）：安装/Install/Setup/Quick Start/快速开始；使用/Usage/Run/运行/启动；配置/Config/Environment/环境变量；API/Architecture/架构/目录结构；License/许可。
- README 语言（中/英）仅用于展示。

**子分（0–100）**
| 项 | 分值 |
|---|---|
| 存在 README | 25 |
| 长度 ≥ 500 字符 | 10 |
| 五个关键章节（各 7 分） | 35 |
| 至少 1 个代码块 | 15 |
| 同时含安装 + 使用章节 | 15 |
| 缺失 README 直接 0 分 | — |

**风险**
- 缺少 README：high（接入者无法快速理解/运行）。
- 缺安装或使用章节：medium。
- 缺配置说明且项目引用环境变量：medium（与启动维度联动）。
- README 过短/无代码示例：low。

**误报控制**：README 是文档，不参与硬编码路径的 high 判定（降为 low）；示例密钥按占位符规则排除。

### 6.3 依赖清单（权重 15）

**识别清单**
- JS/TS：`package.json`、`package-lock.json`、`yarn.lock`、`pnpm-lock.yaml`、`bun.lockb`
- Python：`requirements*.txt`、`pyproject.toml`、`Pipfile`、`setup.py`、`setup.cfg`、`poetry.lock`、`uv.lock`
- Go：`go.mod`、`go.sum`；Rust：`Cargo.toml`、`Cargo.lock`
- Java：`pom.xml`、`build.gradle(.kts)`、`gradle-wrapper.properties`
- PHP：`composer.json`、`composer.lock`；Ruby：`Gemfile`、`Gemfile.lock`
- .NET：`*.csproj`、`*.sln`、`packages.lock.json`；Dart：`pubspec.yaml`；Swift：`Package.swift`；Conda：`environment.yml`

**子分**
| 项 | 分值 |
|---|---|
| 至少 1 个依赖清单 | 50 |
| 至少 1 个锁文件 | 20 |
| 清单可解析且依赖数 > 0（package.json/pyproject 等） | 20 |
| 多生态或 README 有安装说明 | 10 |

**风险**：`package.json` 解析失败（high）；清单存在但无锁文件（low，可复现性）；有代码但无任何清单（high）；声明依赖但无安装文档（medium）。

**误报控制**：vendored / 示例目录中的清单只展示不计主分；monorepo 聚合根清单优先，子包清单列明细。

### 6.4 启动脚本（权重 20）

**信号**
- `package.json.scripts`：`start/dev/serve/preview/build` 及其真实命令。
- `Makefile`：`run/start/dev/serve/up` 目标。
- `Dockerfile` 的 CMD/ENTRYPOINT；`docker-compose.y*ml` / `compose.y*ml` services。
- `Procfile` 的 web 进程。
- README 命令提取：`npm start|run dev`、`yarn|pnpm dev`、`python *.py`、`uvicorn|gunicorn`、`go run`、`cargo run`、`mvn spring-boot:run`、`gradlew bootRun`、`dotnet run`、`php artisan serve`、`bundle exec rails`、`docker compose up`。
- 环境变量引用（`process.env.X`、`os.environ[...]`、`os.getenv`）→ 与 `.env.example` / README 配置章节比对。

**子分**
| 项 | 分值 |
|---|---|
| 明确的启动脚本（start/dev/serve/run） | 40 |
| README 有可执行的启动命令 | 25 |
| 构建步骤明确（build 脚本或文档） | 15 |
| Docker/Compose/Procfile 任一 | 10 |
| 有快速开始章节 | 10 |

**风险**：代码项目无任何启动方式（high，接入阻断）；README 与脚本不一致（medium）；引用环境变量但无 `.env.example` 且无配置文档（medium）；只有构建脚本没有启动脚本（medium）。

**输出**：`suggested_start_command`（优先 dev/start → compose → make → README 命令），UI 可一键复制。

### 6.5 Windows 专用脚本（权重 15，跨平台维度）

**盘点**
- 扩展名大小写不敏感：`.bat/.cmd/.ps1/.vbs`。
- 用途启发式（文件名 + 前 80 行）：setup/install、start/run、build、test、deploy、db、unknown。
- 是否在 README 中被提及；是否在 CI 中被调用。
- 危险模式（只标 medium/low，不夸大）：
  - `powershell.*-ExecutionPolicy\s+Bypass`
  - `-EncodedCommand`
  - `Invoke-WebRequest|iwr ... | iex` / `curl ... | powershell`
  - `Start-Process ... -Verb RunAs`
  - `.vbs` 使用 `WScript.Shell`（info/low）
- 关联硬编码路径/密钥发现（同一行跳转到对应风险）。

**跨平台子分（与硬编码路径共享 100 分）**
| 项 | 扣分 |
|---|---|
| 每个 Windows-only 脚本 | −3（最多 −15） |
| 只有 Windows 启动脚本、无跨平台替代 | −15 |
| 危险脚本模式 | 每项 −10（最多 −20） |
| 无 Windows 脚本 | 不扣分 |

**风险**：仅 Windows 启动且无跨平台方案（medium）；PowerShell 绕过执行策略/下载执行（medium）；脚本含硬编码路径（合并到路径风险）；一般脚本清单仅展示（info）。

### 6.6 硬编码路径（权重 15，跨平台维度）

**规则**
| 规则 ID | 模式 | 默认严重度 |
|---|---|---|
| PATH-WIN-DRIVE | `C:\...`、`C:/...`、JSON 转义 `C:\\...` | high（源码/配置/脚本/CI），low（文档/测试夹具） |
| PATH-WIN-UNC | `\\server\share`、`\\\\server\\share` | high |
| PATH-MAC-HOME | `/Users/<name>/...` | high（源码），low（文档） |
| PATH-LINUX-HOME | `/home/<name>/...` | high（源码），low（文档） |
| PATH-ROOT-MNT | `/root/...`、`/mnt/[c-z]/...` | medium |
| PATH-DEPLOY-ABS | `/opt/...`、`/var/www/...`、`/usr/local/...`、`/srv/...` | low（仅配置/脚本） |

**误报控制**
- 盘符正则使用负向后行 `(?<![\w])[A-Za-z]:[\\/]`，排除 `https://` 中的 `s:/` 与 `s:\`。
- URL 上下文检测：同一行匹配点之前出现 `://` 且不是 `file://` → 跳过；README 代码块内仍可 low。
- 占位符过滤：`<...>`、`${...}`、`%VAR%`、`$HOME`、`~`、`yourname/username/user/example`。
- 跳过 vendored、lockfile、minified、二进制。
- 文档/测试夹具降级为 low；同文件同规则聚合，避免刷屏。
- 单条风险最多保留 100 个证据；分数扣减按严重度封顶。

**子分**：100 起扣；high −20/项（最多 −60）；medium −8/项（最多 −24）；low −3/项（最多 −12）；info −1；最低 0。

**跨平台维度合成**：`cross_platform_score = max(0, 100 − windows_penalty − path_penalty)`；`windows_penalty` 来自 6.5，`path_penalty` 来自 6.6。

### 6.7 密钥与敏感信息（权重 30）

**高置信规则（命中即 critical/high）**
| 类型 | 模式（示意） | 严重度 |
|---|---|---|
| Anthropic | `sk-ant-(api|admin)\d*-[A-Za-z0-9_-]{20,}` | critical |
| OpenAI | `sk-(proj|svcacct|admin)-[A-Za-z0-9_-]{20,}`、legacy `sk-[A-Za-z0-9]{20,}` | critical/high |
| AWS | `AKIA[0-9A-Z]{16}`、`ASIA[0-9A-Z]{16}` | critical |
| 阿里云 | `LTAI[A-Za-z0-9]{12,}` | critical |
| 腾讯云 | `AKID[A-Za-z0-9]{13,}` | critical |
| GitHub | `gh[pousr]_[A-Za-z0-9]{36,}`、`github_pat_...` | high |
| GitLab | `glpat-[A-Za-z0-9_-]{20,}` | high |
| Slack | `xox[baprs]-[A-Za-z0-9-]{10,}` | high |
| Google | `AIza[0-9A-Za-z_-]{35}` | high |
| Stripe | `sk_live_...`、`rk_live_...` | critical |
| SendGrid | `SG.xxx.xxx` | high |
| 私钥 | `-----BEGIN ... PRIVATE KEY-----` | critical |
| Bearer | `Bearer <20+ 非占位 token>` | high（源码），medium（文档） |
| JWT | `eyJ...eyJ...` | medium |
| Azure 连接串 | `AccountKey=` 长值 | critical |
| `.env` 入库 | `.env`、`.env.local`、`.env.production`（排除 `.example/.sample/.template/.dist`） | critical（含值）/high |
| 私钥文件 | `*.pem/*.key/*.p12/*.pfx/id_rsa` 且非空 | critical |
| `.npmrc` / `.pypirc` / docker config | `_authToken` / password / auth | high |
| 泛化赋值 | `api_key|secret|token|password` = 引号值，熵 ≥ 3.3 且长度 ≥ 12 | high/medium（按文件类型） |

**误报控制**
- 占位符白名单：`your`, `example`, `sample`, `demo`, `test`, `dummy`, `fake`, `placeholder`, `changeme`, `xxx`, `***`, `...`, `<...>`, `${...}`, `{{...}}`, `%VAR%`, `process.env`, `os.environ`, `null`, `true`, `false`, `none`, `password`, `123456`, `secret`, `token`, `apikey`.
- 文档/测试夹具/示例目录降一级；lockfile、minified、二进制跳过。
- 泛化赋值必须通过 Shannon 熵阈值；低熵值（`password123`、`localhost`）不算。
- Bearer 排除 `<token>`、`YOUR_TOKEN`、`${TOKEN}`、`xxx`。
- 发现密钥时：**存储与返回仅脱敏值**（前 4 后 2 或 `[REDACTED]`），完整行经过二次脱敏；日志不打印内容。
- `.gitignore` 未覆盖 `.env` → medium；`.env.example` 只展示键名与占位值。
- 每个文件每规则最多 20 条证据；汇总风险最多 30 条；去重同值。

**子分**：100 起扣；critical → 维度 0；high −35/项（最多 −70）；medium −10/项（最多 −40）；low −3；最低 0。
**总分封顶**：存在 critical → 总分 ≤ 49；存在 high → 总分 ≤ 69；报告顶部解释封顶原因。

**规则版本**：`RULES_VERSION = 2026.11.26.1`；规则变更需在 README/CHANGELOG 说明并失效缓存。

### 6.8 评分体系

| 维度 | 权重 | 主要依据 |
|---|---:|---|
| 文档可读性（README） | 20 | README 完整性 |
| 依赖可安装性 | 15 | 清单 + 锁文件 + 解析 |
| 启动可运行性 | 20 | 启动脚本 + 文档命令 + 容器 |
| 跨平台接入性 | 15 | Windows 脚本 + 硬编码路径 |
| 安全合规性 | 30 | 密钥/敏感信息 |

```
total = round( Σ(dimension_score × weight) / Σ(weight of applicable dimensions) )
```

- **全维度计分**：五个维度始终参与计算；无源码/清单/启动方式的项目在对应维度得 0，并在维度卡与风险清单说明原因（避免"文档仓库"被误判为可接入应用）。不做 N/A 重归一，保证公式简单、可比、可复现。
- **等级**：A ≥ 90；B 80–89；C 70–79；D 60–69；F < 60。
- **结论文案**：A「可直接接入」；B「小修后可接入」；C「需治理后接入」；D「风险较高，先整改」；F「存在阻断项，暂不建议接入」。
- **封顶**：critical 密钥 → 49；high 密钥 → 69；解释文案与命中证据。
- **可解释**：报告返回每维 `reasons[]`（加分/扣分项、命中规则、证据数量）；UI「评分方法」抽屉展示公式、权重、阈值、规则版本。
- **确定性**：无随机、无当前时间参与评分；同一快照 + 同一规则版本 = 同一分数。

### 6.9 风险模型

```ts
type Severity = "critical" | "high" | "medium" | "low" | "info";
type Category = "docs" | "dependencies" | "startup" | "platform" | "security" | "hygiene";

interface Risk {
  id: string;              // 规则 ID + 稳定 hash
  rule_id: string;
  category: Category;
  severity: Severity;
  title: string;
  description: string;
  file?: string;           // 仓库相对路径
  line?: number;
  evidence?: string;       // 已脱敏
  occurrences: number;
  recommendation: string;
  source_url?: string;     // blob@commit#Lx
}
```

- 风险排序：severity → category → 文件路径 → 行号；Top 阻断项单独高亮。
- 证据链接：GitHub `https://github.com/{o}/{r}/blob/{sha}/{path}#L{n}`；Gitee `https://gitee.com/{o}/{r}/blob/{sha}/{path}#L{n}`。
- 同一文件同一规则聚合；`occurrences` 计数；详情面板列前 20 条。

---

## 7. AI 增强方案

### 7.1 配置与选择

```env
AI_PROVIDER=auto            # auto | anthropic | openai | off
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-opus-5-5
ANTHROPIC_BASE_URL=         # 可选
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=               # 如 deepseek-chat / qwen-plus
AI_TIMEOUT_SECONDS=30
```

- `auto`：有 Anthropic Key 优先 Anthropic；否则 OpenAI 兼容；否则 disabled。
- `/api/health` 只返回布尔与模型名，不返回 Key。
- 无 Key：报告正常生成，AI 区显示"未配置 AI"与配置指引；规则建议始终可用。
- 联调 AI/提额：请用户把 GitHub / Gitee Token 与 AI Key 写进本地 `.env`（不要发到聊天或提交 git）；实现阶段先以无凭据 + mock 测试跑通，再切真实凭据验证。

### 7.2 请求与输出

- 仅发送**结构化摘要**：仓库元数据、五维分数、评分封顶原因、Top 12 风险（标题/类别/严重度/文件/行/已脱敏证据/建议）、关键信号（README 章节、清单、启动命令、Windows 脚本数、环境变量样例键名）。**不发送源码全文，不发送明文密钥**。
- 输出 JSON（Pydantic 校验）：

```json
{
  "summary": "2-4 句总体判断",
  "reference_score": 0,
  "score_reason": "为什么给出该参考分",
  "blockers": [{"title": "", "why": "", "fix": "", "severity": "high"}],
  "quick_wins": [{"action": "", "expected_effect": ""}],
  "integration_plan": [{"step": 1, "detail": ""}],
  "caveats": [""]
}
```

- `reference_score` 独立展示为「AI 参考分（不影响主评分）」；非法/越界值 clamp 或丢弃。
- AI 建议条目最多 6 条，字符串长度截断（summary 800 字，其他 300 字）。
- **不采纳 AI 对风险事实的改写**：风险清单永远来自确定性规则；AI 只解释与排序建议。
- 校验失败/超时/限流：AI 区 `status=error` + 中文提示 + 重试按钮；主报告不受影响。
- 生成时机：扫描只产出确定性报告；报告页在 AI 已启用且尚无结果时调用 `POST /api/reports/{id}/ai`，前端显示骨架屏；结果写回报告缓存，避免重复计费。AI 不阻塞扫描主链路。
- 脱敏自检：请求体序列化后再次扫描已知密钥模式；若命中则拒绝发送并记录告警。

### 7.3 Anthropic 适配器（按官方 SDK 规范）

- `pip install anthropic`，使用 `anthropic.Anthropic` 同步客户端（在受限线程池中调用）；模型默认 `claude-opus-5-5`，`output_config={"effort":"medium"}`，自适应思考；`max_tokens=3000`，超时 30s。
- 使用结构化输出 `output_config.format = json_schema` 保证 JSON；`stop_reason == "refusal"` 时先处理 `stop_details`，不读取 content。
- 按规范默认启用服务端拒绝回退：beta `server-side-fallback-2026-07-01` + `fallbacks: "default"`；若 SDK/账号不支持，捕获 400 后自动降级为普通请求并记录日志（不阻塞用户）。
- 异常分类处理：AuthenticationError / PermissionDeniedError / NotFoundError / RateLimitError / APIStatusError / APIConnectionError，映射为中文错误。
- 不在前端暴露 Key；所有 AI 调用仅服务端。

### 7.4 OpenAI 兼容适配器

- `httpx.Client` POST `{base_url}/chat/completions`，Bearer Key；`response_format={"type":"json_object"}`；若服务端不支持该参数则重试一次无 response_format。
- `temperature=0.2`；超时 30s；JSON 提取 + Pydantic 校验；兼容 DeepSeek/Qwen/OpenAI。

### 7.5 规则版建议（无 AI 兜底）

根据风险自动生成 3–6 条下一步：轮换密钥并清理历史/加 `.gitignore`、补 README 安装与启动、补 `.env.example`、替换硬编码路径为环境变量、补锁文件、提供跨平台脚本。标注「规则建议」而非 AI。

---

## 8. 页面与视觉设计

### 8.1 设计语言

- 深色工程仪表盘：背景 `#0B1220` / 卡片 `#111A2C` / 边框 `#1E2A44`；主强调青绿 `#34D399`，辅助青 `#22D3EE`，警示 amber `#F59E0B`，高危红 `#F87171`。
- 字体：系统中文栈 + `ui-monospace` 用于路径/SHA/代码；数据密度高但分区清晰。
- 组件：圆角 12–16px、细边框、轻微发光仅用于分数环；图表使用统一色板。
- **可视化规范（dataviz）**：五维数据是"比较大小"，不用雷达图；采用横向条形/仪表（单一色相、直接数值标注、4px 圆角数据端、2px 间隙），维度卡天然作为表格视图。严重度用 KPI 瓦片（图标 + 文字 + 颜色），不做仅靠颜色的编码。评分环是"单一比值对上限"，使用 hero 数字 + 环形 meter。所有图表在实现时用 `validate_palette.js` 针对深色表面实际色值验证，不靠肉眼判断。
- 动效：扫描阶段进度、分数环入场、风险展开；尊重 `prefers-reduced-motion`。
- 无障碍：严重度不只靠颜色，配文字/图标；对比度达标；键盘可操作。

### 8.2 页面

**首页 `/`**
- 顶栏：Logo「RepoReady / Git 仓库接入体检」、GitHub 链接、API 文档。
- Hero：标题 + 副标题 + 大 URL 输入框（平台图标自动识别）+「开始体检」。
- 示例仓库 chips（标注演示点）：`Plazmaz/leaky-repo`（密钥）、`ChrisTitusTech/winutil`（Windows 脚本）、`sindresorhus/got`（规范项目）、`gitee.com/y_project/RuoYi`（Gitee）。
- 能力卡 ×5 + 隐私声明（只读公开仓库、不执行代码、密钥脱敏、AI 请求只发摘要）。
- 配置状态徽章：AI 已启用（provider/model）/ 未配置；Token 已配置（布尔）。
- 最近扫描列表（缓存索引），带分数、commit、时间。

**扫描页 `/scan/:jobId`**
- 仓库信息、平台徽章、阶段步骤条（解析 → 元数据 → 下载 → 检测 → 评分 → 完成）。
- 实际进度来自后端 job；显示当前阶段与耗时；失败显示错误码 + 中文说明 + 重试/返回。
- 完成后自动跳转 `/report/:reportId`。

**报告页 `/report/:reportId`**
- 顶部：仓库名/描述/平台/stars/language、commit short SHA（复制 + 源码树链接）、分支、分析时间、耗时、缓存标记。
- 评分区：SVG 评分环（总分/等级/结论/封顶提示）、五维横向条形仪表（自绘 SVG/CSS，直接标注分数，悬停显示扣分依据）、严重度 KPI 瓦片 ×4（critical/high/medium/low，可点击滚动到风险表）。评分环与维度条都提供文本/表格等价视图（维度卡）。
- 维度卡 ×5：分数进度条、状态、2–3 条关键依据、「查看详情」。
- 风险清单：筛选（分类、严重度）、搜索、展开显示描述/证据/建议/规则 ID/源码行链接；Top 3 阻断项置顶。
- 仓库画像 Tabs：
  - README：章节检查清单、字数、代码块、缺失项。
  - 依赖：清单表（生态/路径/可解析/依赖数）、锁文件状态。
  - 启动：脚本表、文档命令、容器支持、建议启动命令（一键复制）。
  - Windows：文件表（路径/用途/README 引用/风险标记）。
  - 路径：按规则分组，文件/行/片段/严重度。
  - 密钥：仅脱敏证据、规则、建议、`.env`/`.gitignore` 状态。
- AI 区：未配置引导 / 生成中骨架 / 建议卡（总结、参考分、阻断项、快速收益、接入步骤、caveats）/ 失败重试。
- 更新条：同 commit 缓存提示；「检查更新」→ 新 commit 提示 +「基于新版本重新体检」；限流/未知时显示"无法确认，展示缓存报告"。
- 操作：复制分享链接、导出 JSON/MD、重新体检、返回首页。
- 评分方法抽屉：公式、权重、等级、封顶规则、规则版本、局限性。

### 8.3 空态/错误态
- 首页空态：示例与说明；非法 URL 即时校验。
- 扫描错误：错误码 + 建议（如"配置 GITHUB_TOKEN 提高限额，重置时间 xx:xx"）。
- 报告不存在/过期：返回首页；AI 未配置：引导。
- 窄屏：单列卡片，风险表转卡片；图表自适应。

---

## 9. 架构与技术选型

### 9.1 选型理由

- **FastAPI**：Python 文本分析生态成熟、类型化 Pydantic 模型、自动 OpenAPI 文档；单进程即可托管 API + 前端静态文件。扫描使用同步 httpx + `ThreadPoolExecutor(max_workers=2)`，比异步任务更易测试、更抗超时，进度通过内存 job 注册表轮询。
- **React + Vite + TS + Tailwind**：构建快、组件化图表/表格、深色主题实现效率高；Vite 代理开发体验好。
- **Pydantic v2**：报告/AI 输出双端校验，结构稳定。
- **依赖精简**：后端 fastapi、uvicorn、httpx、python-dotenv、anthropic；前端 react、react-dom、react-router-dom、lucide-react、tailwindcss。图表用自绘 SVG/CSS，不引入 Recharts/ECharts。测试只用 pytest + FastAPI TestClient（同步线程架构，不需要 pytest-asyncio）。

### 9.2 数据流

```
┌────────────────────┐        fetch/JSON        ┌──────────────────────────┐
│ React SPA (Vite)   │ ◄──────────────────────► │ FastAPI /api             │
│ Home/Scan/Report   │                          │  ├─ ScanManager(线程池)   │
└────────────────────┘                          │  │   ├─ URL Parser       │
                                                │  │   ├─ PlatformAdapter  │
        ┌───────────────┐                       │  │   │   ├─ GitHub       │
        │ data/reports  │ ◄── JSON 报告 ────────│  │   │   └─ Gitee        │
        │ data/index    │                       │  │   ├─ Fetcher/Extract  │
        └───────────────┘                       │  │   ├─ FileIndex        │
                                                │  │   ├─ 6 Analyzers      │
┌────────────────────┐   HTTPS（只读）           │  │   ├─ Scoring          │
│ GitHub API/codeload│ ◄────────────────────────│  │   └─ ReportStore      │
│ Gitee API/blazearch│                          │  └─ AI Service           │
└────────────────────┘                          │      ├─ Anthropic SDK    │
                                                │      └─ OpenAI-compatible│
                                                └──────────────────────────┘
```

### 9.3 运行形态

- 生产/一键启动：`start.bat`（或 `start.sh`）调用 `scripts/start.py`，由它检测 Python ≥3.11 → 创建 `.venv` → 安装依赖 → `npm install && npm run build` → 启动 `uvicorn backend.app.main:app` → 自动打开浏览器（默认 `http://127.0.0.1:8000`，端口占用时顺延）。
- FastAPI 托管 `frontend/dist`：`/assets/*` 静态资源 + SPA fallback（`/report/*` 等返回 index.html）；`/api/*` 优先级高于 fallback。
- 开发：后端 `uvicorn --reload`（8000）；前端 `npm run dev`（5173，代理 `/api` 到 8000）；CORS 仅允许 5173。

### 9.4 后端模块（详见目录结构）

- `platform/` 适配器：URL 解析、元数据、HEAD、归档 URL、blob URL。
- `fetcher.py`：下载（流式、限额）、安全解压、临时目录管理。
- `file_index.py`：遍历/过滤/文本读取/语言统计/项目画像。
- `analyzers/`：六个纯函数分析器，输入 FileIndex + Meta，输出维度结果与 findings。
- `scoring.py`：权重、封顶、等级、风险聚合排序、规则建议。
- `scan_manager.py`：`ThreadPoolExecutor(max_workers=2)` + 线程安全 job 注册表、阶段进度、同 URL+commit 去重、queued 状态。
- `report_store.py`：`data/reports/*.json` + `data/index.json` 原子写、锁。
- `ai/`：provider 选择、payload 构建/脱敏、校验、错误映射。
- `export.py`：Markdown 渲染。
- `api/routes.py`：扫描/报告/更新/导出/AI/健康检查/示例。

---

## 10. API 设计

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/scans` | body `{url, branch?, force?}` → `{job_id, status, cached_report_id?}` |
| GET | `/api/scans/{job_id}` | 进度 `{status, stage, progress, elapsed_ms, error?, report_id?}` |
| GET | `/api/reports/{report_id}` | 完整报告 |
| GET | `/api/reports?limit=10` | 最近报告摘要（来自 index） |
| POST | `/api/reports/{report_id}/refresh` | 重新体检（force） |
| GET | `/api/reports/{report_id}/updates` | 检查上游 HEAD；`{status, latest_commit, current_commit, retry_after?}` |
| POST | `/api/reports/{report_id}/ai` | 生成/重试 AI 建议（幂等，有缓存直接返回） |
| GET | `/api/reports/{report_id}/export?format=json\|md` | 下载报告 |
| GET | `/api/health` | `{version, rules_version, ai:{enabled,provider,model}, tokens:{github,gitee}}` |
| GET | `/api/examples` | 示例仓库与演示点 |
| GET | `/api/docs` | Swagger UI（FastAPI 自带） |

**错误响应**：`{error_code, message, details?, retry_after?}`；HTTP 400/404/409/429/500 对应语义。

**并发**：扫描并发 ≤ 2（`ThreadPoolExecutor`），排队任务显示 queued；同一 repo+commit 的进行中任务复用；单次扫描 180s 超时。AI 生成走独立小线程池，不阻塞扫描。

---

## 11. 数据模型（核心字段）

```
Report {
  id, schema_version, rules_version, tool_version,
  platform, repo {owner, name, full_name, html_url, description, private, stars, forks,
                  language, license, default_branch, archived, pushed_at, size_kb},
  commit {sha, short_sha, message, date, url, branch},
  analyzed_at, duration_ms, cached,
  score {total, grade, label, capped, cap_reason?, dimensions:[
          {key, name, score, weight, weighted, status, reasons[]}]},
  sections {
    readme {present, path?, chars, sections:[{key,label,present}], code_blocks, badges, findings},
    dependencies {manifests:[{path,ecosystem,kind,parse_ok,dependency_count,lockfile}], ecosystems, findings},
    startup {scripts[], doc_commands[], docker{}, procfile?, env_vars[], env_example, suggested_command?, findings},
    windows {files:[{path,type,purpose,referenced,risk_flags,size}], count, only_windows_start, findings},
    paths {findings:[{rule_id,path,line,snippet,severity,occurrences}], counts_by_rule},
    secrets {findings:[{rule_id,path,line,masked,severity,kind}], env_files[], gitignore_env, findings}
  },
  risks:[Risk], suggestions[], top_actions[],
  ai {status, provider?, model?, generated_at?, summary?, reference_score?, score_reason?,
      blockers[]?, quick_wins[]?, integration_plan[]?, caveats[]?, error?},
  update {previous_commit?, previous_report_id?, has_previous},
  limits {compressed_bytes, extracted_bytes, files_total, files_scanned, files_skipped,
          truncated, duration_ms},
  project {languages[], has_ci, has_tests, has_license, file_count}
}
```

- 存储在 `data/reports/{id}.json`（UTF-8，原子替换）；`data/index.json` 保存每个 repo+分支的最新 report id/commit/score/history（最多 10 条）。
- 不存储归档内容；临时目录扫描后删除；不存储未脱敏密钥。
- `report_id = sha1(platform + full_name + branch + commit_sha + rules_version)[:16]`。

---

## 12. 更新跟踪设计（README 必写）

### 12.1 已实现（轻量）

1. **发现更新**：报告页「检查更新」调用 `/updates` → 平台 API 取分支 HEAD（缓存 5 分钟）；与报告中 commit 比较。
2. **避免全量重算**：
   - 扫描前先取 HEAD；若 `index` 中存在同 repo+branch+commit 且 `rules_version` 一致 → 直接返回缓存报告（`cached=true`，毫秒级）。
   - `force=true` 或规则版本变化才重算。
   - 新 commit 触发完整重扫（轻量实现），但复用元数据、复用前端报告结构与历史索引。
3. **commit 标注**：报告固定记录 `commit.sha/short_sha/message/date/branch`；UI 顶部与导出文件均显示；对比上一份报告时展示前后 commit。
4. **失败/限流兜底**：
   - HEAD 检查失败 → `status=unknown`，展示缓存报告并标注"无法确认是否有更新"；不用旧数据冒充最新。
   - GitHub 403/429 → 读取 `X-RateLimit-Reset` / `Retry-After`，提示重置时间；检查结果内存缓存 5 分钟，避免每次刷新都打 API。
   - Gitee HEAD 获取失败 → 使用 `git ls-remote` 兜底；元数据失败会返回明确错误，不以“无元数据的归档”替代，避免 commit 标注不准确。
   - 归档失败 → Gitee 走 `git clone --depth 1`，并核对克隆 SHA 与元数据 HEAD；GitHub 重试后给出明确错误。
   - AI/报告缓存损坏 → 删除损坏文件并按未命中处理。

### 12.2 生产级增量方案（README 设计说明，不实现）

- 使用 GitHub Trees/Compare API（Gitee 对应 commits/compare）获取旧 commit → 新 commit 的变更文件列表与 blob SHA。
- 以 `blob_sha + rules_version` 为键缓存**文件级检测结果**；仅对新增/修改文件运行内容检测；删除文件剔除旧 findings；README/清单等聚合分析基于缓存结果重算。
- 比较结果超过 API 上限、force push、分支重写、规则版本变化 → 回退全量扫描。
- 未变更的仓库元数据/目录结构复用缓存；报告基于新 commit 重新汇总评分。
- 定时任务（cron/队列）批量检查关注仓库的 `pushed_at`/HEAD；命中更新后入队增量扫描。
- 报告标注 `analyzed_commit`、`tool_version`、`rules_version`，并提供"基于新 commit 重新生成"入口。
- 限流：Token 池 + 按 `X-RateLimit-Remaining/Reset` 调度；失败指数退避；stale-while-revalidate；前端明确展示数据新鲜度。

---

## 13. 安全与隐私

- **只读**：仅下载归档并静态扫描；绝不执行仓库代码、安装依赖、运行脚本。
- **SSRF 防护**：仅白名单 host；不请求用户提供的任意 URL；重定向终点校验；拒绝 IP/非标准端口。
- **归档安全**：压缩/解压体积、文件数、单文件上限；拒绝路径穿越/绝对路径/符号链接；统一路径规范化；临时目录隔离并清理。
- **私有仓库**：metadata.private=true 直接拒绝，避免 Token 越权读取私有代码。
- **密钥处理**：只在内存中匹配；报告/缓存/导出仅存脱敏值；日志不记录原文；AI payload 只含脱敏证据；发送前二次自检。
- **AI 隐私**：只发送摘要与已脱敏证据；UI 明示；无 Key 不调用。
- **限流与滥用**：扫描接口简单内存限流（如 30 次/分钟/IP，便于演示与自测）；单并发 ≤ 2；大仓库拒绝。
- **前端**：URL 渲染转义；代码片段以文本渲染；禁用危险 HTML；导出文件名安全化。

---

## 14. 测试与验收

### 14.1 自动化测试（pytest）

| 模块 | 用例 |
|---|---|
| URL 解析 | GitHub/Gitee 变体、SSH、`.git`、`/tree/branch`、非法域名、SSRF、路径注入 |
| README | 完整/中文/缺失/过短/无代码块 |
| 依赖 | package.json 正常/损坏、多清单、锁文件、pyproject/go.mod |
| 启动 | scripts、Makefile、Docker、Procfile、README 命令提取、建议命令 |
| Windows | 四种扩展名、用途、README 引用、危险模式 |
| 路径 | `C:\`/`C:/`/转义、`https://` 排除、`/Users/`、占位符、文档降级、UNC |
| 密钥 | 每类正样本；占位符/示例负样本；熵阈值；Bearer 假阳性；脱敏；`.env`/`.gitignore` |
| 解压 | `../`、绝对路径、symlink、zip bomb 上限、文件数上限 |
| 抓取 | MockTransport：GitHub/Gitee 元数据、限流、404、归档重定向、超时 |
| 评分 | 权重、封顶、边界 89/90、缺失 README/启动的 0 分处理、确定性 |
| 缓存/更新 | 同 commit 命中、force、新 commit、规则版本失效、限流 unknown |
| AI | provider 选择、schema 校验、参考分 clamp、失败降级、payload 无明文密钥 |
| API | 扫描→轮询→报告、导出、健康检查、错误码 |

### 14.2 真实冒烟（联网，人工 + 截图）

| 仓库 | 验证点 |
|---|---|
| `github.com/Plazmaz/leaky-repo` | 密钥识别、脱敏、封顶、风险排序 |
| `github.com/ChrisTitusTech/winutil` | PowerShell 脚本盘点、跨平台风险（19.8MB，验证体积处理） |
| `github.com/sindresorhus/got` | 规范项目高分、README/依赖/启动正向判断 |
| `gitee.com/y_project/RuoYi` | Gitee 全链路、中文 README、Java 依赖 |
| `github.com/octocat/Hello-World` | 极简仓库低分与缺失项 |

> 若某真实仓库内容变化导致结果不同，以规则可解释为准；测试断言只针对固定 fixture，不针对联网仓库的绝对分数。

### 14.3 验证命令

```bash
# 后端依赖与测试
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
.venv/Scripts/python -m pytest

# 前端
cd frontend
npm install
npm run typecheck   # tsc --noEmit
npm run build
cd ..

# 一键启动（首次较慢，之后增量）
start.bat

# 冒烟
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/scans -H "Content-Type: application/json" -d '{"url":"https://github.com/Plazmaz/leaky-repo"}'
# 轮询 /api/scans/{job_id}，完成后打开 /report/{report_id}

# README 截图（本机 Edge）
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --headless=new --disable-gpu --window-size=1440,1400 \
  --virtual-time-budget=8000 \
  --screenshot="E:\\Git_TestProject\\docs\\screenshots\\report.png" \
  "http://127.0.0.1:8000/report/<report_id>"
```

### 14.4 验收清单（Definition of Done）

- [ ] `start.bat` 在干净环境（Python ≥3.11 + Node 20+）一条命令启动，页面可用。
- [ ] GitHub 与 Gitee 各至少 1 个真实仓库完整出报告。
- [ ] 六类检测均有真实输出；密钥全部脱敏。
- [ ] 评分公式、封顶、等级、规则版本可查看；同快照重复扫描分数一致。
- [ ] 风险表筛选/搜索/展开/源码跳转可用；导出 JSON/MD 成功。
- [ ] 同 commit 二次扫描命中缓存；新 commit 提示更新；限流错误有兜底文案。
- [ ] AI 有 Key 时生成建议与参考分；无 Key/失败时优雅降级。
- [ ] `pytest` 全绿；前端 `tsc` + `vite build` 成功；GitHub Actions CI 配置可执行。
- [ ] README 四问更新跟踪、AI_USAGE 真实错误记录、.env.example、LICENSE 齐全；截图已放入 `docs/screenshots/`。
- [ ] 无密钥、临时文件、归档、node_modules、venv 进入 git。

---

## 15. 交付物与 Git 计划

**本轮执行边界**：我会完成代码、检测规则、测试、前端、AI 适配器、README/AI_USAGE/PRD、截图与本地 git 分阶段提交；不会替你创建 GitHub 远程仓库、推送或在聊天中收集密钥。真实 AI/Token 联调需要你在本地 `.env` 填好后告知我。

| 交付物 | 说明 |
|---|---|
| 源码 | `backend/`、`frontend/`、`scripts/` |
| `README.md` | 简介、截图、快速开始、环境变量、检测与评分规则、更新跟踪设计、限流、安全、限制、测试 |
| `.github/workflows/ci.yml` | push/PR 跑 pytest + 前端类型检查/构建 |
| `AI_USAGE.md` | 工具、使用方式、验证方法、至少 1 条真实 AI 错误记录（含复现与修正） |
| `docs/PRD.md` | 本文件（实现后落库） |
| `.env.example` | 所有可选项与注释 |
| `LICENSE` | MIT |
| `docs/screenshots/` | 首页、报告页（用系统 Edge headless 截图，已验证本机可用） |
| Git 历史 | 分阶段 commit：scaffold → fetch → analyzers → scoring/api → frontend → ai → tests/docs |

**Git 提交流程**：实现并验证后 `git init -b main`，按阶段提交；用户创建 GitHub 远程仓库后 `git remote add origin <url> && git push -u origin main`（README 提供命令）。提交信息按功能分层，避免一次性大提交。

**AI_USAGE 真实素材（已在规划阶段发生，可直接记录）**：
1. AI 最初假设 Gitee 归档可用 HEAD 探测 → 实测 HEAD 返回 405，改为 GET + 白名单重定向。
2. AI 最初把 `git ls-remote` 作为 GitHub 兜底 → 实测本网络连接重置，改为 API + codeload 主链路。
3. AI 最初设计五维雷达图 → 按 dataviz 规范核查后改为横向条形仪表（精确比较与无障碍性更好）。
每条记录都附命令/输出摘要、发现方式与修正，满足"AI 答错但被发现"的真实性要求。

---

## 16. 实施里程碑

| 阶段 | 内容 | 验证门 |
|---|---|---|
| M1 骨架 | 目录、配置、FastAPI health、静态托管、Vite/Tailwind 骨架、start 脚本 | `uvicorn` 启动，首页可见 |
| M2 拉取层 | URL 解析、GitHub/Gitee 适配器、安全下载/解压、文件索引、Mock 测试 | 真实下载两个平台快照并统计文件 |
| M3 检测器 | README/依赖/启动/Windows/路径/密钥 + fixtures + 单测 | 单测全绿；fixture 结果符合预期 |
| M4 评分与报告 | 评分、封顶、风险聚合、Pydantic schema、Markdown 导出 | 固定 fixture 分数快照稳定 |
| M5 扫描与缓存 | job 管理、进度、缓存、更新检查、API 路由 | 扫描→报告→缓存→更新全链路 |
| M6 前端 | 首页、扫描、报告、图表、筛选、AI 区、错误态 | 端到端真实仓库演示 |
| M7 AI | 双适配器、prompt、校验、脱敏、异步生成、失败降级 | mock 测试全绿；用户在本地 `.env` 填入 Key 后做一次真实联调；无 Key 时 UI 优雅降级 |
| M8 收尾 | 真实冒烟、误报调优、README 截图、文档、LICENSE、GitHub Actions CI、git 提交 | 验收清单全过 |

---

## 17. 风险与对策

| 风险 | 对策 |
|---|---|
| GitHub 网络不稳定 / ls-remote 失败 | 主链路 API + codeload SHA；git 仅可选兜底；重试与清晰错误 |
| Gitee 归档 HEAD 405 / 重定向 | 只用 GET；允许白名单重定向；SHA 归档；失败走 git clone |
| API 限流 | Token 支持；只取 1–2 次元数据；归档不占 API；缓存 HEAD 5 分钟；429 文案 |
| 大仓库超时/内存 | 50MB/200MB/5000 文件/512KB 单文件上限；流式下载；截断报告 |
| 密钥误报 / 展示泄露 | 前缀规则 + 熵 + 占位符白名单 + 文档降级；全链路脱敏；回归测试 |
| 路径正则误报 | 负向后行排除 URL；上下文检查；文档/夹具降级 |
| tar/zip 路径穿越 | 手动成员过滤；拒绝绝对/`..`/symlink；临时目录 |
| Windows 一键启动失败 | 纯 ASCII .bat；`py -3.12` 检测；分步错误提示；同时提供 start.sh 与手动步骤 |
| 前端构建/静态托管路径问题 | 产物路径 `frontend/dist`；SPA fallback 顺序测试；Vite base `/` |
| AI 超时/结构化失败 | 独立异步接口；30s 超时；schema 校验；失败可重试；不影响主报告 |
| 真实仓库内容变化导致演示波动 | 测试用固定 fixture；演示仓库选择稳定；报告标注 commit |
| 无头截图不可用 | 优先系统 Edge/Chrome headless 截图；失败则用 Playwright（仅开发依赖）或退化为手工截图说明 |
| 48h 内范围膨胀 | P0 优先；AI/导出/CI 为 P1/P2；不做文件级增量与部署 |

---

## 18. 目录结构（计划）

```
E:\Git_TestProject\
├─ README.md
├─ AI_USAGE.md
├─ LICENSE
├─ .env.example
├─ .gitignore
├─ start.bat / start.sh
├─ .github/workflows/ci.yml
├─ scripts/
│  ├─ start.py             # 跨平台一键启动：venv/依赖/构建/uvicorn/开浏览器
│  └─ dev.py               # 开发模式：uvicorn --reload + vite dev
├─ docs/
│  ├─ PRD.md
│  └─ screenshots/
├─ backend/
│  ├─ requirements.txt / requirements-dev.txt
│  ├─ app/
│  │  ├─ main.py / config.py / models.py
│  │  ├─ api/routes.py
│  │  ├─ services/
│  │  │  ├─ platform/{base,parser,github,gitee}.py
│  │  │  ├─ fetcher.py / file_index.py
│  │  │  ├─ analyzers/{readme,dependencies,startup,windows_scripts,paths,secrets}.py
│  │  │  ├─ scoring.py / suggestions.py / scan_manager.py / report_store.py
│  │  │  ├─ export.py
│  │  │  └─ ai/{base,anthropic_provider,openai_provider,service}.py
│  │  └─ utils/{text,redact,urls,archive}.py
│  └─ tests/{fixtures,test_*.py}
├─ frontend/
│  ├─ package.json / vite.config.ts / tsconfig*.json / index.html
│  └─ src/
│     ├─ main.tsx / App.tsx / index.css
│     ├─ lib/{api,types,format}.ts
│     ├─ components/{Layout,ScoreRing,DimensionBars,DimensionCard,
│     │   RiskTable,SeverityTiles,ReadmePanel,DependencyPanel,StartupPanel,
│     │   WindowsPanel,PathsPanel,SecretsPanel,AiPanel,UpdateBanner,ScoreMethod}.tsx
│     └─ pages/{Home,ScanProgress,Report,NotFound}.tsx
├─ pytest.ini
├─ frontend/package-lock.json   # 提交，CI 用 npm ci
└─ data/（gitignored：reports/index）
```

---

## 19. 已确认决策记录

| 问题 | 结论 |
|---|---|
| 项目名 | **RepoReady** |
| 评分权重 | **均衡版**（README 20 / 依赖 15 / 启动 20 / 跨平台 15 / 安全 30） |
| AI 参考分 | **包含**，独立标注、不影响主评分 |
| 工程加分项 | **GitHub Actions CI + README 截图**；不做额外 demo 仓库、不做英文 README |
| 更新跟踪 | 轻量实现 + README 生产级增量设计 |
| 交付与 Git | 本地一键启动；我负责 git init + 分阶段 commit，用户推送 GitHub |
| 凭据 | GitHub/Gitee Token 与 AI Key 可用，稍后写入 `.env`；无凭据模式必须可运行 |

> 无遗留产品问题。实现阶段若出现新的范围取舍，按"P0 优先、演示稳定性优先"处理，并在 README 记录。
