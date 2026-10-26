"""Malformed workbook relationships must not redirect imports to reference sheets."""
import io
import zipfile
import pytest
from openpyxl import Workbook
from backend.course_files import decode_sheet, option_labels, resolve_reference


def test_missing_data_sheet_cannot_import_hidden_reference_rows():
    book=Workbook();book.active.title='员工导入';reference=book.create_sheet('业务选项');reference.sheet_state='hidden'
    reference.append(['employee_no','full_name','department_id','position_id','hire_date','employment_status'])
    reference.append(['SHOULD-NOT-IMPORT','虚构','invalid','invalid','2026-01-01','ACTIVE'])
    reference['H2']='unexpected';reference['A103']='ignored-invalid-row'
    content=io.BytesIO();book.save(content);output=io.BytesIO()
    with zipfile.ZipFile(content) as source,zipfile.ZipFile(output,'w') as target:
        for info in source.infolist():
            raw=source.read(info.filename)
            if info.filename=='xl/_rels/workbook.xml.rels':raw=raw.replace(b'/xl/worksheets/sheet1.xml',b'/xl/worksheets/missing.xml')
            target.writestr(info,raw)
    with pytest.raises(ValueError):decode_sheet(output.getvalue(),'xlsx')


@pytest.mark.parametrize('kind',['department','position'])
def test_generated_options_never_collide_with_business_codes(kind):
    rows=[{'id':'first','name':'研发','code':'A','status':'ACTIVE','department_id':'dep'},
          {'id':'second','name':'研发','code':'B','status':'ACTIVE','department_id':'dep'},
          {'id':'third','name':'第三部门','code':'研发【A】' if kind=='department' else '研发【D / A】',
           'status':'ACTIVE','department_id':'dep'}]
    keys=(lambda row:[row['code']]) if kind=='department' else (lambda row:['D',row['code']])
    labels=option_labels(rows,keys)
    for row in rows:
        actual=resolve_reference(labels[row['id']],rows,labels,'所属部门' if kind=='department' else '所属职位',
            kind.upper(),None if kind=='department' else 'dep')
        assert actual==row['id']
