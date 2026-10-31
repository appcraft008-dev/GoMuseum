"""把自己人的账号/设备标成测试机,运营报告从真实用户里剔除(10-31)。

邮箱只作命令行参数、不进仓库;标记落 app_events(tester_mark),重跑不重复写。

用法(容器内):
  python scripts/mark_testers.py --email a@x.com --device 1a43f0e663686121
"""

import argparse
import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.app_event import AppEvent  # noqa: E402
from app.models.user import User  # noqa: E402


def mark(db, emails, devices) -> int:
    uids = []
    for e in emails:
        u = db.query(User).filter(User.email == e).one_or_none()
        if u is None:
            raise SystemExit(f"找不到账号: {e}")
        uids.append(str(u.id))
    q = db.query(AppEvent.user_id, AppEvent.device_id).filter(
        AppEvent.name == "tester_mark"
    )
    have = {(u, d) for u, d in q}
    new = [(u, None) for u in uids] + [(None, d) for d in devices]
    new = [x for x in dict.fromkeys(new) if x not in have]
    for u, d in new:
        db.add(AppEvent(name="tester_mark", user_id=u, device_id=d))
    db.commit()
    return len(new)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", action="append", default=[])
    ap.add_argument("--device", action="append", default=[])
    a = ap.parse_args()
    print("新写入", mark(SessionLocal(), a.email, a.device), "条 tester_mark")


if __name__ == "__main__":
    main()
