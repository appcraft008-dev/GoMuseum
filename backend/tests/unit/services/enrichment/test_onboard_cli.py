from scripts.onboard import build_parser


def test_parser_fetch():
    ns = build_parser().parse_args(["orsay", "fetch"])
    assert ns.slug == "orsay" and ns.command == "fetch"


def test_parser_load_staging_sample():
    ns = build_parser().parse_args(
        ["orsay", "load", "--target", "staging", "--pack", "k.json", "--sample"]
    )
    assert ns.command == "load" and ns.target == "staging"
    assert ns.pack == "k.json" and ns.sample is True
