import type { Profile } from './api';
export interface PagePolicy {path:string;label:string;group:string;visible:(profile:Profile)=>boolean}
export const hasRole=(p:Profile|null,role:string)=>!!p?.roles.includes(role);
export const employed=(p:Profile|null)=>!!p?.employee_id&&p.employment_valid!==false;
export const isHR=(p:Profile|null)=>hasRole(p,'HR')&&employed(p);
export const selfService=(p:Profile|null)=>employed(p)&&['EMPLOYEE','MANAGER','HR'].some(r=>hasRole(p,r));
export const pages:PagePolicy[]=[
 {path:'/',label:'工作台',group:'',visible:()=>true},
 {path:'/departments',label:'部门管理',group:'组织人事',visible:p=>isHR(p)||hasRole(p,'ADMIN')},
 {path:'/positions',label:'职位管理',group:'组织人事',visible:p=>isHR(p)||hasRole(p,'ADMIN')},
 {path:'/employees',label:'员工档案',group:'组织人事',visible:p=>isHR(p)||(hasRole(p,'MANAGER')&&employed(p))},
 {path:'/attendance',label:'考勤管理',group:'考勤与请假',visible:selfService},
 {path:'/leaves',label:'请假管理',group:'考勤与请假',visible:selfService},
 {path:'/approvals',label:'直属部门审批',group:'考勤与请假',visible:p=>hasRole(p,'MANAGER')&&employed(p)},
 {path:'/salaries',label:'薪资管理',group:'薪资管理',visible:selfService},
 {path:'/dashboard',label:'数据看板',group:'统计分析',visible:selfService},
 {path:'/users',label:'用户管理与审计',group:'系统管理',visible:p=>hasRole(p,'ADMIN')},
];
export const utilityPages:PagePolicy[]=[{path:'/settings',label:'个人设置',group:'',visible:()=>true}];
export const allPages=[...pages,...utilityPages];
export const visiblePages=(p:Profile|null)=>p&&!p.must_change_password?pages.filter(page=>page.visible(p)):[];
export const canAccess=(path:string,p:Profile|null)=>!!p&&!p.must_change_password&&!!allPages.find(page=>page.path===path)?.visible(p);
export const cacheNames:Record<string,string>={'/settings':'Settings','/':'Home','/departments':'Departments','/positions':'Positions','/employees':'Employees','/attendance':'Attendance','/leaves':'Leaves','/approvals':'Approvals','/salaries':'Salaries','/dashboard':'Dashboard','/users':'Users'};
