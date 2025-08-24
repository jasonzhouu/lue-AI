"""TTS implementation for Google Cloud Text-to-Speech API."""

import os
import asyncio
import logging
from pathlib import Path
from rich.console import Console

from .base import TTSBase
from .. import config


class GoogleTTS(TTSBase):
    """TTS implementation for Google Cloud Text-to-Speech API."""

    @property
    def name(self) -> str:
        return "google"

    @property
    def output_format(self) -> str:
        return "mp3"

    def __init__(self, console: Console, voice: str = None, lang: str = None):
        super().__init__(console, voice, lang)
        self.client = None
        
        if self.voice is None:
            self.voice = config.TTS_VOICES.get(self.name, "en-US-Standard-C")
        
        # Set default language if not specified
        if self.lang is None:
            self.lang = "en-US"

    async def initialize(self) -> bool:
        """Initialize Google Cloud TTS client."""
        try:
            from google.cloud import texttospeech
            self.texttospeech = texttospeech
        except ImportError:
            self.console.print("[bold red]Error: 'google-cloud-texttospeech' package not found.[/bold red]")
            self.console.print("[yellow]Please run 'pip install google-cloud-texttospeech' to use this TTS model.[/yellow]")
            logging.error("'google-cloud-texttospeech' is not installed.")
            return False

        # Get API credentials
        self.credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not self.credentials_path:
            self.console.print("[bold red]Error: Google Cloud credentials not found.[/bold red]")
            self.console.print("[yellow]Please set GOOGLE_APPLICATION_CREDENTIALS environment variable to your service account key file.[/yellow]")
            self.console.print("[cyan]You can create service account credentials at: https://console.cloud.google.com/iam-admin/serviceaccounts[/cyan]")
            logging.error("Google Cloud credentials not configured.")
            return False

        if not os.path.exists(self.credentials_path):
            self.console.print(f"[bold red]Error: Credentials file not found: {self.credentials_path}[/bold red]")
            logging.error(f"Google Cloud credentials file not found: {self.credentials_path}")
            return False

        try:
            # Create TTS client
            self.client = texttospeech.TextToSpeechClient()
            self.initialized = True
            self.console.print("[green]Google Cloud TTS model initialized successfully.[/green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error: Failed to initialize Google Cloud TTS: {e}[/bold red]")
            logging.error(f"Google Cloud TTS initialization failed: {e}", exc_info=True)
            return False

    async def generate_audio(self, text: str, output_path: str):
        """Generate audio from text using Google Cloud TTS."""
        if not self.initialized:
            raise RuntimeError("Google Cloud TTS has not been initialized.")
        
        if not text.strip():
            # Create empty audio file for empty text
            with open(output_path, 'wb') as f:
                f.write(b'')
            return

        try:
            # Use asyncio.to_thread to run the blocking API call
            await asyncio.to_thread(
                self._generate_audio_sync, text, output_path
            )
        except Exception as e:
            logging.error(f"Google Cloud TTS audio generation failed for text: '{text[:50]}...'", exc_info=True)
            raise RuntimeError(f"Google Cloud TTS failed: {e}")

    def _generate_audio_sync(self, text: str, output_path: str):
        """Synchronous version of audio generation."""
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Set the text input to be synthesized
        synthesis_input = self.texttospeech.SynthesisInput(text=text)

        # Build the voice request
        voice = self.texttospeech.VoiceSelectionParams(
            language_code=self.lang,
            name=self.voice
        )

        # Select the type of audio file you want returned
        audio_config = self.texttospeech.AudioConfig(
            audio_encoding=self.texttospeech.AudioEncoding.MP3
        )

        # Perform the text-to-speech request
        response = self.client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        # Write the response to the output file
        with open(output_path, "wb") as out:
            out.write(response.audio_content)

    async def warm_up(self):
        """Warm up the Google Cloud TTS model."""
        if not self.initialized:
            return

        self.console.print("[bold cyan]Warming up the Google Cloud TTS model...[/bold cyan]")
        warmup_file = os.path.join(config.AUDIO_DATA_DIR, f".warmup_google.{self.output_format}")
        
        try:
            await self.generate_audio("Ready.", warmup_file)
            self.console.print("[green]Google Cloud TTS model is ready.[/green]")
        except Exception as e:
            self.console.print(f"[bold yellow]Warning: Google Cloud TTS model warm-up failed: {e}[/bold yellow]")
            logging.warning(f"Google Cloud TTS model warm-up failed: {e}", exc_info=True)
        finally:
            if os.path.exists(warmup_file):
                try:
                    os.remove(warmup_file)
                except OSError:
                    pass