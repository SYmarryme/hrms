# T-004 剩余验收：8000 外部隔离与 SQLite 工作空间重启

当前入口 Cookie 已由用户 A/B 证据确认为 `BLOCKED_CURRENT_PUBLIC_ENTRY`，边界
`AFTER_LOOPBACK_VITE`。暂停改写 Cookie 检测，见[官方支持说明（尚未发送）](cloudstudio-support-issue.md)。
以下只收集两项独立证据；它们通过也不会让 T-004/M00 Gate 通过。
脚本交付时为 NOT_RUN；最新用户回传已完成真实工作空间重启：基线退出 0，原回执/哈希独立保存，
after 的 T004_RESTART_EXIT_CODE=0、AFTER_RESTART_EXIT_CODE=0。
数据库部分按原脚本语义登记 **USER_REPORTED_PASS，完整 CONTENT_MATCH 日志待核对**。
8000 本机监听限制与非公开配置用户回传通过，Edge 无痕访问被登录拦截。
已登录所有者在 IDE 通过 8000 预览收到正常 FastAPI 根路径 404，独立受认证入口仍存在，
整体外部隔离 INCOMPLETE/BLOCKED；不将此直接认定为匿名公开漏洞。
见[最新验收表](t004-acceptance.md)与[脱敏摘要](evidence/t004-restart-isolation-summary.json)。
下述 before/after 为保留的原操作流程，**本次只需核对已有产物，不要重建基线**。
不修改正式部署架构，不安装依赖，不改变现有 `.venv`、锁文件、Cookie 或 Vite Host 设置。

## 最新回传后的日志核对

用户已确认实际工作空间停止/重启；原 after 分支退出 0 只有在回执哈希和原库验证均成功后才返回，
对应 result=CONTENT_MATCH。当前只收到退出码摘要，不补造已经读到完整日志的证据。
在 CloudStudio 私下核对原 before/after 的完整 result.json 和退出码；不要把整个 JSON 提交或贴出，
其中包含原 receipt SHA-256。只对**原 after 输出的 artifacts 目录**执行下列只读投影：

```bash
read -r -p '原 after 运行的 result.json 绝对路径: ' T004_AFTER_RESULT
python3 -B - "$T004_AFTER_RESULT" <<'PY'
import json, re, sys
from pathlib import Path
r = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
v = r.get('verification', {})
if (r.get('action') != 'after' or r.get('result') != 'CONTENT_MATCH'
        or v.get('logical_content') != 'MATCH' or v.get('integrity') != 'ok'
        or v.get('workspace_restart') != 'MANUAL_EVIDENCE_REQUIRED'
        or not re.fullmatch('[0-9a-f]{40}', v.get('prepared_commit', ''))):
    raise SystemExit('原 after 产物不满足 CONTENT_MATCH 核对要求；保留证据并排查')
print(json.dumps({'action': 'after', 'result': 'CONTENT_MATCH',
    'logical_content': 'MATCH', 'integrity': 'ok',
    'prepared_commit': v['prepared_commit'],
    'workspace_restart': 'MANUAL_EVIDENCE_REQUIRED'}, indent=2))
PY
printf 'CONTENT_LOG_REVIEW_EXIT_CODE=%s\n' "$?"
```

同时私下确认：原 before=BASELINE_READY、退出 0；原回执与独立原 SHA-256 一致；
prepared_commit 对应原重启前后同一 HEAD；本次 after 及其 exit-code.txt 的 0 对应同一次执行。
本命令只读取既有 JSON，不访问 DB、不重跑 after，不受现在文档更新后的 HEAD 变化影响。
不展示 SHA-256、marker、DB 路径、回执正文或原始日志；仅回传上述脱敏投影和核对结论。
MANUAL_EVIDENCE_REQUIRED 是脚本保留的语义；用户本次已明确确认 UI 重启，该字段不否认这次实际操作。
若原产物缺失则继续 LOG_REVIEW_PENDING；若内容不符，回退 USER_REPORTED_PASS 并调查，不能改 JSON 或重做基线冒充。

8000 最新分项结果见[验收表](t004-acceptance.md)。现已确认所有者的受认证 IDE 预览存在，
下一步优先请官方确认[只撤销预览路由、保留进程与内部代理](t004-platform-compatibility.md#8000-独立预览入口的能力边界)的方法。
原下列流程保留为将来官方配置变更后的对照，不要求为了同一已知限制重复运行或新建映射。
无痕跳转登录页是本次匿名请求被要求认证的证据，与所有者预览可达可以同时成立。

## 0. 一次更新，保留当前服务

在 CloudStudio Ubuntu **项目根目录**的新终端运行。原服务终端保持运行，先完成端口检查，再准备数据库重启。

```bash
git status --short
git pull --ff-only origin main
git rev-parse HEAD
mkdir -p var/m00
```

若已跟踪文件有本地修改或拉取失败，先保留文件并排查，不 reset/覆盖。日志、DB、回执等均放 `var/m00/`，禁止提交。
新脚本不要求重建旧服务；服务启动时的 commit 与脚本 HEAD 分开记录。
如服务已停，按[原启动指令](t004-execution.md)启动，保持后端 127.0.0.1:8000、Vite 3000 和精确 Host。
不要为此关闭安全属性、重建已通过的 M00 环境或新增 8000 公网映射。

## 1. 8000 隔离：本机存活 + 平台映射 + 独立外网

### 1A. 本机前置检查（CloudStudio 终端）

从**现有服务启动记录/健康诊断报告**取真实服务提交，从 3000 端口卡片取实际 HTTPS 分享入口。
以下 `read` 只读取非凭证信息，不填 Token、Cookie 或带查询参数的授权链接：

```bash
read -r -p '实际运行服务的40位 commit: ' T004_SERVICE_COMMIT
read -r -p '现有3000 HTTPS origin（无路径/查询参数）: ' T004_ORIGIN
export T004_SERVICE_COMMIT T004_ORIGIN
python3 -B scripts/m00/t004_port_isolation.py local \
  --service-commit "$T004_SERVICE_COMMIT"
printf 'LOCAL_COMMAND_EXIT_CODE=%s\n' "$?"
```

预期 `LOCAL_BINDING_OK`、退出 0，8000 全部监听地址为 loopback，3000 在监听，
8000 health 的 fixture/状态/服务提交一致。`external_isolation=NOT_VERIFIED` 是正确结果，不是遗漏。
若 8000 为 `0.0.0.0`、`::`、`*`、非 loopback、无监听、提交不匹配或 health 失败，前置不通过，先保留报告。
脚本不停止进程、不改平台映射、不输出响应头/正文/Cookie 值。

### 1B. 核对平台并观察候选地址（CloudStudio 终端）

先在端口面板记录：当前 3000 分享入口、访问模式；8000 是否有路由/分享链接/访问模式。
不要为测试新增 8000 映射。也不要点“关闭端口”来制造不可达：
[官方说明](https://ide.cloud.tencent.com/docs/guide/code_editing/productivity_plugin/port-plug/)中的该操作会终止进程。
“仅自己可见”不等于无独立 API 入口，拥有者若能从浏览器直达后端仍不满足本项。

[官方 URL 规则](https://cloud.tencent.com/document/product/1039/131818)为
`https://${X_IDE_SPACE_KEY}--${PORT}.${X_IDE_SPACE_REGION}.${X_IDE_SPACE_HOST}`。
仅当现有入口确实采用 `--3000.` 格式，可用下面命令得到**候选地址**，它不会创建映射。
此格式之外不要猜域名，标记 INCOMPLETE，请官方说明实际映射规则。

```bash
T004_BACKEND_ORIGIN="$(python3 - "$T004_ORIGIN" <<'PY'
import sys
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1])
if (u.scheme != 'https' or not u.hostname or not u.hostname.split('.')[0].endswith('--3000')
        or u.username or u.password or u.query or u.fragment or u.path not in ('', '/') or u.port not in (None, 443)):
    raise SystemExit('入口格式未确认；不要猜测8000地址')
print('https://' + u.hostname.replace('--3000.', '--8000.', 1))
PY
)"
export T004_BACKEND_ORIGIN
python3 -B scripts/m00/t004_port_isolation.py remote \
  --origin "$T004_ORIGIN" --backend-origin "$T004_BACKEND_ORIGIN" \
  --service-commit "$T004_SERVICE_COMMIT"
printf 'REMOTE_COMMAND_EXIT_CODE=%s\n' "$?"
```

该脚本校验证书、拒绝跳转，无 Cookie jar/平台登录，不保存域名或原始响应。
预期只能是“观测待补证”，不是自动 PASS：

| 结果/退出码 | 解释 |
|---|---|
| `FAIL_BACKEND_EXTERNALLY_ROUTABLE` / 1 | 候选入口收到 HRMS fixture，哪怕不同提交也算暴露，隔离 FAIL |
| `INCOMPLETE_POSITIVE_CONTROL` / 2 | 3000 正控制不成立，不能把整体网络故障当后端隔离 |
| `OBSERVATION_ONLY_EXTERNAL_EVIDENCE_REQUIRED` / 2 | 3000 正常；8000 被拒/跳转/错误或未识别，必须补独立外网/平台证据 |
| `INCOMPLETE` / 2 | 输入/工具/环境不足，按报告排查，不能验收 |

401/403/404/5xx、登录跳转、DNS/TLS 失败或超时均**不能单独证明**没有后端入口。
工作空间自己访问公网域名也不等于独立外网。

### 1C. 独立外部浏览器操作（不能由 CloudStudio 终端代替）

保持两个服务活着，在自己电脑/手机的独立网络浏览器中：

1. 普通已登录 CloudStudio 的浏览器打开 `T004_ORIGIN` + `/api/v1/poc/health`，
   确认 HRMS fixture 与实际服务提交（只查看这项无 Cookie 端点）。
2. 同一浏览器打开 `T004_BACKEND_ORIGIN` + `/api/v1/poc/health`；记录可达/拒绝/平台错误类别。
3. 无痕/未登录窗口对两个地址重复，确认 3000 正控制仍成立。若两者都被平台登录拦截，则这一组证据不足。
4. 立即回 CloudStudio 再运行 1A，证明观测期间后端仍活着。保留前后两份 result.json。

私下保存时间/时区、浏览器访问模式、平台映射截图、正控制及后端结果，遮掉工作空间标识/完整域名，
不要导出 HAR、原始头、Cookie 或登录页面凭证。
**任何外部模式能收到 8000 的 HRMS 响应，都不满足“无独立入口”的断言**，包括仅拥有者可访问。
这是严格隔离子项不满足，不自动等于匿名公开漏洞；必须区分匿名请求与所有者受认证请求。
若已确认响应来自 FastAPI，应用层正常 HTTP 404 也代表已到达后端，不能当作网关阻断通过。
接受 T004-06 需：前后 loopback/health 均成立、只公开 3000 的平台映射证据、独立外网正控制成立，
且普通/无痕均无可独立访问的后端；拒绝原因必须能够和平台未映射/隔离机制对应。
只有网络错误、平台说明不清或无法区分访问控制与无路由时为 INCOMPLETE/BLOCKED，不填 PASS。
当前脚本始终不授予整项验收，由用户回传上述脱敏证据确认。

## 2. SQLite：重启前基线 → UI 工作空间重启 → 原库只读验证

本实验只新建一份合成 SQLite marker，不接触任何已有业务库。数据目录是工作空间内
`var/m00/t004-workspace-data/`，结论只适用于该实际路径/工作空间类型。
不是停应用后重跑，也不测试断电恢复/备份还原；不得据此宣称 24 小时在线或正式生产存储已批准。

### 2A. 重启前（完成端口验收后，CloudStudio 终端）

```bash
umask 077
mkdir -p "$PWD/var/m00/t004-workspace-data"
python3 -B scripts/m00/t004_restart_acceptance.py before \
  --data-root "$PWD/var/m00/t004-workspace-data"
printf 'BEFORE_COMMAND_EXIT_CODE=%s\n' "$?"
```

预期 `BASELINE_READY`、退出 0，baseline 的 logical_content=MATCH、integrity=ok。
记录输出的**绝对 receipt 路径**和 `receipt_sha256`。下载该 receipt.json 的独立副本到本地私密目录，
另将 SHA-256、项目绝对路径和 `git rev-parse HEAD` 保存到本地笔记；不要只留在将要重启的工作空间中。
回执含合成 marker 和 DB 路径，仍是私密测试产物，禁止提交。
此时 `workspace_restart=NOT_RUN`；没有实际重启就没有持久化验收。

### 2B. 操作 CloudStudio UI

记录当前时间/时区，使用 CloudStudio 工作空间控制台实际提供的“暂停/停止后恢复”或“完整重启工作空间”操作，
记录具体操作名、状态变化、恢复时间与工作空间身份（私下留截图，不公开标识）。
[官方算力说明](https://ide.cloud.tencent.com/docs/guide/code_editing/basic_operations/compute-switching/)给出的操作是：
顶部“算力”右侧“停止”→工作空间停止提示→“立即启动”。若实际版本有此界面可按此执行，
无需切换 CPU/GPU；界面不同以当前版本的工作空间停止/恢复能力为准并记录，不能用应用重启代替。
**不能仅 Ctrl+C、重开终端、重启 Vite/Uvicorn 或重新运行 start 脚本**。
平台如果没有该能力/权限，标记 BLOCKED 并记录限制，不假定完成。
不要删除/重建工作空间；不要做备份还原或搬移 DB。内核 boot_id/终端断开本身不是充分证据。

### 2C. 恢复后（仍是同一个工作空间、同一个项目绝对路径）

**先验证，暂不 git pull、不 checkout、不重新 prepare、不恢复 DB。**
回到原项目根目录，核对恢复后的 HEAD 与重启前记录一致。输入独立保存的回执路径及原 SHA-256：

```bash
git rev-parse HEAD
read -r -p '重启前原 receipt.json 的绝对路径: ' T004_RECEIPT
read -r -p '独立保存的重启前 receipt SHA-256: ' T004_RECEIPT_SHA256
python3 -B scripts/m00/t004_restart_acceptance.py after \
  --receipt "$T004_RECEIPT" --receipt-sha256 "$T004_RECEIPT_SHA256"
printf 'AFTER_COMMAND_EXIT_CODE=%s\n' "$?"
```

预期 `CONTENT_MATCH`、退出 0，verification.logical_content=MATCH、integrity=ok，
原标记/逻辑摘要一致、WAL 保留、FK 检查无异常。receipt 字节 SHA-256 必须与独立保存值一致。
脚本复用原 `t004_persistence.py` 的只读验证（缺库不会自动创建）；`workspace_restart=MANUAL_EVIDENCE_REQUIRED`
表示需结合 2B 的真实操作证据，不能把它自动变成 PASS。
回执丢失时可使用下载的**原回执**，但不能更改其中 DB 路径/marker/commit 或把 DB/备份拷回来。
原 DB 路径消失、内容/回执/hash/commit 不符、SQLite 损坏均 FAIL；不要重做 before 掩盖丢失。
工具不可用/没有完成 UI 重启为 INCOMPLETE/BLOCKED，不能宣称持久化通过。

结合真实重启证据和 before/after 成功，可回传 T004-08、09、10 中的**数据库部分**结果。
T004-10 的恢复后同源/浏览器子项仍需服务恢复实测，Cookie 仍受当前入口阻断；不将整行或整项自动 PASS。
若要恢复服务，先完成上述原库验证，再依原启动说明准备/启动本次提交的隔离服务并单独复核；
此步骤不属于数据库一致性的证据，也不解除已知 Cookie 阻断。

## 3. 查看产物与回传

每次脚本打印 `artifacts=...` 的目录；`result.json`、`exit-code.txt` 均在被 Git 忽略的 `var/m00/`。
仅针对输出的具体路径查看，不上传整个目录：

```bash
read -r -p '本次脚本输出的 artifacts 绝对目录: ' T004_ARTIFACTS
python3 -m json.tool "$T004_ARTIFACTS/result.json"
cat "$T004_ARTIFACTS/exit-code.txt"
git status --short
```

回传：脚本提交、实际服务提交、端口本机前后结果、外部两种模式及平台映射脱敏结论、
SQLite before/after 结果、实际 UI 重启操作与时间。不要回传 DB、回执内 marker、凭证、Cookie 值、原始日志或私有设计。
除非用户明确提供对应实测证据，否则剩余项继续 NOT_RUN；已知 Cookie 项继续 BLOCKED。
官方问题说明可由用户在官方渠道提交，Codex 未代发；start.sh/preview.yml 仅有独立对照提案，未实施。
