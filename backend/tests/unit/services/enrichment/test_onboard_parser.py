import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))

from onboard import build_parser


def test_parser_supports_catalog_subcommand():
    ns = build_parser().parse_args(["orsay", "catalog", "--target", "prod"])
    assert ns.command == "catalog" and ns.slug == "orsay" and ns.target == "prod"


def test_parser_supports_views_subcommand():
    # views 用 --museum 选馆(slug 位置参可省),--max 默认 4
    ns = build_parser().parse_args(["views", "--museum", "orsay"])
    assert ns.command == "views" and ns.museum == "orsay" and ns.max == 4
