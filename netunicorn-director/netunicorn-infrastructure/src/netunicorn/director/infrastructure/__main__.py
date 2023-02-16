import argparse

from .server import main


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        "-f",
        help="Configuration file location",
        required=True,
        type=str,
        dest="filepath",
    )
    return parser


if __name__ == "__main__":
    args = create_parser().parse_args()
    main(args.filepath)
