"""Local-terminal identity operations. No HTTP registration/bootstrap/reset routes."""
import argparse
import getpass
import sys

from sqlalchemy.exc import SQLAlchemyError

from backend.auth import AuthError, AuthService
from backend.database import Database
from backend.settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init-admin', 'reset-password', 'init-hr'])
    parser.add_argument('--username', required=True)
    parser.add_argument('--operator', help='Existing ADMIN username, only for init-hr')
    parser.add_argument('--employee-id', help='Existing independently employed person, only for init-hr')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('Use an interactive private terminal; passwords are never accepted as arguments or environment variables')
    if args.action == 'init-hr' and (not args.operator or not args.employee_id):
        parser.error('init-hr requires --operator and --employee-id; missing employment facts cannot be auto-created or bypassed')
    if args.action != 'init-hr' and (args.operator or args.employee_id):
        parser.error('--operator and --employee-id are only for init-hr')
    operator_password = getpass.getpass('现有ADMIN密码（不回显）: ') if args.action == 'init-hr' else ''
    password = getpass.getpass('新密码（12–128字符，不回显）: ')
    confirmation = getpass.getpass('再次输入: ')
    if password != confirmation:
        print('两次输入不一致，未修改', file=sys.stderr)
        return 1
    database = Database(Settings.from_env().database_path)
    try:
        database.check_revision()
        auth = AuthService(database)
        if args.action == 'init-admin':
            auth.bootstrap_admin(args.username, password)
            print('首次 ADMIN 已建立；角色与唯一初始化成功审计已原子提交。未授予薪资/治理等业务专项权限。')
        elif args.action == 'reset-password':
            auth.reset_password(args.username, password)
            print('密码已更新；该账号全部旧会话已撤销。')
        else:
            auth.provision_first_hr(args.operator, operator_password, args.username, password, args.employee_id)
            print('首位独立HR账号已绑定有效员工；普通角色授予与来源审计已原子提交，未授予CEO或薪酬治理权限。')
        return 0
    except AuthError as error:
        print(error.code + ': ' + error.message, file=sys.stderr)
        return 1
    except (SQLAlchemyError, RuntimeError):
        print('数据库或迁移状态不满足要求；未确认成功，不输出内部数据。', file=sys.stderr)
        return 1
    finally:
        password = confirmation = operator_password = ''
        database.engine.dispose()


if __name__ == '__main__':
    sys.exit(main())
