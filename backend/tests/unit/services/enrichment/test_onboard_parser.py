import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))

from onboard import build_parser


def test_parser_supports_catalog_subcommand():
    ns = build_parser().parse_args(["orsay", "catalog", "--target", "prod"])
    assert ns.command == "catalog" and ns.slug == "orsay" and ns.target == "prod"
