# T-002 精确依赖重放（等待 CloudStudio 执行）

当前状态：锁文件与脚本已准备，**新环境重放 `NOT_RUN`，T-002 `PARTIAL`，未通过验收**。
输入证据为用户回传的原提交 `954bfb341d638e62bf8243073b03f30850ae2d81`：
Ubuntu 24.04.3 LTS / x86_64 / Python 3.11.1；T-001 7/7 MATCH、退出 0；
环境检查 ENV_EXIT_CODE=0；SQLite PoC 13 项通过、POC_EXIT_CODE=0。
本轮未在 Windows 执行安装、venv 重建或项目测试，也未独立重新执行用户回传的结果。

完整 `pip freeze --all` 被无改版地拆成两个文件：
`requirements/m00-bootstrap.lock` 固定 pip/setuptools 两个环境引导工具；
`requirements/m00.lock` 固定另外 11 个项目/测试及传递依赖。合并后正好 13 包。
`requirements/m00.in` 原样保留；本次重放不用它解析新版本。

实现顺序：新建独立 venv → 先引导工具、后项目依赖 → pip check → 严格包清单比对 →
原 SQLite PoC → JUnit 13/13 检查及再次核对版本。任一步失败退出非零并保留证据。
不执行 T-004、生产恢复或业务开发；七份正式文档不修改、不公开。

在 CloudStudio 的项目根目录手动执行：

```bash
git pull --ff-only origin main
git rev-parse HEAD
M00_REPLAY_PYTHON="$PWD/.venv/bin/python" bash scripts/m00/replay_dependencies.sh
replay_rc=$?
printf 'REPLAY_COMMAND_EXIT_CODE=%s\n' "$replay_rc"
```

先确认 `git rev-parse HEAD` 与本轮交付报告的新提交相同。如果 git pull 失败或检出提交
不一致，停止并回传错误，不继续验收。原 `.venv` 中的解释器只用来运行 `venv` 模块，
包安装始终调用新 venv 自己的 Python；不修改/激活/清空原 `.venv`，不安装系统依赖。
如原解释器路径不同，可将变量设为对应 Python 3.11.1 的绝对路径或命令名；
不设置变量时用 `python3`，若它不是 3.11.1 则明确失败，不能以不同版本代替成功。

每次脚本用 `mktemp` 创建唯一的 `var/m00/replay.<随机后缀>/`，虚拟环境位于其下 `venv/`。
因此无需复用或删除 `.venv-replay`；重跑也会使用另一个新目录。整个 `var/` 已被 Git 忽略。
不使用 `--system-site-packages` 或 `--upgrade-deps`；每个 pip 命令绑定新解释器，
隔离用户包、pip 配置/私有源及 pytest 插件/选择参数，避免现有环境影响重放。
Python venv 的隔离行为见 [Python 3.11 官方说明](https://docs.python.org/3.11/library/venv.html)。
pip 精确版本安装选项见 [pip 官方说明](https://pip.pypa.io/en/stable/cli/pip_install/)。

脚本保持快照的全部精确版本，通过公共 PyPI 的二进制轮子重建；不会因下载或兼容性
错误自动升级、降级或退回范围安装。只有完成真实重放后才能说明该锁文件可在目标环境
重建。用户回传中没有包文件哈希，因此本轮不编造 wheel 的 SHA-256。

同一运行目录中的证据：

| 文件/目录 | 内容与通过判据 |
|---|---|
| `commit.txt` | 实际检出的本轮提交 |
| `replay.log` | 系统/Python、两次安装、`pip check`、版本比对、pytest 真实输出 |
| `installed.freeze.txt` | 新环境实际的完整 `pip freeze --all` |
| `versions.json` | `result=LOCK_MATCH`，`missing=[]`、`extra=[]`、`mismatched={}`，`isolated_venv=true` |
| `junit.xml` | 正好 13 个 testcase，无 failure/error/skipped |
| `poc-exit-code.txt` | `0`；未到测试阶段则该文件不生成，不能算通过 |
| `verification.json` | 再次确认版本一致，`poc.cases=13` 且 `poc.result=PASS` |
| `exit-code.txt` | 整个重放退出 `0` |
| `status.txt` | `last_stage=complete`，`exit_code=0` |
| `cases/`、`pytest-cache/`、`venv/` | 当前运行的实验数据库、迁移/备份观察、缓存和新虚拟环境 |

成功输出同时应看到 `No broken requirements found.`、`13 passed`、`POC_EXIT_CODE=0`、
`REPLAY_CHECKS_OK` 与 `REPLAY_EXIT_CODE=0`，调用方的 `REPLAY_COMMAND_EXIT_CODE` 也为 0。
只安装成功、原环境测试通过或部分步骤返回 0 都不构成完整重放成功。
JUnit 数量不足、跳过用例、多装包、锁版本不符、依赖冲突或任何测试失败均不得算通过。

将本轮 commit、脱敏 `replay.log`、`installed.freeze.txt`、两个版本报告、JUnit 和退出码
回传给 Codex。日志可能包含工作区绝对路径，分享前去除个人路径及其他非必要信息；
不要提交日志、数据库或 venv，不发送任何私有交接资料、凭证或真实员工数据。
本次 PoC 是原有实验测试，不证明正式业务或部署完成。收到真实结果前，T-002 不变更为通过。
