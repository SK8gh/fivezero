from argparse import ArgumentParser, Namespace


def parse_arguments() -> Namespace:
    """
    parses arguments from the run/debug configuration
    """
    parser = ArgumentParser()

    parser.add_argument(
        "--password",
        type=str,
        required=True
    )

    parser.add_argument(
        "--log_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )

    return parser.parse_args()
