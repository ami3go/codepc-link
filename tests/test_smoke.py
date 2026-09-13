from codepc_link import __version__
from codepc_link.cli import build_parser
from codepc_link.rfcomm import DEFAULT_RFCOMM_CHANNEL


def test_version_is_defined() -> None:
    assert __version__


def test_cli_parser_builds() -> None:
    parser = build_parser()
    assert parser.prog == "codepc-link"


def test_serve_verbose_flag_counts_levels() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve", "-vv"])
    assert args.handler == "serve"
    assert args.verbose == 2


def test_serve_rfcomm_parser_defaults_and_verbose() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve-rfcomm", "-vv"])
    assert args.handler == "serve-rfcomm"
    assert args.channel == DEFAULT_RFCOMM_CHANNEL
    assert args.verbose == 2
