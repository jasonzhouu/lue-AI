"""TTS implementation for Apple's native macOS speech synthesis."""

import os
import asyncio
import logging
import subprocess
from pathlib import Path
from rich.console import Console

from .base import TTSBase
from .. import config


class AppleTTS(TTSBase):
    """TTS implementation for Apple's native macOS speech synthesis."""

    @property
    def name(self) -> str:
        return "apple"

    @property
    def output_format(self) -> str:
        return "aiff"  # Apple's native audio format

    def __init__(self, console: Console, voice: str = None, lang: str = None):
        super().__init__(console, voice, lang)
        if self.voice is None:
            self.voice = config.TTS_VOICES.get(self.name, "Samantha")

    async def initialize(self) -> bool:
        """Initialize Apple TTS - checks if macOS and say command is available."""
        # Check if we're running on macOS
        if not self._is_macos():
            self.console.print("[bold red]Error: Apple TTS is only available on macOS.[/bold red]")
            logging.error("Apple TTS requires macOS")
            return False
        
        # Check if 'say' command is available
        if not self._check_say_command():
            self.console.print("[bold red]Error: 'say' command not found. This should be available on macOS.[/bold red]")
            logging.error("'say' command not available")
            return False
        
        self.initialized = True
        self.console.print("[green]Apple TTS model initialized successfully.[/green]")
        return True

    def _is_macos(self) -> bool:
        """Check if running on macOS."""
        try:
            import platform
            return platform.system() == "Darwin"
        except:
            return False

    def _check_say_command(self) -> bool:
        """Check if 'say' command is available."""
        try:
            result = subprocess.run(["which", "say"], capture_output=True, text=True)
            return result.returncode == 0 and "say" in result.stdout
        except:
            return False

    async def generate_audio(self, text: str, output_path: str):
        """Generate audio from text using macOS 'say' command."""
        if not self.initialized:
            raise RuntimeError("Apple TTS has not been initialized.")
        
        if not text.strip():
            # Create empty audio file for empty text
            with open(output_path, 'wb') as f:
                f.write(b'')
            return

        try:
            # Use asyncio.to_thread to run the blocking subprocess call
            await asyncio.to_thread(
                self._generate_audio_sync, text, output_path
            )
        except Exception as e:
            logging.error(f"Apple TTS audio generation failed for text: '{text[:50]}...'", exc_info=True)
            raise RuntimeError(f"Apple TTS failed: {e}")

    def _generate_audio_sync(self, text: str, output_path: str):
        """Synchronous version of audio generation using 'say' command."""
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Build the say command
        cmd = ["say", "-v", self.voice, "-o", output_path]
        
        try:
            # Run the say command with the text as input
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=text)
            
            if process.returncode != 0:
                raise RuntimeError(f"say command failed: {stderr}")
                
        except subprocess.CalledProcessError as e:
            if "Voice not found" in str(e):
                available_voices = self._get_available_voices()
                error_msg = f"Voice '{self.voice}' not found. Available voices: {', '.join(available_voices)}"
                self.console.print(f"[bold red]Error: {error_msg}[/bold red]")
                raise RuntimeError(error_msg)
            else:
                raise RuntimeError(f"say command failed: {e}")

    def _get_available_voices(self) -> list[str]:
        """Get list of available voices on the system."""
        try:
            result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
            if result.returncode == 0:
                voices = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        # Extract voice name (first field)
                        voice_name = line.split()[0]
                        voices.append(voice_name)
                return voices
            return []
        except:
            return []

    async def warm_up(self):
        """Warm up the Apple TTS model."""
        if not self.initialized:
            return

        self.console.print("[bold cyan]Warming up the Apple TTS model...[/bold cyan]")
        warmup_file = os.path.join(config.AUDIO_DATA_DIR, f".warmup_apple.{self.output_format}")
        
        try:
            await self.generate_audio("Ready.", warmup_file)
            self.console.print("[green]Apple TTS model is ready.[/green]")
        except Exception as e:
            self.console.print(f"[bold yellow]Warning: Apple TTS model warm-up failed: {e}[/bold yellow]")
            logging.warning(f"Apple TTS model warm-up failed: {e}", exc_info=True)
        finally:
            if os.path.exists(warmup_file):
                try:
                    os.remove(warmup_file)
                except OSError:
                    pass