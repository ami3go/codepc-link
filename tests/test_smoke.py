from codepc_link import __version__
from codepc_link.cli import build_parser


def test_version_is_defined() -> None:
    assert __version__


def test_cli_parser_builds() -> None:
    parser = build_parser()
    assert parser.prog == "codepc-link"
