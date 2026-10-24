# CloudStudio Ubuntu 执行说明

T-001～T-003 已于 2026-10-25 获用户验收；下一批请使用[T-004 独立执行指令](t004-execution.md)。

首次环境/PoC 用户已回传通过结果，见[验收记录](acceptance.md)。本页保留首次准备步骤；
本轮 T-002 精确锁的操作以[依赖重放说明](m00-replay.md)为准，不再使用范围安装重新定版。
**全新环境重放 `NOT_RUN`，T-002 尚未通过验收。**
只执行 T-001～T-003，不启动 Web 服务，不实施 T-004。

1. 从 GitHub 导入 `SYmarryme/hrms`，选择 `main`，在项目根目录执行
   `git rev-parse HEAD`，与首次交付报告的提交号比对。
2. 通过 CloudStudio 的私有文件传输将本地 `handoff/hrms-m00/` 放到云端同一路径，
   才能核验私有设计。不要把该目录上传公开 GitHub。没有资料时 T-001 云端核验保留
   `NOT_RUN/BLOCKED`，可独立运行环境/数据库 PoC。
3. 准备隔离 Python 环境。以下命令仅供 Ubuntu；有 sudo 权限时才安装缺少的系统包。

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip sqlite3
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/m00.in
python -m pip check
mkdir -p var/m00
python -m pip freeze --all > var/m00/requirements.cloudstudio.txt
python scripts/m00/verify_baseline.py > var/m00/baseline.log 2>&1
baseline_rc=$?
printf 'BASELINE_EXIT_CODE=%s\n' "$baseline_rc"
bash scripts/m00/check_env.sh
env_rc=$?
printf 'ENV_EXIT_CODE=%s\n' "$env_rc"
bash scripts/m00/run_sqlite_poc.sh
poc_rc=$?
printf 'POC_EXIT_CODE=%s\n' "$poc_rc"
```

安装任何一步失败即停下修复，不能把失败后的命令当成功。PoC 暂选 Python >=3.11，
不是对云端预装版本的声明。Python 不足或无 sudo 权限时回传版本/错误，另定环境方案。
`check_env.sh` 还检查 Node/npm；如果缺少，检查结果非零，并先回传真实系统版本，
再确定受支持的 Node/npm 安装及固定方式。此批无 JS 包，所以不生成空壳 npm 锁文件。
标准流程只用 venv/pip 和 pytest，暂不引入另一种包管理器或测试框架。

环境脚本为每项打印版本与退出码，任一工具缺失或非 Ubuntu 退出 1。
`env_probe.py` 报告 Python 内置 SQLite 的实际版本；该版本可能与 CLI 不同。
`df -T` 记录实验文件系统类型，但不代表已验证休眠/重启持久化。
WAL 在目标文件系统无法启用时 PoC 必须失败并留证，不擅自降级或声称部署可行。

`requirements/m00.in` 保留原始范围。用户已回传的真实快照现固定为 `m00.lock`
及 `m00-bootstrap.lock`，应在全新环境按重放说明执行。未经真实回传与验收 T-002 仍待验收。

PoC 测试与预期（用户回传原环境 13/13 通过；新锁环境重放仍为 `NOT_RUN`）：

| pytest 用例 | 正向 / 负向断言 |
|---|---|
| file_wal_foreign_keys_each_connection | 两连接文件库 FK/WAL/timeout；孤立 FK 拒绝 |
| wal_reader_and_busy_timeout_rejection | WAL 读取已提交值；另一写事务等待后 SQLITE_BUSY；释放可重试 |
| waiting_writer_succeeds_after_release | 第二写者等待锁，释放后成功提交 |
| two_connection_cas_and_global_first_marker | 同版本 CAS 仅一成功；全局成功标记重复拒绝 |
| unique_null_and_required_key_boundaries | UNIQUE 允许多个 NULL；相同非 NULL、必填事故号 NULL/重放拒绝 |
| global_first_marker_race | 两独立连接抢全局首次标记，仅一成功 |
| incident_race_rechecks_global_gate_under_lock | 同事故/跨事故竞争，锁内重查全局条件，仅一成功 |
| injected_dml_failure_rolls_back_all_writes | 中途异常后数据、成功标记全部无残留 |
| sqlalchemy_each_connection_and_explicit_transaction | SQLAlchemy 连接事件的 PRAGMA 与显式事务回滚 |
| legacy_sqlite_ddl_limit_is_recorded | 真实展示传统驱动 CREATE TABLE 可能在 rollback 后仍存在 |
| online_backup_wal_isolated_restore_and_corrupt_rejection | 在线 backup 含已提交 WAL、不含未提交值；隔离恢复逻辑一致、拒覆盖/损坏库 |
| alembic_zero_upgrade_repeat_batch_and_failure_restore | 零库/重复升级、保留数据的 batch；注入迁移失败、记录残留、隔离恢复后重试 |

测试中预期的 IntegrityError/SQLITE_BUSY/注入异常由 `pytest.raises` 断言捕获，
只有符合预期才是测试成功；意外未拒绝也会失败。所有数据均为 `lab_*` 合成内容，
全局事故门闩只是事务实验，不是企业生产恢复工具。

Alembic 环境只接受测试代码提供的新临时路径，不加载 `.env` 或业务连接串。
显式连接事务下对 batch 失败后的版本、结构、数据做精确断言；同时单独测传统驱动
DDL 未整体回滚的反例。不能据此推广为所有 SQLite DDL 都安全可回滚。
失败数据库留在当前实验目录并记录 `migration-failure.json`，不执行 stamp、
不在损坏库上重试、不删除残留；从迁移前在线快照恢复到另一目录后才再次 upgrade。
不提供破坏性 downgrade。参考 [SQLAlchemy SQLite 事务说明](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
及 [Alembic batch 迁移说明](https://alembic.sqlalchemy.org/en/latest/batch.html)。
备份使用 [sqlite3.Connection.backup](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)，
不直接复制运行中的主 `.db`。独立企业保管域、审计水位/旧备份防回退和恢复放行不在此 PoC 实现。

每次环境检查输出 `var/m00/env.*/environment.log` 和退出码；PoC 输出
`var/m00/poc.*/poc.log`、`junit.xml`、`exit-code.txt`、独立 cases 数据库及失败观察。
成功时 pytest 返回 0；依赖/配置错误、失败断言或工具缺失返回非零，保留原始错误。
不要把 pytest summary 的通过当作业务验收，也不要忽略早期环境检查的失败。
重复运行会新建目录，不复用旧库；不要自行向 pytest 传入指向既有目录的 `--basetemp`
（pytest 会清理其内容）。

清理：停止 PoC 后，确认 `realpath var/m00/poc.<本次随机后缀>` 位于项目 `var/m00/`，
只删除该次已确认的实验目录；保留待回传证据，禁止通配删除、git clean 或删除业务库。
`.venv/` 可单独重新创建；七份设计、Git 历史不属于清理对象。

回传：准确 commit、OS/架构/文件系统、环境报告及退出码、安装步骤、候选 lock、
PoC 日志/JUnit/退出码和失败观察。先去掉凭据、私有包源、用户名/工作区路径等个人信息，
不要发送 `.env`、Token、真实员工资料或任何生产库。所有运行产物继续留在 Git 忽略目录。
