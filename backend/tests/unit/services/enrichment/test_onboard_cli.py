import pytest

from app.core.config import settings
from scripts import onboard
from scripts.onboard import build_parser


def test_parser_fetch():
    ns = build_parser().parse_args(["orsay", "fetch"])
    assert ns.slug == "orsay" and ns.command == "fetch"


def test_cmd_load_aborts_when_target_mismatches_container_env(monkeypatch):
    # 容器 ENVIRONMENT=staging，却 --target prod → 守卫 abort（防误把数据灌进错环境）
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    with pytest.raises(SystemExit, match="ENVIRONMENT"):
        onboard.cmd_load("orsay", "k.json", False, target="prod")


def test_parser_load_staging_sample():
    ns = build_parser().parse_args(
        ["orsay", "load", "--target", "staging", "--pack", "k.json", "--sample"]
    )
    assert ns.command == "load" and ns.target == "staging"
    assert ns.pack == "k.json" and ns.sample is True
