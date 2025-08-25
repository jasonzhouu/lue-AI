"""
AI Assistant UI Module

This module handles the rendering and display of the AI assistant interface.
It provides a full-screen overlay for interacting with the AI assistant.
"""

from rich.console import Console
from rich.text import Text
from .ui_theme import COLORS
from .ui_utils import get_terminal_size, wrap_text_to_lines, create_border_line, create_separator_line, truncate_text
from . import content_parser


def get_current_context(reader):
    """Extract the current reading context for the AI assistant."""
    try:
        current_chapter = reader.chapters[reader.ui_chapter_idx]
        current_paragraph = current_chapter[reader.ui_paragraph_idx]
        sentences = content_parser.split_into_sentences(current_paragraph)
        current_sentence = sentences[reader.ui_sentence_idx] if reader.ui_sentence_idx < len(sentences) else ""

        # Get chapter title if available
        chapter_titles = content_parser.extract_chapter_titles(reader.chapters)
        chapter_title = ""
        for idx, title in chapter_titles:
            if idx == reader.ui_chapter_idx:
                chapter_title = title
                break

        return current_sentence, chapter_title
    except (IndexError, AttributeError):
        return "Unable to get current sentence", ""


def format_conversation_message(role, message, width, prefix_added=False):
    """Format a conversation message with proper word wrapping."""
    prefix = "" if prefix_added else ("User: " if role == "user" else "AI: ")
    message_lines = []

    # First split by actual newlines in the message
    paragraphs = message.split('\n')

    for para_idx, paragraph in enumerate(paragraphs):
        if para_idx == 0 and not prefix_added:
            # First paragraph gets the prefix
            words = paragraph.split(' ')
            current_line = prefix
        else:
            # Subsequent paragraphs are indented
            words = paragraph.split(' ') if paragraph.strip() else ['']
            current_line = "    "

        for word in words:
            if not word and para_idx > 0:  # Empty paragraph (newline)
                if current_line.strip():
                    message_lines.append(current_line.rstrip())
                message_lines.append("    ")  # Empty line
                current_line = "    "
                continue

            test_line = current_line + word + " "
            if len(test_line) <= width - 6:
                current_line = test_line
            else:
                if current_line.strip():
                    message_lines.append(current_line.rstrip())
                # Continuation lines get extra indentation
                indent = "    " if para_idx == 0 and not prefix_added else "        "
                current_line = indent + word + " "

        if current_line.strip():
            message_lines.append(current_line.rstrip())

    return message_lines


def render_ai_assistant(reader):
    """
    Render a full-screen AI assistant overlay.
    """
    try:
        width, height = get_terminal_size()
        console = Console()

        # Always clear screen to prevent content residue
        console.clear()

        # Create title
        title = "AI Assistant"

        # Print title with borders
        border_line = "┌" + "─" * (width - 2) + "┐"
        title_line = create_border_line(width, "│", "│", " ")
        title_content = title.center(width - 2)
        title_line = "│" + title_content + "│"
        separator_line = create_separator_line(width)

        console.print(Text(border_line, style=COLORS.AI_BORDER))
        console.print(Text(title_line, style=f"{COLORS.AI_BORDER} {COLORS.AI_TITLE}"))
        console.print(Text(separator_line, style=COLORS.AI_BORDER))

        # Get current sentence and context
        current_sentence, chapter_title = get_current_context(reader)

        # Print current sentence section (highlighted)
        sentence_title = "Current Highlighted Sentence:"
        sentence_title_line = create_border_line(width, "│ ", " │", " ")
        sentence_title_line = "│ " + sentence_title + " " * (width - 4 - len(sentence_title)) + " │"
        console.print(Text(sentence_title_line, style="bold yellow"))

        # Display the current sentence with word wrapping
        if current_sentence:
            sentence_lines = wrap_text_to_lines(current_sentence, width - 8)

            for line in sentence_lines[:2]:  # Show max 2 lines for sentence
                sentence_line = "│ \"" + line + "\" " + " " * (width - 6 - len(line)) + " │"
                console.print(Text(sentence_line, style="bright_white"))

        # Show chapter info if available
        if chapter_title:
            truncated_title = truncate_text(chapter_title, width - 12)
            chapter_line = "│ Chapter: " + truncated_title + " " * (width - 12 - len(truncated_title)) + " │"
            console.print(Text(chapter_line, style=COLORS.AI_CONTEXT))

        # Separator
        separator_line = create_separator_line(width)
        console.print(Text(separator_line, style=COLORS.AI_BORDER))

        # Calculate available space for conversation
        # Count actual used lines dynamically:
        # - Top border (1) + title (1) + separator (1) = 3
        # - Current sentence section: title (1) + sentence lines (up to 2) = up to 3
        # - Chapter info (1 if exists) = 0 or 1
        # - Separator after context (1) = 1
        # - Input section: separator (1) + input (1) + separator (1) + controls (1) = 4
        # - Bottom border (1) = 1
        # - Suggestions (if no conversation): title (1) + suggestions (up to 2) = up to 3

        base_used_lines = 3 + 1 + 1 + 4 + 1  # 10 lines minimum

        # Add lines for current sentence display (up to 2 lines)
        sentence_lines_count = 0
        if current_sentence:
            sentence_lines = wrap_text_to_lines(current_sentence, width - 8)
            sentence_lines_count = min(len(sentence_lines), 2)

        # Add line for chapter info if it exists
        chapter_line_count = 1 if chapter_title else 0

        # Add lines for suggestions if no conversation exists
        suggestions_lines_count = 0
        if not reader.ai_conversation and not reader.ai_waiting_response:
            suggestions_lines_count = 3  # title + 2 suggestion lines

        total_used_lines = base_used_lines + sentence_lines_count + chapter_line_count + suggestions_lines_count
        available_height = max(3, height - total_used_lines)

        # Show conversation history
        conversation_lines = []
        for i, (role, message) in enumerate(reader.ai_conversation[-10:]):  # Show last 10 messages
            style = COLORS.AI_USER_MESSAGE if role == "user" else COLORS.AI_AI_MESSAGE
            message_lines = format_conversation_message(role, message, width)

            for line in message_lines:
                conversation_lines.append((line, style))

        # Show conversation (scroll to bottom if too many lines)
        start_idx = max(0, len(conversation_lines) - available_height)
        displayed_lines = 0

        for i in range(start_idx, len(conversation_lines)):
            if displayed_lines >= available_height:
                break
            line_text, style = conversation_lines[i]
            line_text = truncate_text(line_text, width - 6)
            conv_line = "│ " + line_text + " " * (width - 4 - len(line_text)) + " │"
            console.print(Text(conv_line, style=style))
            displayed_lines += 1

        # Fill remaining conversation space
        for _ in range(available_height - displayed_lines):
            empty_line = create_border_line(width)
            console.print(Text(empty_line, style=COLORS.AI_BORDER))

        # Input section
        separator_line = create_separator_line(width)
        console.print(Text(separator_line, style=COLORS.AI_BORDER))

        # Show waiting indicator or input prompt
        if reader.ai_waiting_response:
            input_text = "AI is thinking..."
            input_line = "│ " + input_text + " " * (width - 4 - len(input_text)) + " │"
            console.print(Text(input_line, style=COLORS.AI_WAITING))
        else:
            input_prompt = "Question: "
            input_text = input_prompt + reader.ai_input_buffer + "█"  # Show cursor
            if len(input_text) > width - 6:
                # Show end of input if too long
                input_text = "..." + input_text[-(width - 9):]
            input_line = "│ " + input_text + " " * (width - 4 - len(input_text)) + " │"
            console.print(Text(input_line, style=COLORS.AI_INPUT))

        # Controls
        separator_line = create_separator_line(width)
        console.print(Text(separator_line, style=COLORS.AI_BORDER))

        controls = "[Enter] Send Question   [Esc/?] Close   [Ctrl+U] Clear Input"
        if len(controls) > width - 4:
            controls = "[Enter] Send   [Esc] Close   [Ctrl+U] Clear"
        controls_padding = (width - 2 - len(controls)) // 2
        controls_line = "│" + " " * controls_padding + controls + " " * (width - 2 - len(controls) - controls_padding) + "│"
        console.print(Text(controls_line, style=COLORS.AI_CONTROLS))

        # Suggestions (if no conversation yet)
        if not reader.ai_conversation and not reader.ai_waiting_response:
            suggestions_title = "Suggested Questions:"
            suggestions_line = "│ " + suggestions_title + " " * (width - 4 - len(suggestions_title)) + " │"
            console.print(Text(suggestions_line, style=COLORS.AI_CONTROLS))

            suggestions = [
                "What does this sentence mean?",
                "What is the main point of this content?",
                "Is there any deeper meaning here?"
            ]

            for i, suggestion in enumerate(suggestions[:2]):  # Show max 2 suggestions
                truncated_suggestion = truncate_text(suggestion, width - 8)
                suggestion_text = f"{i+1}. {truncated_suggestion}"
                suggestion_line = "│ " + suggestion_text + " " * (width - 4 - len(suggestion_text)) + " │"
                console.print(Text(suggestion_line, style="dim white"))

        # Bottom border
        bottom_line = "└" + "─" * (width - 2) + "┘"
        console.print(Text(bottom_line, style=COLORS.AI_BORDER))

    except Exception as e:
        # Fallback to simple display
        console = Console()
        console.clear()
        console.print(f"\nAI Assistant (Render Error: {e})", style="red")
        console.print("─" * 50)
        console.print("Current Context:", style="cyan")
        console.print(reader.ai_current_context if reader.ai_current_context else "Unable to get context")
        console.print("─" * 50)
        if reader.ai_waiting_response:
            console.print("AI is thinking...", style="yellow")
        else:
            console.print(f"Question: {reader.ai_input_buffer}█", style="white")
        console.print("─" * 50)
        console.print("Press Enter to send question, Esc to close", style="yellow")
