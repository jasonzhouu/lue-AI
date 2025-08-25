#!/usr/bin/env python3
"""
Simple test script to validate Textual integration with Lue.
This tests the basic structure without full TTS/AI integration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static, Footer
from textual.binding import Binding
from rich.text import Text

class TestLueApp(App):
    """Minimal test app to validate Textual integration."""
    
    CSS = """
    #content {
        height: 1fr;
        padding: 1;
        border: solid $primary;
    }
    """
    
    BINDINGS = [
        Binding("h", "prev_para", "Prev Para"),
        Binding("l", "next_para", "Next Para"),
        Binding("j", "prev_sent", "Prev Sent"),
        Binding("k", "next_sent", "Next Sent"),
        Binding("c", "show_toc", "TOC"),
        Binding("question_mark", "show_ai", "AI"),
        Binding("q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.current_para = 0
        self.current_sent = 0
        self.paragraphs = [
            "This is the first paragraph of our test book.",
            "Here is the second paragraph with more content.",
            "The third paragraph demonstrates navigation.",
            "Finally, the fourth paragraph completes our test."
        ]
        
    def compose(self) -> ComposeResult:
        """Create the test interface."""
        yield Container(
            Static(id="content"),
            id="main"
        )
        yield Footer()
        
    def on_mount(self) -> None:
        """Initialize the test app."""
        self.update_display()
        
    def update_display(self) -> None:
        """Update the content display."""
        content_widget = self.query_one("#content", Static)
        
        display_lines = []
        for i, para in enumerate(self.paragraphs):
            if i == self.current_para:
                display_lines.append(Text(f"► {para}", style="bold yellow"))
            else:
                display_lines.append(Text(f"  {para}", style="dim"))
        
        display_lines.append(Text(""))
        display_lines.append(Text(f"Position: Para {self.current_para + 1}/{len(self.paragraphs)}, Sent {self.current_sent + 1}", style="blue"))
        display_lines.append(Text(""))
        display_lines.append(Text("Controls: h/l (paragraphs), j/k (sentences), c (TOC), ? (AI), q (quit)", style="green"))
        
        content = Text("\n".join(str(line) for line in display_lines))
        content_widget.update(content)
        
    def action_prev_para(self) -> None:
        """Move to previous paragraph."""
        if self.current_para > 0:
            self.current_para -= 1
            self.current_sent = 0
            self.update_display()
            
    def action_next_para(self) -> None:
        """Move to next paragraph."""
        if self.current_para < len(self.paragraphs) - 1:
            self.current_para += 1
            self.current_sent = 0
            self.update_display()
            
    def action_prev_sent(self) -> None:
        """Move to previous sentence."""
        if self.current_sent > 0:
            self.current_sent -= 1
        elif self.current_para > 0:
            self.current_para -= 1
            self.current_sent = 2  # Assume 3 sentences per paragraph
        self.update_display()
        
    def action_next_sent(self) -> None:
        """Move to next sentence."""
        if self.current_sent < 2:  # Assume 3 sentences per paragraph
            self.current_sent += 1
        elif self.current_para < len(self.paragraphs) - 1:
            self.current_para += 1
            self.current_sent = 0
        self.update_display()
        
    def action_show_toc(self) -> None:
        """Show table of contents (placeholder)."""
        content_widget = self.query_one("#content", Static)
        toc_content = Text("📚 Table of Contents\n\n1. Chapter 1\n2. Chapter 2\n3. Chapter 3\n\nPress 'c' again to return", style="cyan")
        content_widget.update(toc_content)
        
    def action_show_ai(self) -> None:
        """Show AI assistant (placeholder)."""
        content_widget = self.query_one("#content", Static)
        ai_content = Text("🤖 AI Assistant\n\nCurrent: " + self.paragraphs[self.current_para] + "\n\nAsk a question...\n\nPress '?' again to return", style="magenta")
        content_widget.update(ai_content)


if __name__ == "__main__":
    app = TestLueApp()
    app.run()
