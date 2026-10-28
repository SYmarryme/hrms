import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import select,update,func
from backend.models import users,auth_sessions,audit_events
from backend.auth import AuthError

URL='/api/v1/auth/password'
def secret():return secrets.token_urlsafe(24)
def signed(client,name,password):
 response=client.post('/api/v1/auth/login',json={'username':name,'password':password})
 status=response.status_code;assert status==200
 return response.json()['data']
def change(client,headers,current,new,confirm=None):
 return client.post(URL,headers=headers,json={'current_password':current,'new_password':new,'confirm_password':new if confirm is None else confirm})
@pytest.fixture
def accounts(tmp_path):
 # Real independently migrated fixture, with known random credentials kept in test memory only.
 from backend.course_demo import create_demo,demo_path
 from backend.settings import Settings
 from backend.app import create_app
 from fastapi.testclient import TestClient
 from conftest import Clock
 passwords={role:secret() for role in ['admin','hr','manager','employee']}
 clock=Clock();settings=Settings(demo_path('password-suite',root=tmp_path),'https://hrms.test')
 create_demo(settings,passwords,root=tmp_path,clock=clock)
 app=create_app(settings,clock)
 with TestClient(app,base_url=settings.public_origin,headers={'Origin':settings.public_origin}) as client:
  h={role:{'Authorization':'Bearer '+signed(client,'fixture-'+role,p)['access_token']} for role,p in passwords.items()}
  yield app,client,clock,passwords,h

@pytest.mark.parametrize('role',['admin','hr','manager','employee'])
def test_each_role_changes_only_self_and_revokes_every_session(accounts,role):
 app,client,_,passwords,h=accounts
 second=signed(client,'fixture-'+role,passwords[role])['access_token'];new=secret()
 response=change(client,h[role],passwords[role],new);status=response.status_code;assert status==204
 for headers in [h[role],{'Authorization':'Bearer '+second}]:
  status=client.get('/api/v1/auth/me',headers=headers).status_code;assert status==401
 status=client.post('/api/v1/auth/login',json={'username':'fixture-'+role,'password':passwords[role]}).status_code;assert status==401
 fresh=signed(client,'fixture-'+role,new);profile=client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+fresh['access_token']}).json()['data']
 assert profile['must_change_password'] is False and role.upper() in profile['roles']
 with app.state.database.transaction() as session:
  stored=session.execute(select(users).where(users.c.username=='fixture-'+role)).mappings().one()
  assert stored['password_hash'].startswith('$argon2id$') and stored['must_change_password'] is False

@pytest.mark.parametrize('case,status_code',[('wrong',400),('same',422),('mismatch',422),('short',422),('long',422)])
def test_invalid_change_does_not_modify_password_or_sessions(accounts,case,status_code):
 app,client,_,passwords,h=accounts;old=passwords['employee'];new=secret();current=secret() if case=='wrong' else old
 if case=='same':new=old
 if case=='short':new='x'*11
 if case=='long':new='x'*129
 with app.state.database.transaction() as session:before=dict(session.execute(select(users).where(users.c.username=='fixture-employee')).mappings().one())
 response=change(client,h['employee'],current,new,secret() if case=='mismatch' else new);status=response.status_code;assert status==status_code
 status=client.get('/api/v1/auth/me',headers=h['employee']).status_code;assert status==200
 with app.state.database.transaction() as session:
  after=dict(session.execute(select(users).where(users.c.id==before['id'])).mappings().one());assert after==before
  events=session.execute(select(audit_events).where(audit_events.c.action_code=='auth.password.change',audit_events.c.outcome=='FAILURE')).mappings().all();assert len(events)==1

@pytest.mark.parametrize('field',['user_id','username','employee_id'])
def test_self_change_forbids_target_parameters(accounts,field):
 app,client,_,passwords,h=accounts
 payload={'current_password':passwords['employee'],'new_password':secret(),'confirm_password':secret(),field:'other-account'}
 status=client.post(URL,headers=h['employee'],json=payload).status_code;assert status==422
 status=client.get('/api/v1/auth/me',headers=h['employee']).status_code;assert status==200

@pytest.mark.parametrize('path',['/departments','/positions','/employees','/attendance?month=2026-10','/leaves','/salaries','/dashboard?month=2026-10','/users','/users/audit-events'])
def test_temporary_login_blocks_every_business_family(accounts,path):
 _,client,_,passwords,h=accounts;temporary=secret()
 created=client.post('/api/v1/users',headers=h['admin'],json={'username':'temporary-admin','password':temporary,'employee_id':None,'roles':['ADMIN'],'department_ids':[]})
 status=created.status_code;assert status==201
 login=signed(client,'temporary-admin',temporary);assert login['must_change_password'] is True
 limited={'Authorization':'Bearer '+login['access_token']}
 profile=client.get('/api/v1/auth/me',headers=limited);status=profile.status_code;assert status==200 and profile.json()['data']['must_change_password'] is True
 response=client.get('/api/v1'+path,headers={**limited,'X-HRMS-Session-Probe':'1'});status=response.status_code;assert status==403
 assert response.json()['error']['code']=='PASSWORD_CHANGE_REQUIRED'
 status=client.post('/api/v1/auth/logout',headers=limited).status_code;assert status==204


def test_reset_revokes_old_tokens_and_cannot_be_bypassed_before_change(accounts):
 app,client,_,passwords,h=accounts
 profile=client.get('/api/v1/auth/me',headers=h['employee']).json()['data'];uid=profile['id'];temporary=secret()
 listing=client.get('/api/v1/users',headers=h['admin']).json()['data']['items'];target=next(row for row in listing if row['id']==uid)
 response=client.post('/api/v1/users/'+uid+'/password',headers={**h['admin'],'If-Match':'"v'+str(target['version_no'])+'"'},json={'password':temporary});status=response.status_code;assert status==200
 status=client.get('/api/v1/auth/me',headers=h['employee']).status_code;assert status==401
 first=signed(client,'fixture-employee',temporary);second=signed(client,'fixture-employee',temporary);assert first['must_change_password'] is True
 limited={'Authorization':'Bearer '+first['access_token']};new=secret()
 status=change(client,limited,temporary,new).status_code;assert status==204
 for raw in [first['access_token'],second['access_token']]:
  status=client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+raw}).status_code;assert status==401
 fresh=signed(client,'fixture-employee',new);assert fresh['must_change_password'] is False
 status=client.get('/api/v1/leaves',headers={'Authorization':'Bearer '+fresh['access_token']}).status_code;assert status==200


def test_flag_is_checked_again_for_already_issued_tokens(accounts):
 app,client,_,_,h=accounts
 with app.state.database.transaction(write=True) as session:session.execute(update(users).where(users.c.username=='fixture-hr').values(must_change_password=True))
 response=client.get('/api/v1/departments',headers=h['hr']);status=response.status_code;assert status==403
 assert response.json()['error']['code']=='PASSWORD_CHANGE_REQUIRED'


def test_concurrent_self_changes_have_exactly_one_winner(accounts):
 app,client,_,passwords,h=accounts;raw=h['employee']['Authorization'].split(' ',1)[1];candidates=[secret(),secret()]
 def attempt(index):
  try:app.state.auth.change_password(raw,passwords['employee'],candidates[index],candidates[index],'test-peer',str(uuid4()));return index,204
  except AuthError as error:return index,error.status
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[0,1]))
 winners=[index for index,status in results if status==204];assert len(winners)==1
 assert sorted(status for _,status in results)==[204,401]
 fresh=signed(client,'fixture-employee',candidates[winners[0]]);assert fresh['must_change_password'] is False


def test_audit_failure_rolls_back_hash_flag_and_all_session_revocations(accounts,monkeypatch):
 import backend.auth as module
 app,client,_,passwords,h=accounts
 with app.state.database.transaction() as session:before=dict(session.execute(select(users).where(users.c.username=='fixture-employee')).mappings().one())
 real=module.audit
 def fail(session,now,action,*args,**kwargs):
  if action=='auth.password.change':raise RuntimeError('injected audit failure')
  return real(session,now,action,*args,**kwargs)
 with monkeypatch.context() as patch:
  patch.setattr(module,'audit',fail)
  with pytest.raises(RuntimeError):change(client,h['employee'],passwords['employee'],secret())
 with app.state.database.transaction() as session:after=dict(session.execute(select(users).where(users.c.id==before['id'])).mappings().one());assert after==before
 status=client.get('/api/v1/auth/me',headers=h['employee']).status_code;assert status==200


def test_change_rate_limit_and_audit_never_return_secrets(accounts):
 app,client,_,passwords,h=accounts;wrong=secret();new=secret()
 for _ in range(11):response=change(client,h['employee'],wrong,new)
 status=response.status_code;assert status==429
 with app.state.database.transaction() as session:
  import json
  data=json.dumps([dict(row) for row in session.execute(select(audit_events)).mappings()],default=str)
 for value in [wrong,new,passwords['employee'],h['employee']['Authorization'].split(' ',1)[1]]:assert value not in data and value not in response.text


def test_missing_bearer_and_target_query_cannot_change_any_password(accounts):
 _,client,_,passwords,h=accounts;new=secret()
 status=change(client,{},passwords['employee'],new).status_code;assert status==401
 status=client.post(URL+'?user_id=other-account',headers=h['employee'],json={
  'current_password':passwords['employee'],'new_password':new,'confirm_password':new}).status_code;assert status==400
 status=client.get('/api/v1/auth/me',headers=h['employee']).status_code;assert status==200


def test_controlled_reset_and_business_write_cannot_bypass_restriction(accounts):
 app,client,_,_,h=accounts;temporary=secret()
 app.state.auth.reset_password('fixture-hr',temporary)
 limited={'Authorization':'Bearer '+signed(client,'fixture-hr',temporary)['access_token']}
 response=client.post('/api/v1/departments',headers=limited,json={'code':'MUST-NOT-EXIST','name':'Synthetic blocked operation'})
 status=response.status_code;assert status==403 and response.json()['error']['code']=='PASSWORD_CHANGE_REQUIRED'
 with app.state.database.transaction() as session:
  from backend.models import metadata
  departments=metadata.tables['departments']
  assert session.execute(select(func.count()).select_from(departments).where(departments.c.code=='MUST-NOT-EXIST')).scalar_one()==0
  assert session.execute(select(users.c.must_change_password).where(users.c.username=='fixture-hr')).scalar_one() is True
  event=session.execute(select(audit_events).where(audit_events.c.action_code=='org.department.create',audit_events.c.outcome=='FAILURE')).mappings().one()
  assert event['actor_user_id'] is not None
