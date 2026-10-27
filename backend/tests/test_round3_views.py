from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy import update
from backend.models import metadata
from test_course import course


def submit(client,headers,day,kind='ANNUAL'):
    response=client.post('/api/v1/leaves',headers=headers,json={'start_date':day,'end_date':day,'leave_type':kind,'reason':'虚构个人统计测试'})
    status=response.status_code
    assert status==201
    return response.json()['data']


def test_personal_summary_covers_all_pages_and_is_independent_of_filters(course):
    _,client,_,h,_=course
    day=date(2040,1,2);own=[]
    for i in range(26):
        while day.weekday()>4:day+=timedelta(days=1)
        own.append(submit(client,h['employee'],str(day),'SICK' if i==0 else 'ANNUAL'));day+=timedelta(days=1)
    for item,state in [(own[0],'APPROVED'),(own[1],'REJECTED')]:
        response=client.post('/api/v1/leaves/'+item['id']+'/decision',headers={**h['manager'],'If-Match':'"v1"'},json={'status':state,'opinion':'虚构审批'})
        status=response.status_code;assert status==200
    response=client.post('/api/v1/leaves/'+own[2]['id']+'/cancel',headers={**h['employee'],'If-Match':'"v1"'},json={})
    status=response.status_code;assert status==200
    submit(client,h['hr'],'2041-01-01')
    first=client.get('/api/v1/leaves?page_size=20',headers=h['employee']).json()['data']
    assert first['total']==26 and len(first['items'])==20
    assert first['summary']=={'month':'2026-10','submitted_this_month':26,'pending':23,'approved':1,'rejected':1}
    filtered=client.get('/api/v1/leaves?status=APPROVED&leave_type=SICK&submitted_from=2026-10-01&submitted_to=2026-10-31&page_size=1',headers=h['employee']).json()['data']
    assert filtered['total']==1 and filtered['items'][0]['id']==own[0]['id']
    assert filtered['summary']==first['summary']
    second=client.get('/api/v1/leaves?page=2&page_size=20',headers=h['employee']).json()['data']
    assert len(second['items'])==6 and second['summary']==first['summary']


@pytest.mark.parametrize('role',['employee','manager','hr'])
def test_advanced_roles_do_not_widen_personal_leaves_or_summary(course,role):
    _,client,_,h,profiles=course
    for actor,day in [('employee','2040-01-02'),('manager','2040-01-03'),('hr','2040-01-04')]:submit(client,h[actor],day)
    data=client.get('/api/v1/leaves?employee_id='+profiles['employee']['employee_id'],headers=h[role]).json()['data']
    assert data['total']==1 and data['items'][0]['employee_id']==profiles[role]['employee_id']
    assert data['summary']['submitted_this_month']==1 and data['summary']['pending']==1
    approvals=client.get('/api/v1/leaves?scope=approval',headers=h['manager']).json()['data']
    assert approvals['total']==2 and 'summary' not in approvals
    assert all(row['employee_id']!=profiles['manager']['employee_id'] for row in approvals['items'])
    status=client.get('/api/v1/leaves',headers=h['admin']).status_code;assert status==403
    status=client.get('/api/v1/leaves').status_code;assert status==401


def test_submission_month_uses_shanghai_midnight_and_cancelled_is_not_rejected(course):
    app,client,_,h,_=course
    before=submit(client,h['employee'],'2040-01-02');after=submit(client,h['employee'],'2040-01-03')
    with app.state.database.transaction(write=True) as session:
        table=metadata.tables['course_leaves']
        session.execute(update(table).where(table.c.id==before['id']).values(created_at=datetime(2026,9,30,15,59,59,tzinfo=timezone.utc)))
        session.execute(update(table).where(table.c.id==after['id']).values(created_at=datetime(2026,9,30,16,0,0,tzinfo=timezone.utc)))
    response=client.post('/api/v1/leaves/'+after['id']+'/cancel',headers={**h['employee'],'If-Match':'"v1"'},json={})
    status=response.status_code;assert status==200
    data=client.get('/api/v1/leaves',headers=h['employee']).json()['data']
    assert data['summary']=={'month':'2026-10','submitted_this_month':1,'pending':1,'approved':0,'rejected':0}
    day=client.get('/api/v1/leaves?submitted_from=2026-10-01&submitted_to=2026-10-01',headers=h['employee']).json()['data']
    assert day['total']==1 and day['items'][0]['id']==after['id']


@pytest.mark.parametrize('query',['status=UNKNOWN','leave_type=MARRIAGE','submitted_from=2026-10-02&submitted_to=2026-10-01'])
def test_leave_filter_validation(course,query):
    _,client,_,h,_=course
    status=client.get('/api/v1/leaves?'+query,headers=h['employee']).status_code
    assert status==422


def test_dashboard_retains_hr_company_scope_and_chronological_exact_salary_totals(course):
    _,client,_,h,profiles=course
    for month,amount in [('2026-05','0.00'),('2026-10','1234.56')]:
        response=client.put('/api/v1/salaries',headers=h['hr'],json={'employee_id':profiles['employee']['employee_id'],'month':month,'amount':amount})
        status=response.status_code;assert status==200
    hr=client.get('/api/v1/dashboard?month=2026-10',headers=h['hr']).json()['data']
    own=client.get('/api/v1/dashboard?month=2026-10',headers=h['employee']).json()['data']
    assert hr['employee_count']==3 and own['employee_count']==1
    assert hr['attendance']['expected_days']==3*own['attendance']['expected_days']
    assert [row['month'] for row in hr['salary_trend']]==['2026-05','2026-06','2026-07','2026-08','2026-09','2026-10']
    assert hr['salary_trend'][0]['amount']=='0.00' and hr['salary_trend'][-1]['amount']=='1234.56'
    for role in ['employee','manager']:
        assert 'salary_trend' not in client.get('/api/v1/dashboard?month=2026-10',headers=h[role]).json()['data']
    status=client.get('/api/v1/dashboard?month=2026-10',headers=h['admin']).status_code;assert status==403


def test_current_submission_month_rolls_at_server_shanghai_midnight(course):
    _,client,clock,h,_=course
    # Real session activity keeps the existing idle policy intact while the test clock advances.
    for _ in range(5):
        clock.advance(hours=23)
        status=client.get('/api/v1/auth/me',headers=h['employee']).status_code;assert status==200
    clock.value=datetime(2026,10,31,15,59,tzinfo=timezone.utc)
    submit(client,h['employee'],'2051-01-02')
    before=client.get('/api/v1/leaves',headers=h['employee']).json()['data']['summary']
    assert before['month']=='2026-10' and before['submitted_this_month']==1
    clock.advance(minutes=2)
    submit(client,h['employee'],'2051-01-03')
    after=client.get('/api/v1/leaves',headers=h['employee']).json()['data']['summary']
    assert after['month']=='2026-11' and after['submitted_this_month']==1 and after['pending']==2
