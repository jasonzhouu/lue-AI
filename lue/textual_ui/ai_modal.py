"""
AI Assistant modal for the Lue e-book reader Textual interface.
Provides interactive AI assistance for understanding text content.
"""

from typing import TYPE_CHECKING
from textual.screen import ModalScreen
from textual.containers import Container
from textual.widgets import Static
from textual.binding import Binding
from textual.app import ComposeResult
from rich.text import Text

if TYPE_CHECKING:
    from .. import reader as lue_reader


class AIAssistantModal(ModalScreen):
    """AI Assistant modal screen with proper input handling."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("ctrl+u", "clear_input", "Clear"),
        Binding("enter", "send_message", "Send"),
    ]
    
    def __init__(self, lue_instance: "lue_reader.Lue"):
        super().__init__()
        self.lue = lue_instance
        self.input_buffer = ""
        self.sent_message = ""  # Store the message being processed
        self.conversation_history = []
        self.current_context = ""
        self.waiting_for_response = False
        
    def compose(self) -> ComposeResult:
        """Create the AI Assistant interface."""
        with Container(id="ai-container"):
            yield Static("🤖 AI Assistant", id="ai-title")
            yield Static(id="ai-context")
            yield Static(id="ai-conversation")
            yield Static(id="ai-input-display")
            
    def on_mount(self) -> None:
        """Initialize AI Assistant when mounted."""
        self.update_context_display()
        self.update_conversation_display()
        self.update_input_display()
        
    def update_context_display(self) -> None:
        """Update the current sentence context."""
        try:
            context_widget = self.query_one("#ai-context", Static)
            
            # Get current sentence from lue instance
            if hasattr(self.lue, 'get_current_sentence'):
                current_sentence = self.lue.get_current_sentence()
            else:
                current_sentence = "No sentence available"
                
            self.current_context = current_sentence
            context_content = Text(f"Current: {current_sentence[:100]}...", style="cyan")
            context_widget.update(context_content)
        except Exception:
            pass
        
    def update_conversation_display(self) -> None:
        """Update the conversation history."""
        try:
            conv_widget = self.query_one("#ai-conversation", Static)
            
            if self.conversation_history:
                conv_display = Text()
                for i, entry in enumerate(self.conversation_history[-3:]):  # Show last 3 exchanges
                    if i > 0:
                        conv_display.append("\n")
                    conv_display.append(f"Q: {entry['question']}", style="yellow")
                    conv_display.append("\n")
                    conv_display.append(f"A: {entry['answer'][:200]}...", style="green")
                    conv_display.append("\n")
            else:
                conv_display = Text("Ask a question about the current text...", style="dim")
                
            conv_widget.update(conv_display)
        except Exception:
            pass
        
    def update_input_display(self) -> None:
        """Update the input buffer display."""
        try:
            input_widget = self.query_one("#ai-input-display", Static)
            
            if self.waiting_for_response:
                # Show the sent message and waiting status
                input_content = Text()
                input_content.append(f"❯ {self.sent_message}", style="white")
                input_content.append(" ", style="white")
                input_content.append("(Waiting for AI response...)", style="yellow")
            else:
                cursor = "█" if len(self.input_buffer) % 2 == 0 else " "  # Blinking cursor effect
                input_content = Text(f"❯ {self.input_buffer}{cursor}", style="white")
                
            input_widget.update(input_content)
        except Exception:
            pass
        
    def on_key(self, event) -> None:
        """Handle key input for the AI assistant."""
        if self.waiting_for_response:
            return  # Ignore input while waiting for response
            
        if event.key == "backspace":
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                self.update_input_display()
        elif event.character and event.character.isprintable():
            self.input_buffer += event.character
            self.update_input_display()
            
    def action_clear_input(self) -> None:
        """Clear the input buffer."""
        if not self.waiting_for_response:
            self.input_buffer = ""
            self.update_input_display()
        
    async def action_send_message(self) -> None:
        """Send message to AI assistant."""
        if not self.input_buffer.strip() or self.waiting_for_response:
            return
            
        question = self.input_buffer.strip()
        self.sent_message = question  # Store the message being processed
        self.input_buffer = ""
        self.waiting_for_response = True
        self.update_input_display()
        
        try:
            # Get AI response from lue instance
            if hasattr(self.lue, 'get_ai_response'):
                answer = await self.lue.get_ai_response(question)
            else:
                answer = "AI Assistant not configured. Please set up Gemini API key."
                
            # Add to conversation history
            self.conversation_history.append({
                'question': question,
                'answer': answer,
                'context': self.current_context
            })
            
        except Exception as e:
            self.conversation_history.append({
                'question': question,
                'answer': f"Error: {str(e)}",
                'context': self.current_context
            })
        finally:
            self.waiting_for_response = False
            self.sent_message = ""  # Clear the sent message
            self.update_conversation_display()
            self.update_input_display()
