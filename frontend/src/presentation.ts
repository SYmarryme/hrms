export const employeeStates:Record<string,string>={PRE_HIRE:'待入职',PROBATION:'试用',ACTIVE:'在职',EXIT_PROCESSING:'离职办理中',TERMINATED:'已离职'};
export const roleNames:Record<string,string>={EMPLOYEE:'员工',MANAGER:'主管',HR:'人事',ADMIN:'系统管理员'};
export const rolesText=(roles:readonly string[])=>roles.map(role=>roleNames[role]||'授权角色').join('、');
export function stateLabel(value:string) { return employeeStates[value] || ({DISABLED:'停用',PENDING:'待审批',APPROVED:'已批准',REJECTED:'已驳回',CANCELLED:'已取消',SUCCESS:'成功',FAILURE:'失败'} as Record<string,string>)[value] || '未知状态'; }
export const enabledLabel=(value:string)=>value==='ACTIVE'?'启用':'停用';
export function formatBeijing(value:string|null|undefined) {
  if(!value)return '—';
  // SQLAlchemy SQLite datetimes are UTC; new API replies explicitly carry Z.
  const normalized=/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?$/.test(value)?value+'Z':value;
  if(!/(?:Z|[+-]\d\d:\d\d)$/.test(normalized))return '—';
  const date=new Date(normalized);if(Number.isNaN(date.getTime()))return '—';
  const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(date);
  const p=Object.fromEntries(parts.map(item=>[item.type,item.value]));return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`;
}
export const employeeLabel=(row:{employee_name?:string|null;employee_no?:string|null},fallback='本人')=>row.employee_name?`${row.employee_name}${row.employee_no?' · '+row.employee_no:''}`:fallback;
export const eventLabel=(code:string)=>({COURSE_EMPLOYEE_CREATE:'员工建档',COURSE_EMPLOYEE_EDIT:'档案修改',COURSE_TRANSFER:'组织调动',COURSE_TERMINATION:'离职归档'} as Record<string,string>)[code]||'员工信息变更';
const actions:Record<string,string>={'auth.login':'登录','auth.logout':'退出登录','system.bootstrap.complete':'身份初始化','course.fixture.initialize':'初始化资料',
 'identity.role.assign':'角色授权变更','identity.create':'创建账号','identity.password.reset':'重置密码','auth.password.reset':'重置密码','identity.hr.initialize':'首次HR授权',
 'org.department.create':'新增部门','org.department.update':'修改部门','position.create':'新增职位','position.update':'修改职位','employee.create':'新增员工',
 'employee.update':'修改员工','employee.transfer':'员工调动','employee.archive':'离职归档','employee.export':'导出员工','employee.import.commit':'导入员工',
 'employee.import.preflight':'员工导入预检','attendance.clock.in':'上班打卡','attendance.clock.out':'下班打卡','attendance.rule.create':'保存考勤规则',
 'leave.create':'提交请假','leave.cancel':'取消请假','leave.decision':'处理审批','salary.update':'修改薪资'};
export const actionLabel=(code:string)=>actions[code]||'业务操作';
