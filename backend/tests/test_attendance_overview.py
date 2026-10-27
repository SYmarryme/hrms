from datetime import datetime,timezone
from sqlalchemy import insert,update
from uuid import uuid4
from backend.models import metadata
from test_course import course

def test_attendance_overview_uses_exclusive_planned_days_and_unchanged_summary(course):
 app,client,clock,h,profiles=course
 eid=profiles['employee']['employee_id']
 # Mon Oct 26: not due at 08:59; one prior full day is both late and early.
 with app.state.database.transaction(write=True) as session:
  table=metadata.tables['course_attendance']
  for day,in_hour,out_hour in [(20,2,9),(21,1,10),(22,2,10),(23,1,9)]:
   incoming=datetime(2026,10,day,in_hour,0,tzinfo=timezone.utc)
   session.execute(insert(table).values(id=str(uuid4()),employee_id=eid,work_date=incoming.date(),clock_in_at=incoming,clock_out_at=incoming.replace(hour=out_hour),created_at=incoming,updated_at=incoming,version_no=1))
 data=client.get('/api/v1/attendance?month=2026-10',headers=h['employee']).json()['data']
 counts={row['name']:row['count'] for row in data['overview']['items']}
 assert data['overview']['total_days']==5
 assert counts=={'NORMAL':0,'LATE':0,'EARLY':0,'LATE_EARLY':0,'MISSING':0,'APPROVED_LEAVE':0,'IN_PROGRESS':1,'UPCOMING':4}
 # Fixture hire date is Oct 26: out-of-employment records must not enter the overview.
 assert data['summary']['planned_days']==5 and data['summary']['expected_days']==5
 assert data['summary']['complete_days']==0
 status=client.get('/api/v1/attendance?month=2026-10&employee_id='+eid,headers=h['manager']).status_code
 assert status==403


def test_overlap_leave_future_and_not_due_days_are_counted_once(course):
 app,client,clock,h,profiles=course
 eid=profiles['employee']['employee_id']
 with app.state.database.transaction(write=True) as session:
  session.execute(update(metadata.tables['employees']).where(metadata.tables['employees'].c.id==eid).values(hire_date=datetime(2026,10,1).date()))
  table=metadata.tables['course_attendance']
  for day,in_hour,out_hour in [(20,2,9),(21,1,10),(22,2,10),(23,1,9),(24,1,10)]:
   incoming=datetime(2026,10,day,in_hour,0,tzinfo=timezone.utc)
   session.execute(insert(table).values(id=str(uuid4()),employee_id=eid,work_date=incoming.date(),clock_in_at=incoming,clock_out_at=incoming.replace(hour=out_hour),created_at=incoming,updated_at=incoming,version_no=1))
 for day in ['2026-10-19','2026-10-27']:
  response=client.post('/api/v1/leaves',headers=h['employee'],json={'start_date':day,'end_date':day,'leave_type':'OTHER','reason':'虚构统计边界'})
  status=response.status_code;assert status==201
  item=response.json()['data']
  response=client.post('/api/v1/leaves/'+item['id']+'/decision',headers={**h['manager'],'If-Match':'"v1"'},json={'status':'APPROVED','opinion':'虚构审批'})
  status=response.status_code;assert status==200
 before=client.get('/api/v1/attendance?month=2026-10',headers=h['employee']).json()['data']
 counts={row['name']:row['count'] for row in before['overview']['items']}
 assert counts=={'NORMAL':1,'LATE':1,'EARLY':1,'LATE_EARLY':1,'MISSING':12,'APPROVED_LEAVE':2,'IN_PROGRESS':1,'UPCOMING':3}
 assert before['overview']['total_days']==22 and sum(counts.values())==22
 assert before['summary']=={'planned_days':22,'leave_days':2,'expected_days':20,'complete_days':4,'late_days':2,'early_days':2,'missing_days':12,'attendance_rate':'20.00'}
 # At the exact shift end, an incomplete day becomes missing, without changing the denominator.
 clock.advance(hours=9,minutes=1)
 after=client.get('/api/v1/attendance?month=2026-10',headers=h['employee']).json()['data']
 counts={row['name']:row['count'] for row in after['overview']['items']}
 assert counts['MISSING']==13 and counts['IN_PROGRESS']==0 and sum(counts.values())==22
 hr=client.get('/api/v1/attendance?month=2026-10&employee_id='+eid,headers=h['hr']).json()['data']
 assert hr['overview']==after['overview']
 status=client.get('/api/v1/attendance?month=2026-10&employee_id='+profiles['hr']['employee_id'],headers=h['employee']).status_code;assert status==403
 status=client.get('/api/v1/attendance?month=2026-10',headers=h['admin']).status_code;assert status==403
 status=client.get('/api/v1/attendance?month=2026-10').status_code;assert status==401


def test_overview_excludes_months_outside_employment_and_respects_termination(course):
 app,client,_,h,profiles=course
 empty=client.get('/api/v1/attendance?month=2026-09',headers=h['employee']).json()['data']
 assert empty['overview']['total_days']==0 and not any(row['count'] for row in empty['overview']['items'])
 with app.state.database.transaction(write=True) as session:
  table=metadata.tables['employees'];session.execute(update(table).where(table.c.id==profiles['employee']['employee_id']).values(termination_date=datetime(2026,10,28).date()))
 data=client.get('/api/v1/attendance?month=2026-10',headers=h['employee']).json()['data']
 assert data['overview']['total_days']==2
 assert {row['name']:row['count'] for row in data['overview']['items']}['UPCOMING']==1
