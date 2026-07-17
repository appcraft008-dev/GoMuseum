#!/usr/bin/env python3
"""VPS host 上跑:prod → staging 内容表搬运。slim(默认)=搬运后金样本裁剪;full=全量拉真。
用户表(users/benefits/devices)与 recognition_events 永不搬(隐私红线;staging 自有)。
零 LLM。spec 2026-07-17-staging-lightweight §2。
用法(VPS root):python3 sync_staging_from_prod.py --mode slim --yes"""

import argparse
import subprocess
import sys

PROD_PG = "gomuseum_prod_postgres"
STG_PG = "gomuseum_staging_postgres"
STG_BACKEND = "gomuseum_staging_backend"
# 恢复顺序=依赖顺序;--disable-triggers 双保险
CONTENT_TABLES = [
    "museums",
    "artists",
    "museum_objects",
    "object_images",
    "object_embeddings",
    "object_content_sections",
    "object_suggested_questions",
]


def out(cmd):
    return subprocess.run(
        cmd, shell=True, check=True, capture_output=True, text=True
    ).stdout.strip()


def conn(container):
    u = out(f"docker exec {container} printenv POSTGRES_USER")
    d = out(f"docker exec {container} printenv POSTGRES_DB")
    return u, d


def psql(container, sql):
    u, d = conn(container)
    return out(f'docker exec {container} psql -U {u} -d {d} -Atc "{sql}"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["slim", "full"], default="slim")
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args()

    # 1) schema 对齐前置检查
    pv = psql(PROD_PG, "SELECT version_num FROM alembic_version")
    sv = psql(STG_PG, "SELECT version_num FROM alembic_version")
    if pv != sv:
        sys.exit(f"❌ alembic 版本不一致 prod={pv} staging={sv}:先把两边部署到同一版本")

    users_before = psql(STG_PG, "SELECT count(*) FROM users")
    prod_objs = psql(PROD_PG, "SELECT count(*) FROM museum_objects")
    stg_objs = psql(STG_PG, "SELECT count(*) FROM museum_objects")
    print(f"mode={ns.mode} | prod objects={prod_objs} → staging(现 {stg_objs} 将重置)")
    print(f"staging users={users_before}(不动)")
    if not ns.yes:
        sys.exit("预览模式:加 --yes 执行(破坏性重置 staging 内容表)")

    # 2) 清 staging 内容表(child→parent,不 CASCADE 防波及)
    for t in reversed(CONTENT_TABLES):
        psql(STG_PG, f"DELETE FROM {t}")

    # 3) 搬运(dump 管道直灌,--disable-triggers 免 FK 顺序问题)
    pu, pd = conn(PROD_PG)
    su, sd = conn(STG_PG)
    tables = " ".join(f"-t {t}" for t in CONTENT_TABLES)
    pipe = (
        f"docker exec {PROD_PG} pg_dump -U {pu} -d {pd} --data-only "
        f"--disable-triggers {tables} | "
        f"docker exec -i {STG_PG} psql -U {su} -d {sd} -v ON_ERROR_STOP=1 -q"
    )
    subprocess.run(pipe, shell=True, check=True)

    # 4) slim 裁剪
    if ns.mode == "slim":
        subprocess.run(
            f"docker exec {STG_BACKEND} sh -c "
            f"'cd /app && python scripts/staging_prune.py --yes'",
            shell=True,
            check=True,
        )

    # 5) 验收摘要:件数 + 用户表零泄漏
    print(f"staging objects={psql(STG_PG, 'SELECT count(*) FROM museum_objects')}")
    users_after = psql(STG_PG, "SELECT count(*) FROM users")
    if users_after != users_before:
        sys.exit(f"❌ users 表被波及!before={users_before} after={users_after}")
    print(f"users 不变({users_after}) ✓ 完成,全程零 LLM 调用")


if __name__ == "__main__":
    main()
