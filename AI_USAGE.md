# AI_USAGE · RepoReady 开发中的 AI 使用记录

> 开发日期：2026-11-26
> 说明：本文件记录在本项目中实际使用 AI 的方式、验证手段，以及 **真实发生并被发现的 AI 错误**。没有编造“AI 答错”案例；下面每一条都能在代码、测试或命令输出中找到对应证据。

---

## 1. 使用了哪些 AI / 工具

| 工具 | 角色 | 实际用途 |
|---|---|---|
| **Claude Code（CLI 编码代理）** | 主力开发 | 需求拆解、PRD、架构设计、后端/前端编码、测试编写、文档、代码审查 |
| **Claude Code 规划子代理（Plan）** | 独立设计审阅 | 对架构、扫描管线、评分、AI 适配器、风险点做独立推演；其建议由我逐条判断后采纳/拒绝 |
| **curl / httpx 探测** | 非 AI 验证 | 验证 GitHub / Gitee API、归档、分支 HEAD、重定向、限流等真实行为 |
| **Edge Headless** | 非 AI 验证 | 对首页与报告页做真实浏览器截图与页面检查 |
| **pytest / TypeScript / Vite** | 非 AI 验证 | 自动测试、类型检查、生产构建 |

> 没有把任何真实 Token / AI Key 发给 AI 或提交到仓库。联调所需密钥只从本地 `.env` 读取。

---

## 2. AI 参与的工作流

1. **需求拆解与题目映射**：AI 把题目拆成“URL → 安全快照 → 六类检测 → 确定性评分 → 可视化 → 风险清单 → 更新跟踪设计 → AI 加分项”，并列出限流、SSRF、归档安全、密钥脱敏等硬点。
2. **技术选型**：用户确认 Python FastAPI + React；AI 给出平台适配器、线程池扫描、JSON 报告缓存、双 AI 适配器方案。
3. **真实链路探测（关键）**：在写 PRD 前用 curl/httpx 实测 GitHub / Gitee 的 API、归档、HEAD、重定向与限流，避免“纸上架构”。
4. **PRD**：形成 `docs/PRD.md`（含评分公式、检测规则、误报控制、API、数据模型、更新跟踪、安全边界、验收清单）。
5. **分阶段实现**：后端模型/适配器/抓取/六类分析器/评分/缓存/API → 前端页面与图表 → AI 适配器 → 测试 → 文档。
6. **验证与修正**：单测、真实 Gitee 扫描、生产构建、浏览器截图、密钥序列化检查；发现 AI 输出问题即修，并补回归测试。
7. **审查**：用 `/code-review` 类思路检查类型、错误路径、缓存一致性、安全边界；对 AI 设计的方案做“是否真的可运行”复核。

### 典型提示词（摘录/概述）

- **PRD 提示词**：  
  “为 48 小时 Git 仓库接入体检题写 PRD：必须覆盖 README、依赖、启动脚本、Windows 脚本、硬编码路径、密钥；给出确定性评分与风险清单；设计 GitHub/Gitee 拉取、限流兜底、更新跟踪说明、AI 加分项与验收清单。”
- **分析器提示词**：  
  “写一个纯函数密钥扫描器：高置信前缀规则 + 泛化赋值熵检测 + 占位符白名单 + 文档/测试降级 + 全量脱敏；输出文件/行号/脱敏证据；不要执行仓库代码。”
- **审查提示词**：  
  “审查当前实现：找会阻断演示的真实问题（限流、归档、静态托管、评分封顶、缓存、脱敏），优先给文件/行号与修复方案，不要泛泛而谈。”

---

## 3. AI 错误记录（真实发生 + 如何被发现 + 修正）

### 记录 1：Gitee 归档用 HEAD 探测（405）

- **AI 的假设**：下载归档前先发 `HEAD` 判断 Content-Length / 状态，再 GET。
- **实际情况**：Gitee 归档端点对 HEAD 返回 **405**，但 GET 会 302 到签名后的 `blazearchive` 地址并返回 zip。
- **如何发现**：写 PRD 前用 curl 实测：
  ```bash
  curl -sSIL https://gitee.com/y_project/RuoYi/repository/archive/master.zip
  # HTTP 405
  ```
- **修正**：Gitee 归档只使用 **GET**；允许白名单重定向；不发送 API Token；对最终 host 做校验。
- **代码位置**：`backend/app/services/http_client.py`、`backend/app/services/platform/gitee.py`。
- **后续关联问题**：即便 GET，httpx 仍可能拿到 WAF 返回的 HTML 页面（46KB，`<!DOCTYPE...`）。于是增加归档 HTML 检测 + `git clone --depth 1` 兜底：
  - `backend/app/services/fetcher.py`（`ARCHIVE_BLOCKED`）
  - `backend/app/services/scan_service.py`（`_clone_fallback`）
  - 真实扫描 RuoYi 时验证成功。

### 记录 2：GitHub 用 `git ls-remote` 作为兜底（连接重置）

- **AI 的假设**：GitHub 元数据 API 失败时，可以用 `git ls-remote` 获取 HEAD SHA。
- **实际情况**：当前网络下 `git ls-remote https://github.com/...` 返回：
  ```text
  error: RPC failed; curl 56 Recv failure: Connection was reset
  fatal: expected flush after ref listing
  ```
- **如何发现**：联调前的网络探测。
- **修正**：GitHub 主链路固定为 **REST API + codeload 按 SHA 归档**；git 只作为 Gitee 的兜底，不作为 GitHub 依赖。
- **代码位置**：`backend/app/services/platform/github.py`、`backend/app/services/scan_service.py`。
- **备注**：GitHub API 未认证 60 次/小时/IP，当前网络出口可能共享配额；README 建议配置 `GITHUB_TOKEN`。

### 记录 3：泛化密钥规则把方法链当密钥（真实误报）

- **AI 的初版规则**：`password = configService.selectConfigByKey("...")` 这类赋值中，值看起来熵够高、长度够长，被识别为 high 级泛化凭据。
- **实际情况**：在真实仓库 `gitee.com/y_project/RuoYi` 的 `SysUserServiceImpl.java` 中命中了该误报，导致安全维度被封顶、报告分数被压低。
- **如何发现**：真实扫描输出中出现：
  ```text
  SEC-GENERIC  SysUserServiceImpl.java:533  conf…yKey  high
  ```
  人工复核代码后确认是方法调用而非真实凭据。
- **修正**：
  1. 泛化值排除点号方法链 / camelCase 标识符（无数字时）；
  2. 要求值包含数字或 `_ - + =`；
  3. 增加回归测试：
     - `backend/tests/test_secrets.py::test_method_chain_not_generic_secret`
     - `_should_skip_generic("configService.selectConfigByKey") is True`
- **结果**：重扫 RuoYi 后安全维度从 0 恢复为 100，误报消失。

### 记录 4：私钥头被“占位符”规则误杀（漏报）

- **AI 的初版占位符规则**：所有命中值只要包含空格就视为占位文本。
- **实际情况**：`-----BEGIN RSA PRIVATE KEY-----` 天然包含空格，会被当成 placeholder 跳过，导致**私钥规则永远不触发**。
- **如何发现**：编写 `test_all_provider_patterns` 时发现 `SEC-PRIVATE-KEY` 缺失；检查规则才意识到空格过滤误伤。
- **修正**：`is_obvious_placeholder()` 对私钥头显式豁免；补测试覆盖 private key。
- **代码位置**：`backend/app/utils/secrets_patterns.py`。
- **测试**：`backend/tests/test_secrets.py::test_all_provider_patterns`、`test_mask_secret_never_returns_full_value`。

### 记录 5：前端图标 `Github` 在 lucide-react 1.80 不存在（构建期发现）

- **AI 的假设**：`lucide-react` 导出 `Github` 品牌图标，TypeScript 类型检查通过。
- **实际情况**：`vite build` 报：
  ```text
  [MISSING_EXPORT] "Github" is not exported by "node_modules/lucide-react/dist/esm/lucide-react.mjs"
  ```
  lucide v1.80 已不包含品牌图标，TypeScript 未拦住，生产构建拦住。
- **如何发现**：`node node_modules/vite/bin/vite.js build`（直接构建）暴露错误。
- **修正**：全部替换为通用 `GitFork` 图标；重新构建成功。
- **代码位置**：`frontend/src/pages/HomePage.tsx`、`frontend/src/pages/ReportPage.tsx`。
- **经验**：类型检查通过不等于运行时导出存在；前端必须以生产构建作为门禁。

### 记录 6：五维雷达图（设计与可读性问题）

- **AI 的初版设计**：五维分数用雷达图展示，视觉上“像体检仪表盘”。
- **问题**：五维数据是“比较大小”，雷达图在精确比较和无障碍表格等价上弱于横向条形；dataviz 规范要求优先直接标注、表格视图、非颜色单一编码。
- **如何发现**：阅读 dataviz 规范并对照表单/反模式后修正。
- **修正**：改为五维横向条形仪表 + 评分环 + 严重度 KPI 瓦片；维度卡作为表格等价视图。
- **代码位置**：`frontend/src/components/DimensionBars.tsx`、`ScoreRing.tsx`、`SeverityTiles.tsx`。

### 记录 7：AI 规划子代理的部分建议被拒绝（避免“照单全收”）

规划子代理提供了很有价值的审阅，但也有与实测事实/官方规范冲突的建议，我没有采纳：

| AI 子代理建议 | 拒绝原因 |
|---|---|
| Gitee 归档只能按分支，不能按 SHA | 实测 `repository/archive/{sha}.zip` 返回 200 且根目录为 `{repo}-{sha}`，SHA 归档是确定性的，优先使用 |
| Anthropic 直接走裸 HTTP | 官方 SDK 规范要求 Python 项目使用 `anthropic` SDK；适配器按 SDK + 结构化输出实现 |
| 五维使用雷达图 | dataviz 规范建议比较类数据用条形；改为条形仪表 |
| AI 不给参考分 | 用户明确要求独立参考分；保留但明确标注“不影响主评分” |

### 记录 8：httpx 默认 certifi 导致 GitHub API TLS 失败

- **AI 的初版实现**：`HttpClient` 使用 httpx 默认证书校验（certifi 证书包）。
- **实际情况**：用户开启网络加速器后扫描 `Plazmaz/leaky-repo` 报 `NETWORK_ERROR`；服务端直接请求 `api.github.com` 报 `SSL: CERTIFICATE_VERIFY_FAILED`。
- **发现来源（重要）**：这是**用户在真实使用中扫描失败后截图反馈**的问题，不是 AI 自查发现的。用户截图暴露出两个问题：
  1. GitHub API 的 TLS 证书链校验失败；
  2. 失败任务仍然显示 100% 进度，容易被误认为“已完成”。
- **用户截图**：
  ![用户真实扫描失败截图：NETWORK_ERROR + 100%](docs/screenshots/network-error.png)
- **诊断**：不是 Token/限流；对比测试发现：
  - httpx 默认 certifi 上下文：失败
  - `ssl.create_default_context()`（系统证书库）：HTTP 200
  - codeload 归档：正常
- **修正**：
  - `HttpClient` 改用系统信任库，同时保留 TLS 校验（没有使用 `verify=False`）；
  - 失败任务保留实际进度，不再显示 100%；
  - README 增加代理/证书排障说明。
- **验证**：修复后 GitHub `Plazmaz/leaky-repo` 强制重扫成功（33/F，4 critical + 6 high），Token 配额正常。

### 记录 9：测试夹具中的过期证书被当成 critical 私钥

- **AI 的初版实现**：所有 `.pem` / `.key` 文件和非 fixture 的私钥命中都按 critical/high 处理，没有区分 `test/fixtures/` 这类测试夹具。
- **如何发现**：端到端验收扫描 `sindresorhus/got` 时得到 48/F；检查发现 critical 来自 `test/fixtures/expired-certificate*.pem`（仓库故意提交的过期证书测试夹具），把安全维度打成 0 并触发总分封顶。
- **修正**：
  - fixture/examples/samples 路径下的密钥与 `.env` 降为 low；
  - 其他 test/docs 路径降为 medium；
  - `.ai` / `.eps` 等设计文件按二进制跳过；
  - 新增 `test_fixture_secrets_are_low_severity` 回归测试。
- **验证**：`got` 从 **48/F → 76/C**；`Plazmaz/leaky-repo` 仍为 **33/F**（真实私钥仍被 critical 识别），说明误报修复没有削弱真阳性。
- **代码位置**：`backend/app/services/analyzers/secrets.py`、`backend/app/services/file_index.py`。

### 记录 10：旧报告的 disabled 状态没有 AI 生成按钮

- **AI 的初版实现**：前端只为 `ai.status === "not_generated"` 显示「生成 AI 建议」按钮；对于在 AI 配置之前扫描、状态为 `disabled` 的旧报告，只显示“AI 未启用”，没有补生成入口。
- **如何发现**：用户配置阿里云百炼 Key 后反馈“接入建议这块怎么没有”；检查发现用户打开的报告 `ai.status=disabled`（扫描时 AI 尚未配置），后端 `/api/health` 已启用 AI，但前端没有按钮。
- **修正**：
  - `AiAdvicePanel` 接收后端 `ai.enabled` 状态；
  - 后端 AI 已启用时，`disabled` 旧报告也显示「生成 AI 建议」；
  - `AI_AUTO_GENERATE=true` 时，`disabled` 旧报告也允许自动生成；
  - README 补充“旧报告可补生成”说明。
- **验证**：对用户的旧报告调用真实 `qwen-plus`，状态变为 `ready`，参考分 72；主评分 69 与 fingerprint 不变。首页/报告页重新加载后 AI 建议正常展示。
- **代码位置**：`frontend/src/components/AiAdvicePanel.tsx`、`frontend/src/pages/ReportPage.tsx`。

---

## 4. 如何验证 AI 输出（不是“看着像就行”）

| 维度 | 验证手段 | 结果 |
|---|---|---|
| 后端逻辑 | `pytest` 109 个用例：URL、六类检测、解压安全、评分、缓存、API、AI | 全绿 |
| 密钥脱敏 | 断言序列化报告 / 导出 / AI payload 不含 fixture 原始假密钥 | 通过 |
| 评分确定性 | 同一 fixture 重复构建，分数与指纹一致；AI 前后指纹一致 | 通过 |
| 危险输入 | 路径穿越、绝对路径、symlink、zip bomb、Windows 保留名、大小写冲突 | 拒绝 / 跳过并告警 |
| API 契约 | FastAPI TestClient：健康、扫描提交、报告、导出、SPA fallback、404 | 通过 |
| 真实仓库 | Gitee RuoYi 完整扫描（归档被反爬 → 浅克隆兜底）；GitHub `Plazmaz/leaky-repo` 完整扫描（限额重置后） | 均成功；GitHub 报告 33/F，4 critical + 6 high，证据全部脱敏 |
| AI 端到端 | 本地 Mock OpenAI 兼容服务：AI `ready`、参考分 68、主评分/指纹不变、mock 服务确认 payload 无原始假密钥 | 通过（mock 仅验证链路，不代表真实模型质量） |
| 真实 AI | 阿里云百炼 OpenAI 兼容接口（`qwen-plus`）：`octocat/Hello-World` 报告真实生成成功；AI 参考分 35，主评分与 fingerprint 均不变；未发送明文密钥 | 通过 |
| 前端 | `tsc --noEmit`、`vite build`、Edge headless 截图 | 通过 |
| AI 输出 | Pydantic schema 校验、参考分 clamp、超时/失败降级、风险事实不被改写 | 通过 |

### 真实命令记录（节选）

```bash
# Gitee 归档 HEAD 405、GET 重定向实测
curl -sSIL https://gitee.com/y_project/RuoYi/repository/archive/master.zip

# GitHub codeload 按 SHA 实测
curl -sS -L https://codeload.github.com/octocat/Hello-World/tar.gz/7fd1a60b...

# 后端测试
.venv/Scripts/python -m pytest
# 109 passed

# 前端生产构建
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
```

> 截图见 `docs/screenshots/home.png` 与 `docs/screenshots/report.png`；均为本机真实运行后由 Edge Headless 生成。

---

## 5. 我对 AI 输出的使用原则

1. **可验证优先**：任何涉及网络、限流、归档、路径安全、密钥脱敏的结论，必须用 curl/httpx/测试验证，不凭记忆。
2. **不执行仓库代码**：AI 生成的扫描器只读文本，不 `npm install`、不运行仓库脚本。
3. **评分可复现**：AI 不参与主评分；AI 参考分独立标注；评分指纹排除 AI 与时间。
4. **全量脱敏**：报告、缓存、导出、日志、AI 请求都不出现明文密钥；用测试锁住。
5. **不照单全收**：对 AI 规划/建议逐条核对规范与实测事实，冲突时选可验证的方案。

---

## 6. 备注

- 如果评审需要更多“Vibe Coding”过程材料，可补充：PRD 对话截图、分析器规则迭代记录、真实仓库扫描前后对比截图。
- 本项目没有把任何真实凭据用于 AI 联调；AI Key 只从本地 `.env` 读取，且 `.env` 被 `.gitignore` 忽略。
