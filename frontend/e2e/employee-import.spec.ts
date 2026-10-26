import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';

test('HR downloads Chinese XLSX, sees a precise failed row, and imports the corrected batch',async({page})=>{
  const credentials:Record<string,string>=JSON.parse(process.env.HRMS_E2E_PASSWORDS||'{}');
  test.skip(!credentials.hr,'Run through scripts/e2e_local.py for an independent fictional database');
  await page.goto('/login');await page.getByLabel('账号',{exact:true}).fill('fixture-hr');
  await page.getByLabel('密码',{exact:true}).fill(credentials.hr);await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByRole('navigation',{name:'业务菜单'}).getByRole('link',{name:'员工档案',exact:true}).click();
  await expect(page.getByText(/无需查询数据库ID/)).toBeVisible();
  const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'下载 XLSX 模板',exact:true}).click();
  const file=await (await downloadEvent).path();if(!file)throw new Error('Template download unavailable');
  const folder=path.resolve('..','var','mvp','employee-import-e2e');await fs.mkdir(folder,{recursive:true});
  const bad=path.join(folder,'invalid.xlsx'),fixed=path.join(folder,'corrected.xlsx');
  const python=path.resolve('..','var','mvp','venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  execFileSync(python,['-c',`
import sys
from openpyxl import load_workbook
book=load_workbook(open(sys.argv[1],'rb'));sheet=book.worksheets[0];reference=book['业务选项']
assert [c.value for c in sheet[1]]==['员工工号','姓名','所属部门','所属职位','入职日期','员工状态']
position=reference['C2'].value;department_code=reference['D2'].value
department=next(row[0] for row in reference.iter_rows(min_row=2,values_only=True) if row[1]==department_code)
for number,code,day in [(2,'XLSX-UI-GOOD','2026-01-01'),(3,'XLSX-UI-FIXED','2026-02-30')]:
    for column,value in enumerate([code,'虚构中文模板员工',department,position,day,'在职'],1):sheet.cell(number,column,value)
book.save(sys.argv[2]);sheet['E3']='2026-01-02';book.save(sys.argv[3])
`,file,bad,fixed]);
  await page.getByRole('button',{name:'导入',exact:true}).click();await page.getByLabel('选择模板文件',{exact:true}).setInputFiles(bad);
  await page.getByRole('button',{name:'预检文件',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('第 3 行 · 入职日期');
  await expect(page.getByRole('alert')).toContainText('入职日期不是有效日历日期');
  await expect(page.getByRole('dialog',{name:'员工文件导入'}).getByRole('button',{name:'导入',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'关闭弹窗'}).click();await page.getByRole('dialog',{name:'放弃未保存修改'}).getByRole('button',{name:'放弃修改'}).click();await page.getByLabel('工号 / 姓名',{exact:true}).fill('XLSX-UI-');await page.getByRole('button',{name:'查询',exact:true}).click();
  await expect(page.getByText('暂无员工数据',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'导入',exact:true}).click();await page.getByLabel('选择模板文件',{exact:true}).setInputFiles(fixed);
  await page.getByRole('button',{name:'预检文件',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'员工文件导入'}).getByRole('button',{name:'导入',exact:true})).toBeEnabled();
  await page.getByRole('dialog',{name:'员工文件导入'}).getByRole('button',{name:'导入',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'已原子导入 2 名员工'})).toBeVisible();
  await expect(page.getByRole('row').filter({hasText:'XLSX-UI-GOOD'})).toBeVisible();
  await expect(page.getByRole('row').filter({hasText:'XLSX-UI-FIXED'})).toBeVisible();
});
