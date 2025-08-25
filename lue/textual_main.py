"""
Alternative main entry point using Textual framework.
This provides a new UI implementation that solves input handling issues.
"""

import asyncio
import sys
import argparse
import os
import platform
import platformdirs
import logging
from rich.console import Console
from .textual_app import LueApp
from . import config
from .tts_manager import TTSManager, get_default_tts_model_name


def setup_logging():
    """Set up file-based logging for the application."""
    log_dir = platformdirs.user_log_dir(appname="lue", appauthor=False)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "error.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        filename=log_file,
        filemode='a',
        force=True,
    )
    logging.info("Textual application starting")


def setup_environment():
    """Set environment variables for TTS models."""
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "10"
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "10"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    if platform.system() == "Darwin" and platform.processor() == "arm":
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


def main():
    """Main entry point for Textual-based Lue application."""
    tts_manager = TTSManager()
    available_tts = tts_manager.get_available_tts_names()
    default_tts = get_default_tts_model_name(available_tts)

    parser = argparse.ArgumentParser(
        description="A terminal-based eBook reader with TTS (Textual UI)",
        add_help=False
    )
    
    parser.add_argument(
        '-h', '--help',
        action='help',
        help='Show this help message and exit'
    )
    
    parser.add_argument("file_path", help="Path to the eBook file (.epub, .pdf, .txt, etc.)")
    parser.add_argument(
        "-f",
        "--filter",
        action="store_true",
        help="Enable PDF text cleaning filters",
    )
    
    parser.add_argument(
        "-o", "--over", type=float, help="Seconds of overlap between sentences"
    )
    
    if available_tts:
        parser.add_argument(
            "-t",
            "--tts",
            choices=available_tts,
            default=default_tts,
            help=f"Select the Text-to-Speech model (default: {default_tts})",
        )
        parser.add_argument(
            "-v",
            "--voice",
            help="Specify the voice for the TTS model",
        )
        parser.add_argument(
            "-l",
            "--lang",
            help="Specify the language for the TTS model",
        )
    
    args = parser.parse_args()

    if args.over is not None:
        config.OVERLAP_SECONDS = args.over

    if args.filter:
        config.PDF_FILTERS_ENABLED = True

    setup_environment()
    setup_logging()
    
    console = Console()

    # Check for FFmpeg tools
    import subprocess
    for tool in ['ffprobe', 'ffplay', 'ffmpeg']:
        try:
            subprocess.run([tool, '-version'], check=True, text=True, 
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print(f"\n[bold red]Error: {tool} not found.[/bold red] "
                         "Please install FFmpeg and ensure it's in your system's PATH.")
            logging.error(f"Required tool '{tool}' not found. FFmpeg may not be installed.")
            sys.exit(1)

    # Create TTS instance
    tts_instance = None
    if available_tts and hasattr(args, 'tts') and args.tts:
        voice = args.voice if hasattr(args, 'voice') else None
        lang = args.lang if hasattr(args, 'lang') else None
        tts_instance = tts_manager.create_model(args.tts, console, voice=voice, lang=lang)

    # Create and run Textual app
    app = LueApp(args.file_path, tts_model=tts_instance, overlap=args.over)
    app.run()


def cli():
    """Synchronous entry point for the command-line interface."""
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logging.critical(f"Fatal error in Textual application startup: {e}", exc_info=True)


if __name__ == "__main__":
    cli()
