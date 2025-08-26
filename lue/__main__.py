"""Main entry point for the Lue eBook reader application."""

from .textual_main import cli as textual_cli


def cli():
    """Entry point for the command-line interface."""
    textual_cli()

if __name__ == "__main__":
    cli()
