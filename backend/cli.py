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
    parser.add_argument('action', choices=['init-admin', 'reset-password'])
    parser.add_argument('--username', required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('Use an interactive private terminal; passwords are never accepted as arguments or environment variables')
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
        else:
            auth.reset_password(args.username, password)
            print('密码已更新；该账号全部旧会话已撤销。')
        return 0
    except AuthError as error:
        print(error.code + ': ' + error.message, file=sys.stderr)
        return 1
    except (SQLAlchemyError, RuntimeError):
        print('数据库或迁移状态不满足要求；未确认成功，不输出内部数据。', file=sys.stderr)
        return 1
    finally:
        password = confirmation = ''
        database.engine.dispose()


if __name__ == '__main__':
    sys.exit(main())
