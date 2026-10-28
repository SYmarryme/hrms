"""Attendance rule errors and history, using only the isolated course fixture."""
from datetime import date

import pytest
from sqlalchemy import select

from backend.models import metadata
from test_course import course

URL = '/api/v1/attendance/rules'
RULE = {'effective_from': '2026-10-27', 'weekdays': [0, 1, 2, 3, 4],
        'start_time': '09:00', 'end_time': '18:00', 'grace_minutes': 10}


def stored_rules(app):
    with app.state.database.transaction() as session:
        return [dict(row) for row in session.execute(select(metadata.tables['course_attendance_rules'])).mappings()]


@pytest.mark.parametrize('changes,code,message', [
    ({'start_time': '14:00', 'end_time': '06:00'}, 'ATTENDANCE_TIME_ORDER', '下班时间必须晚于上班时间，请重新设置。'),
    ({'start_time': '09:00', 'end_time': '09:00'}, 'ATTENDANCE_TIME_ORDER', '下班时间必须晚于上班时间，请重新设置。'),
    ({'weekdays': []}, 'ATTENDANCE_WORKDAYS_REQUIRED', '请至少选择一个工作日。'),
    # Field validation precedes cross-field time ordering, consistently with the UI.
    ({'weekdays': [], 'start_time': '14:00', 'end_time': '06:00'}, 'ATTENDANCE_WORKDAYS_REQUIRED', '请至少选择一个工作日。'),
    ({'start_time': '25:00'}, 'VALIDATION_ERROR', '请求字段或格式不正确'),
    ({'grace_minutes': 121}, 'VALIDATION_ERROR', '请求字段或格式不正确'),
    ({'weekdays': [0, 0]}, 'VALIDATION_ERROR', '请求字段或格式不正确'),
    ({'weekdays': [5]}, 'VALIDATION_ERROR', '请求字段或格式不正确'),
    ({'effective_from': '2026-02-30'}, 'VALIDATION_ERROR', '请求字段或格式不正确'),
])
def test_specific_rule_validation_is_safe_and_never_writes(course, changes, code, message):
    app, client, _, headers, _ = course
    before = stored_rules(app)
    response = client.post(URL, headers=headers['hr'], json={**RULE, **changes})
    assert response.status_code == 422
    assert response.json()['error'] == {'code': code, 'message': message}
    assert stored_rules(app) == before


@pytest.mark.parametrize('weekdays', [[0], [1, 3], [0, 1, 2, 3, 4]])
def test_legal_rule_persists_exact_dates_times_and_weekdays(course, weekdays):
    app, client, _, headers, _ = course
    payload = {**RULE, 'weekdays': weekdays}
    response = client.post(URL, headers=headers['hr'], json=payload)
    assert response.status_code == 201
    row = stored_rules(app)[0]
    assert row['effective_from'] == date(2026, 10, 27)
    assert {key: row[key] for key in payload if key != 'effective_from'} == {
        key: value for key, value in payload.items() if key != 'effective_from'}
    assert client.get(URL, headers=headers['employee']).json()['data']['items'][0]['weekdays'] == weekdays


@pytest.mark.parametrize('role,status', [(None, 401), ('employee', 403), ('manager', 403), ('admin', 403)])
def test_rule_write_requires_hr_even_when_called_directly(course, role, status):
    app, client, _, headers, _ = course
    response = client.post(URL, headers=headers[role] if role else {}, json=RULE)
    assert response.status_code == status
    assert stored_rules(app) == []


def test_effective_rule_history_workdays_and_raw_punches_remain_consistent(course):
    app, client, _, headers, profiles = course
    assert client.post('/api/v1/attendance/clock-in', headers=headers['employee'], json={}).status_code == 200
    def punches():
        with app.state.database.transaction() as session:
            return [dict(row) for row in session.execute(select(metadata.tables['course_attendance'])).mappings()]
    original = punches()
    assert original[0]['employee_id'] == profiles['employee']['employee_id']
    assert client.post(URL, headers=headers['hr'], json={**RULE, 'weekdays': [1], 'start_time': '10:00'}).status_code == 201
    assert client.post(URL, headers=headers['hr'], json={**RULE, 'effective_from': '2026-10-29', 'weekdays': [3], 'start_time': '08:00'}).status_code == 201
    with app.state.database.transaction() as session:
        service = app.state.course
        assert service.rule(session, date(2026, 10, 26))['start_time'] == '09:00'
        assert service.rule(session, date(2026, 10, 27))['start_time'] == '10:00'
        assert service.rule(session, date(2026, 10, 28))['start_time'] == '10:00'
        assert service.rule(session, date(2026, 10, 29))['start_time'] == '08:00'
        assert service.workdays(session, date(2026, 10, 26), date(2026, 10, 30)) == {
            date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 29)}
    monthly = client.get('/api/v1/attendance?month=2026-10', headers=headers['employee']).json()['data']
    assert monthly['summary']['planned_days'] == 3
    assert monthly['items'][0]['clock_in_at'].startswith('2026-10-26T00:59')
    rows = stored_rules(app)
    repeated = client.post(URL, headers=headers['hr'], json=RULE)
    assert repeated.status_code == 409 and repeated.json()['error']['message'] == '该生效日期已有规则'
    for past in ['2026-10-25', '2026-10-26']:
        response = client.post(URL, headers=headers['hr'], json={**RULE, 'effective_from': past})
        assert response.status_code == 409
        assert response.json()['error']['message'] == '新规则只能次日或以后生效，不能重算历史打卡'
    assert stored_rules(app) == rows
    assert punches() == original
    history = client.get(URL, headers=headers['hr']).json()['data']['items']
    assert [row['effective_from'] for row in history] == ['2026-10-29', '2026-10-27']
