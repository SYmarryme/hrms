"""Bounded, all-or-nothing employee file imports and scoped, formula-safe exports."""
import csv
import io
import zipfile
import re
import posixpath
from collections import Counter
from datetime import date, datetime
from uuid import UUID

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from pydantic import ValidationError
from sqlalchemy import select
from backend.auth import AuthError
from backend.course import EmployeeInput, values, T, SHANGHAI
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError
from openpyxl.utils.exceptions import InvalidFileException
from defusedxml.ElementTree import fromstring

COLUMNS = ['employee_no', 'full_name', 'department_id', 'position_id', 'hire_date', 'employment_status']
BUSINESS_COLUMNS = ['员工工号', '姓名', '所属部门', '所属职位', '入职日期', '员工状态']
STATES = {'待入职':'PRE_HIRE', '试用':'PROBATION', '在职':'ACTIVE', '离职办理中':'EXIT_PROCESSING'}
OPTION_SHEET = '业务选项'
MAX_BYTES = 2 * 1024 * 1024


class ImportIssue(ValueError):
    def __init__(self, field, code, message, row=1):
        self.detail = {'row':row, 'field':field, 'code':code, 'message':message}


def reference_catalogue(session):
    departments = [dict(row) for row in session.execute(select(T['departments']).order_by(T['departments'].c.code)).mappings()]
    positions = [dict(row) for row in session.execute(select(T['positions']).order_by(T['positions'].c.department_id,T['positions'].c.code)).mappings()]
    return departments, positions


def option_labels(rows, keys):
    """Names first, stable business keys for duplicate/ambiguous names; never database IDs."""
    counts = Counter(row['name'] for row in rows)
    codes = Counter(row['code'] for row in rows)
    labels = {}
    for row in rows:
        collision = codes[row['name']] > (1 if row['code']==row['name'] else 0)
        labels[row['id']] = (row['name'] if counts[row['name']] == 1 and not collision
                             else row['name'] + '【' + ' / '.join(keys(row)) + '】')
    # Unusual business names may themselves contain the bracket syntax. JSON labels
    # are an injective fallback using only name and business codes, with no ID exposure.
    owners={}
    for row in rows:
        for value in (row['name'],row['code']):owners.setdefault(value,set()).add(row['id'])
    collisions=any(owners.get(labels[row['id']],set())-{row['id']} for row in rows)
    if len(set(labels.values())) != len(labels) or collisions:
        import json
        reserved_values=set(owners)
        labels={}
        used=set()
        for row in rows:
            candidate=row['name']+'【编号 '+json.dumps(keys(row),ensure_ascii=False)+'】'
            while candidate in reserved_values or candidate in used:candidate+='（业务选项）'
            labels[row['id']]=candidate
            used.add(candidate)
    return labels


def template_employees(session, kind):
    if kind == 'csv':
        return encode_sheet([BUSINESS_COLUMNS], kind)
    departments, positions = reference_catalogue(session)
    enabled = {row['id']:row for row in departments if row['status'] == 'ACTIVE'}
    current_positions = [row for row in positions if row['status'] == 'ACTIVE' and row['department_id'] in enabled]
    # Build labels from ALL records so a disabled homonym cannot change their meaning.
    dep_codes = {row['id']:row['code'] for row in departments}
    dep_labels = option_labels(departments, lambda row:[row['code']])
    pos_labels = option_labels(positions, lambda row:[dep_codes[row['department_id']], row['code']])
    book = Workbook(); sheet = book.active; sheet.title = '员工导入'
    sheet.append(BUSINESS_COLUMNS); sheet.freeze_panes = 'A2'; sheet.auto_filter.ref = 'A1:F101'
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='245BD1')
    for column, width in zip('ABCDEF', (22,22,38,48,18,20)):
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2,max_row=101,max_col=6):
        for cell in row: cell.number_format = 'yyyy-mm-dd' if cell.column == 5 else '@'
    notes = {'A1':'最多100名员工；工号按文本填写，保留前导零。',
             'C1':'请选择已启用部门。CSV可填部门编号或唯一名称；重名请使用业务选项中的完整选项。',
             'D1':'请选择属于该部门的已启用职位；所有选择仍由服务器重新校验。请参阅业务选项中的所属部门编号。',
             'E1':'填写有效日期，格式 YYYY-MM-DD；在职员工入职日不能在未来。',
             'F1':'待入职、试用、在职、离职办理中；离职请使用系统归档操作。'}
    for coordinate, note in notes.items(): sheet[coordinate].comment = Comment(note, 'HRMS')
    reference = book.create_sheet(OPTION_SHEET)
    reference.append(['部门选项','部门编号','职位选项','职位所属部门编号','职位编号','员工状态'])
    reference.freeze_panes = 'A2'
    for column, width in zip('ABCDEF',(38,22,48,24,22,20)): reference.column_dimensions[column].width=width
    for number, row in enumerate(enabled.values(),2):
        for column, value in ((1,dep_labels[row['id']]), (2,row['code'])):
            cell=reference.cell(number,column,value);cell.data_type='s'
    for number, row in enumerate(current_positions,2):
        for column, value in ((3,pos_labels[row['id']]),(4,dep_codes[row['department_id']]),(5,row['code'])):
            cell=reference.cell(number,column,value);cell.data_type='s'
    for number, state in enumerate(STATES,2): reference.cell(number,6,state)
    # Named ranges avoid Excel's 255-character inline-list limit; no formulas from user data.
    for name, column, count, target in [('HRMS_Departments','A',len(enabled),'C'),
            ('HRMS_Positions','C',len(current_positions),'D'),('HRMS_EmployeeStates','F',len(STATES),'F')]:
        book.defined_names.add(DefinedName(name,attr_text=f"'{OPTION_SHEET}'!${column}$2:${column}${max(2,count+1)}"))
        validation=DataValidation(type='list',formula1=name,allow_blank=True,showDropDown=False,showErrorMessage=True,
            errorStyle='stop',errorTitle='请选择有效业务选项',error='请从列表选择，填写后仍须服务端预检。',
            showInputMessage=True,promptTitle='员工导入',prompt='每条员工行可选择；职位必须属于所选部门。')
        sheet.add_data_validation(validation);validation.add(f'{target}2:{target}101')
    stream=io.BytesIO();book.save(stream);book.close()
    return stream.getvalue()


def media(kind):
    return 'text/csv; charset=utf-8' if kind == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def safe_cell(value):
    value = str(value) if value is not None else ''
    if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


def encode_sheet(rows, kind):
    if kind == 'csv':
        stream = io.StringIO(newline=''); writer = csv.writer(stream)
        writer.writerows([[safe_cell(v) for v in row] for row in rows])
        return stream.getvalue().encode('utf-8-sig')
    book = Workbook(); sheet = book.active; sheet.title = 'employees'
    for row in rows:
        sheet.append([safe_cell(v) for v in row])
    stream = io.BytesIO(); book.save(stream); book.close()
    return stream.getvalue()


def data_sheet_path(archive):
    namespace = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    sheets=fromstring(archive.read('xl/workbook.xml')).findall('m:sheets/m:sheet',namespace)
    if not sheets or len(sheets)>2 or sheets[0].get('state','visible')!='visible':
        raise ValueError('employee worksheet required')
    if len(sheets)==2 and (sheets[0].get('name')!='员工导入' or sheets[1].get('name')!=OPTION_SHEET):
        raise ValueError('only the template reference worksheet is accepted')
    relations=list(fromstring(archive.read('xl/_rels/workbook.xml.rels')))
    if len({entry.get('Id') for entry in relations})!=len(relations):raise ValueError('duplicate worksheet relationship')
    paths=[]
    for sheet in sheets:
        relation=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        if not relation:raise ValueError('missing worksheet relationship ID')
        entries=[entry for entry in relations if entry.get('Id')==relation]
        if len(entries)!=1:raise ValueError('missing worksheet relationship')
        for entry in entries:
            target=entry.get('Target','')
            path=posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
            if (entry.get('TargetMode')=='External' or entry.get('Type')!='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet'
                    or not path.startswith('xl/worksheets/') or not path.endswith('.xml') or path not in archive.namelist()):
                raise ValueError('invalid employee worksheet relationship')
            paths.append(path)
    if len(set(paths))!=len(paths):raise ValueError('shared worksheet target')
    return paths[0], [sheet.get('name') for sheet in sheets]


def decode_sheet(content, kind):
    if not content or len(content) > MAX_BYTES:
        raise ValueError('file size')
    if kind == 'csv':
        rows = list(csv.reader(io.StringIO(content.decode('utf-8-sig')), strict=True))
    else:
        # Refuse zip bombs, macros, external links and formulas before data-only interpretation.
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if len(archive.infolist()) > 100 or sum(info.file_size for info in archive.infolist()) > 10 * MAX_BYTES:
                raise ValueError('expanded workbook too large')
            if any('vbaProject' in name or 'externalLinks/' in name for name in archive.namelist()):
                raise ValueError('active workbook content')
            main_path,expected_names=data_sheet_path(archive)
            for name in archive.namelist():
                if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                    for element in fromstring(archive.read(name)).iter():
                        if element.tag.endswith('}f'):
                            raise ImportIssue('文件','FORMULA_NOT_ALLOWED','文件不得包含公式单元格')
                        if name==main_path and element.tag.endswith('}c'):
                            reference=element.get('r','')
                            match=re.fullmatch(r'([A-Z]+)([1-9]\d*)',reference)
                            if not match or match[1] not in tuple('ABCDEF'):
                                raise ImportIssue('文件','INVALID_FILE_COLUMNS','员工表仅接受模板的六列',int(match[2]) if match else 1)
                            if int(match[2])>101:
                                raise ImportIssue('文件','ROW_LIMIT_EXCEEDED','员工录入范围为第2至101行，最多100名员工',int(match[2]))
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            if [sheet.title for sheet in book.worksheets]!=expected_names or book.worksheets[0].sheet_state!='visible':
                raise ValueError('employee worksheet identity mismatch')
            sheet = book.worksheets[0]
            sheet.reset_dimensions()  # Ignore attacker-controlled dimension metadata; inspect actual cells.
            rows = []
            for cells in sheet.iter_rows(max_row=102, max_col=7):
                if any(cell.data_type == 'f' for cell in cells): raise ValueError('formula cell')
                if cells[6].value is not None: raise ValueError('extra column')
                rows.append([cell.value for cell in cells[:6]])
            while rows and all(value is None for value in rows[-1]): rows.pop()
            if len(rows)>101: raise ValueError('row count')
        finally:
            book.close()
    if not rows or rows[0] not in (COLUMNS,BUSINESS_COLUMNS):
        raise ImportIssue('表头','INVALID_FILE_COLUMNS','请使用中文员工模板的六列表头，或完整保留旧版六列格式')
    if not 1 <= len(rows)-1 <= 100 or not any(any(value not in (None,'') for value in row) for row in rows[1:]):
        raise ImportIssue('文件','INVALID_ROW_COUNT','请填写1至100名员工；不要修改员工录入范围')
    return rows[0],rows[1:]


def resolve_reference(value, rows, labels, field, prefix, department_id=None, legacy=False):
    if not isinstance(value,str) or not value.strip():
        raise ImportIssue(field,prefix+'_REQUIRED',field+'不能为空，请填写编号或选择业务选项')
    value=value.strip()
    if legacy:
        try: value=str(UUID(value))
        except ValueError: raise ImportIssue(field,prefix+'_NOT_FOUND','旧版'+field+'必须是有效数据库ID，请改用中文模板填写业务选项')
        matches=[row for row in rows if row['id']==value]
    else:
        matches=[row for row in rows if value in (row['name'],row['code'],labels[row['id']])]
        if department_id is not None:
            scoped=[row for row in matches if row['department_id']==department_id]
            if not scoped and matches:
                raise ImportIssue(field,'POSITION_DEPARTMENT_MISMATCH','所属职位不属于所选部门，请核对职位所属部门编号')
            matches=scoped
    if not matches:
        raise ImportIssue(field,prefix+'_NOT_FOUND',field+'不存在，请核对业务编号或重新下载模板')
    if len(matches)>1:
        raise ImportIssue(field,'AMBIGUOUS_'+prefix,field+'名称或编号存在歧义，请选择附带业务编号的完整选项')
    row=matches[0]
    if row['status']!='ACTIVE':
        raise ImportIssue(field,prefix+'_DISABLED',field+'已停用，请重新选择已启用选项')
    if department_id is not None and row['department_id']!=department_id:
        raise ImportIssue(field,'POSITION_DEPARTMENT_MISMATCH','所属职位不属于所选部门，请核对职位所属部门编号')
    return row['id']


def import_employees(service, session, now, content, kind, mode):
    try:
        columns,rows = decode_sheet(content, kind)
    except ImportIssue as error:
        return {'valid':False,'errors':[error.detail],'imported':0}
    except (ValueError, UnicodeError, zipfile.BadZipFile, csv.Error, KeyError, TypeError, OSError, ParseError, DefusedXmlException, InvalidFileException):
        return {'valid': False, 'errors': [{'row':1,'field':'文件','code':'INVALID_FILE_TEMPLATE',
            'message':'文件格式无效，请使用UTF-8 CSV或未含宏、外部链接及公式的XLSX模板'}], 'imported': 0}
    departments,positions=reference_catalogue(session)
    dep_codes={row['id']:row['code'] for row in departments}
    dep_labels=option_labels(departments,lambda row:[row['code']])
    pos_labels=option_labels(positions,lambda row:[dep_codes[row['department_id']],row['code']])
    legacy=columns==COLUMNS
    prepared, errors, seen = [], [], set()
    for number, row in enumerate(rows, 2):
        if all(value in (None,'') for value in row):continue
        try:
            if len(row) != len(COLUMNS):
                raise ImportIssue('文件','INVALID_FILE_COLUMNS','该行必须包含模板的六列')
            data = dict(zip(COLUMNS,row))
            department_id=resolve_reference(data['department_id'],departments,dep_labels,'所属部门','DEPARTMENT',legacy=legacy)
            position_id=resolve_reference(data['position_id'],positions,pos_labels,'所属职位','POSITION',department_id,legacy)
            hire_date=data['hire_date']
            if isinstance(hire_date,datetime):
                if hire_date.time()!=datetime.min.time():
                    raise ImportIssue('入职日期','INVALID_HIRE_DATE','入职日期只能包含日期，不能包含时分秒')
                hire_date=hire_date.date()
            if isinstance(hire_date,date):hire_date=hire_date.isoformat()
            if not isinstance(hire_date,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',hire_date):
                raise ImportIssue('入职日期','INVALID_HIRE_DATE','入职日期须为有效的YYYY-MM-DD日期')
            try:date.fromisoformat(hire_date)
            except ValueError:raise ImportIssue('入职日期','INVALID_HIRE_DATE','入职日期不是有效日历日期，请核对年月日')
            state=data['employment_status']
            state=STATES.get(state,state) if isinstance(state,str) else state
            if state not in STATES.values():
                raise ImportIssue('员工状态','INVALID_EMPLOYEE_STATUS','员工状态请选择待入职、试用、在职或离职办理中；离职请使用归档操作')
            payload = EmployeeInput(employee_no=data['employee_no'], full_name=data['full_name'], current_department_id=department_id,
                current_position_id=position_id, hire_date=hire_date, employment_status=state)
            item = values(payload)
            service.active_position(session, item['current_department_id'], item['current_position_id'])
            if item['employment_status'] in ('ACTIVE','PROBATION','EXIT_PROCESSING') and item['hire_date'] > now.astimezone(SHANGHAI).date():
                raise ImportIssue('入职日期','FUTURE_HIRE_DATE','在职员工入职日期不能在未来；尚未入职请选择待入职')
            if item['employee_no'] in seen or session.execute(select(T['employees'].c.id).where(T['employees'].c.employee_no == item['employee_no'])).first():
                raise ImportIssue('员工工号','DUPLICATE_EMPLOYEE_NO','员工工号在本文件中重复或已存在，请使用唯一工号')
            seen.add(item['employee_no']); prepared.append(item)
        except ImportIssue as error:
            errors.append({**error.detail,'row':number})
        except ValidationError as error:
            fields={'employee_no':'员工工号','full_name':'姓名','hire_date':'入职日期','employment_status':'员工状态'}
            for issue in error.errors(include_input=False):
                field=fields.get(issue['loc'][0],'字段')
                errors.append({'row':number,'field':field,'code':'INVALID_EMPLOYEE_FIELD','message':field+'格式或长度不正确，请按模板填写有效文本'})
        except (ValueError,TypeError,AuthError):
            errors.append({'row':number,'field':'员工','code':'INVALID_EMPLOYEE_FIELD','message':'员工字段或部门职位归属无效，请按模板核对'})
    if errors:
        return {'valid':False, 'errors':errors, 'imported':0}
    if mode == 'commit':
        for item in prepared: service.save_employee(session, now, item)
    return {'valid':True, 'errors':[], 'count':len(prepared), 'imported':len(prepared) if mode == 'commit' else 0}


def export_employees(service, session, principal, q, kind):
    table = T['employees']; cond = [service.employee_scope(session, principal)]
    if q:
        from sqlalchemy import or_
        cond.append(or_(table.c.full_name.contains(q, autoescape=True), table.c.employee_no.contains(q, autoescape=True)))
    rows = session.execute(select(table).where(*cond).order_by(table.c.employee_no)).mappings()
    data = [COLUMNS]
    for row in rows:
        data.append([row['employee_no'],row['full_name'],row['current_department_id'],row['current_position_id'],
                     row['hire_date'].isoformat() if row['hire_date'] else '',row['employment_status']])
    return encode_sheet(data, kind)
