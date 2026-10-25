# 第一批正式应用：登录与系统主页

本批交付代码入口为 backend/ 与 frontend/，不是 experiments 中的合成 PoC。
Windows 仅编写/静态检查；安装、迁移、自动化测试、构建与真实页面操作均由用户在 Ubuntu 执行。
登录基线 ba59a4d 已由用户回传 Ubuntu 安装/迁移/首位ADMIN、测试退出0和 Edge 登录/主页/退出/刷新重新登录通过。
本批新增部门功能及扩展回归仍为 NOT_RUN，详见[部门说明](departments.md)。CloudStudio公网部署仍为可选目标。

## 已实现范围

- Argon2id 密码、不透明服务器随机 Bearer、数据库仅存摘要；登录、/auth/me、退出。
- 30 天固定绝对期限、24 小时空闲、最多 5 个有效会话；第六次原子撤销最早有效会话；
  last_seen_at 至少间隔 5 分钟才更新，NULL 使用 created_at。UTC 服务器时钟，绝不滚动延长 expires_at。
- 受控本地 CLI 首次 ADMIN，唯一成功审计标记与账号/角色同事务；无默认密码，无公开注册/初始化 API。
- 受控 CLI 重置密码会撤销该账号全部旧会话。自助改密页面/HTTP 端点本批未实现。
- /me 只读取会话本人，账号停用/离职即时拒绝，角色按数据库当前有效期/撤销状态重新查询。
  主页不含工资/人事对象查询；角色列表不赋予任意业务权限。后续业务接口仍须各自执行后端动作/对象/范围/字段授权。
- 401 表示凭据缺失/无效，403 表示来源等访问策略拒绝；前端分别处理。页面路由守卫不代替后端验证。
- Token 仅在请求模块私有内存，刷新/新标签重新登录；无 JWT、refresh、Cookie 回退或持久化插件。

为满足 DB-01 的真实 FK 闭包，首迁移建立 13 张批准表：departments、positions、employees、
employee_assignments、employee_lifecycle_events、approval_cases、management_appointment_proposal_versions、
users、roles、role_assignments、auth_sessions、audit_events、outbox_events。
组织/员工/审批相关表目前仅是引用基础结构，没有对应业务接口、种子员工或业务功能；不声称完成全部54表。
初始迁移使用独立不可变schema_v1快照，后续变更须另建Alembic版本。启动不建表、不迁移、不初始化管理员。
现存非版本化数据库拒绝自动收编；初始身份/审计不提供破坏式降级命令。

依据最新明确指令，正式应用采用 Bearer；旧私密文档的 Cookie/CSRF 载体与本批认证方式的差异已明确，
本批以用户最新约束为准，不修改七份原文或擅自改业务权限。新整合候选全文仍不冒充已签收基线。
M00/T-004 历史通过和失败证据完整保留；其云端部署项不再作为本批功能的前置 Gate。

## Ubuntu 最少命令

项目根目录运行。先停止由旧 PoC 启动器启动的服务，释放3000/8000；不要杀其他进程或清空旧数据库。

```bash
git pull --ff-only origin main
bash scripts/core/setup.sh
var/core/venv/bin/python -m alembic -c backend/alembic.ini upgrade head
read -r -p '首次管理员账号（无默认账号）: ' HRMS_ADMIN_USERNAME
var/core/venv/bin/python -m backend.cli init-admin --username "$HRMS_ADMIN_USERNAME"
```

CLI 必须在私密交互终端输入两次12–128字符新密码，不回显，不用命令行/环境变量传密码。
每步退出0再继续；第二次初始化应拒绝，不能删除审计标记重建。默认数据在 var/hrms/app.sqlite3，
与M00实验库独立；可显式 export HRMS_DATABASE_PATH=/受控绝对路径/app.sqlite3，但不得放入frontend。

```bash
bash scripts/core/test.sh
read -r -p '实际3000 HTTPS origin（Ubuntu本机开发可填http://127.0.0.1:3000）: ' HRMS_PUBLIC_ORIGIN
export HRMS_PUBLIC_ORIGIN
bash scripts/core/start.sh
```

start保持前台；仅后端127.0.0.1:8000、前端0.0.0.0:3000，精确Host校验不关闭。
CloudStudio作为可选运行方式时，只将3000设公开，8000保持“仅自己可见”；所有者预览例外不替代应用鉴权。
core环境在var/core/venv，不修改原.venv/M00锁；依赖声明是待云端解析候选，未伪造传递依赖锁。
npm生成frontend/package-lock.json和安装版本快照，请保留供后续锁定；日志/报告在var/core，禁止公开提交。
不需要在Windows执行任何上述命令。公网预览若有平台问题，单独记录，不回到严格T-004流程。

受控本地重置密码（非公网端点，需拥有项目/数据库操作权限）：

```bash
var/core/venv/bin/python -m backend.cli reset-password --username "$HRMS_ADMIN_USERNAME"
```

## 测试与手工验证

后端用真实临时SQLite文件和Alembic，覆盖登录/me/logout、401/403、凭证不回显、无注册/PoC路由、
空闲和绝对期限、NULL回退、5分钟节流、第6次登录、并发登录、改密/停用、角色刷新、限流、
并发首次初始化、初始化及登录审计失败回滚、WAL/FK/迁移重复运行和审计不可修改。
前端测试覆盖私有内存、Bearer附加、Cookie省略、模块刷新、401/403及退出网络失败。
自动化测试与前端构建本地均NOT_RUN，运行后以实际退出码/报告为准。
登录基线定义24项后端测试与6项前端测试；本批部门扩展用例另计，运行结果不得沿用基线结论。
测试脚本还执行Vue/TypeScript类型检查；当前只做了静态语法核验，不能冒称类型检查或构建已通过。
当前限流以账号与实际socket peer各计数；Vite后的多个浏览器共享loopback peer，60次/分钟peer预算可能共享，
这是当前单进程可用性限制，不通过信任任意转发IP来规避；后续可信代理方案再独立审查。

用户手工：登录页错误密码→拒绝；正确密码→主页显示当前账号/角色；退出→登录页，旧会话不能再访问；
刷新/新标签→重新登录；CLI改密后所有旧页面请求失效；不查看/复制网络中的凭证或导出HAR。
若退出网络失败，客户端会清内存，但不能声称服务器已撤销，页面会明确提示。
这不是完整HRMS业务/生产上线或工资权限验收；部门已另批准备，员工和其他业务仍待后续。

上一轮被中断的5份T-004工具文件原样保留、未纳入本批提交，不再继续实现或执行。
