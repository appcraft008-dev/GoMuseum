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


def test_parser_generate_command():
    ns = build_parser().parse_args(
        [
            "orsay",
            "generate",
            "--target",
            "staging",
            "--qid",
            "Q1",
            "--langs",
            "en,fr",
            "--force",
            "--limit",
            "5",
        ]
    )
    assert ns.command == "generate"
    assert ns.target == "staging" and ns.qid == "Q1"
    assert ns.langs == "en,fr" and ns.force is True and ns.limit == 5


def test_cmd_generate_aborts_on_env_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    with pytest.raises(SystemExit, match="ENVIRONMENT"):
        onboard.cmd_generate(
            "orsay", qid=None, langs=None, force=False, limit=None, target="prod"
        )


def test_parser_report_command():
    ns = build_parser().parse_args(["orsay", "report", "--langs", "en,fr"])
    assert ns.command == "report"
    assert ns.langs == "en,fr"


def test_parser_report_langs_optional():
    ns = build_parser().parse_args(["orsay", "report"])
    assert ns.command == "report" and ns.langs is None
