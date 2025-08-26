"""
Table of Contents modal for the Lue e-book reader Textual interface.
Enhanced TOC with better space utilization and navigation.
"""

from textual.screen import ModalScreen
from textual.containers import Container
from textual.widgets import Static
from textual.binding import Binding
from textual.app import ComposeResult
from rich.text import Text

from . import reader as lue_reader


class TOCModal(ModalScreen):
    """Enhanced Table of Contents modal with better space utilization."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("c", "dismiss", "Close"),
        Binding("q", "quit", "Quit"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("enter", "select_chapter", "Select"),
        Binding("home", "go_to_top", "First Chapter"),
        Binding("end", "go_to_bottom", "Last Chapter"),
        Binding("page_up", "page_up", "Page Up"),
        Binding("page_down", "page_down", "Page Down"),
    ]
    
    def __init__(self, lue_instance: lue_reader.Lue):
        super().__init__()
        self.lue = lue_instance
        # Initialize selected chapter to current chapter
        self.selected_chapter = getattr(lue_instance, 'chapter_idx', 0)
        # Dynamic scrolling - will be calculated based on actual screen size
        self.toc_scroll_offset = 0
        
    def compose(self) -> ComposeResult:
        """Create the TOC interface with better layout."""
        with Container(id="toc-container"):
            yield Static("📚 Table of Contents", id="toc-title")
            yield Static(id="toc-content")
            yield Static(id="toc-footer")
            
    def on_mount(self) -> None:
        """Initialize TOC content when mounted."""
        self.update_toc_display()
        
    def on_resize(self) -> None:
        """Handle screen resize by updating display."""
        self.update_toc_display()
        
    def update_toc_display(self) -> None:
        """Update the TOC content display with dynamic height calculation."""
        try:
            toc_widget = self.query_one("#toc-content", Static)
            footer_widget = self.query_one("#toc-footer", Static)
            
            # Get actual available height from the container
            container = self.query_one("#toc-container", Container)
            available_height = container.size.height - 4  # Account for title, footer, and borders
            
            # Get chapter titles using the existing content parser
            from . import content_parser
            file_path = getattr(self.lue, 'file_path', None)
            if hasattr(self.lue, 'chapters') and self.lue.chapters:
                chapter_titles = content_parser.extract_chapter_titles(self.lue.chapters, file_path)
            else:
                chapter_titles = [(i, f"Chapter {i+1}") for i in range(len(getattr(self.lue, 'chapters', [])))]
            
            total_chapters = len(chapter_titles)
            if total_chapters == 0:
                toc_widget.update(Text("No chapters available", style="dim"))
                footer_widget.update(Text("", style="dim"))
                return
            
            # Calculate how many chapters can fit on screen
            visible_height = max(5, available_height - 2)  # Reserve space for scroll indicators
            
            # Smart scrolling: keep selected chapter visible and centered when possible
            if total_chapters <= visible_height:
                # All chapters fit on screen
                self.toc_scroll_offset = 0
                start_idx = 0
                end_idx = total_chapters
            else:
                # Need scrolling - center the selected chapter
                center_offset = visible_height // 2
                ideal_start = max(0, self.selected_chapter - center_offset)
                ideal_end = min(total_chapters, ideal_start + visible_height)
                
                # Adjust if we're near the end
                if ideal_end == total_chapters:
                    ideal_start = max(0, total_chapters - visible_height)
                
                self.toc_scroll_offset = ideal_start
                start_idx = ideal_start
                end_idx = ideal_end
            
            # Build TOC display
            toc_lines = []
            current_chapter = getattr(self.lue, 'chapter_idx', 0)
            
            # Add scroll indicator at top if needed
            if self.toc_scroll_offset > 0:
                toc_lines.append((f"  ↑ {self.toc_scroll_offset} more above", "dim"))
            
            # Display chapters
            for i in range(start_idx, end_idx):
                if i >= len(chapter_titles):
                    break
                    
                chapter_idx, title = chapter_titles[i]
                
                # Indicators
                current_indicator = "●" if i == current_chapter else " "
                selection_indicator = "▶" if i == self.selected_chapter else " "
                
                # Style based on selection and current position
                if i == self.selected_chapter:
                    style = "bold yellow on blue"
                elif i == current_chapter:
                    style = "bold green"
                else:
                    style = "white"
                
                # Format with proper spacing
                line_text = f"{current_indicator}{selection_indicator} {title}"
                toc_lines.append((line_text, style))
            
            # Add scroll indicator at bottom if needed
            if end_idx < total_chapters:
                remaining = total_chapters - end_idx
                toc_lines.append((f"  ↓ {remaining} more below", "dim"))
            
            # Build the final display text
            toc_display = Text()
            for i, (line_text, style) in enumerate(toc_lines):
                if i > 0:
                    toc_display.append("\n")
                toc_display.append(line_text, style=style)
                
            toc_widget.update(toc_display)
            
            # Update footer with navigation info
            current_title = ""
            for idx, title in chapter_titles:
                if idx == current_chapter:
                    current_title = title
                    break
            
            footer_text = f"Current: {current_title} ({current_chapter + 1}/{total_chapters}) | [↑↓] Navigate [Enter] Jump [Esc] Close"
            footer_widget.update(Text(footer_text, style="dim"))
            
        except Exception as e:
            toc_widget = self.query_one("#toc-content", Static)
            toc_widget.update(Text(f"Error updating TOC: {str(e)}", style="red"))
        
    def action_cursor_up(self) -> None:
        """Move selection up with scrolling support."""
        if self.selected_chapter > 0:
            self.selected_chapter -= 1
            self.update_toc_display()
            
    def action_cursor_down(self) -> None:
        """Move selection down with scrolling support."""
        # Get actual chapter count from titles
        from . import content_parser
        file_path = getattr(self.lue, 'file_path', None)
        if hasattr(self.lue, 'chapters') and self.lue.chapters:
            chapter_titles = content_parser.extract_chapter_titles(self.lue.chapters, file_path)
            max_chapters = len(chapter_titles) - 1
        else:
            max_chapters = len(getattr(self.lue, 'chapters', [])) - 1
            
        if self.selected_chapter < max_chapters:
            self.selected_chapter += 1
            self.update_toc_display()
            
    def action_go_to_top(self) -> None:
        """Jump to first chapter."""
        self.selected_chapter = 0
        self.update_toc_display()
        
    def action_go_to_bottom(self) -> None:
        """Jump to last chapter."""
        from . import content_parser
        file_path = getattr(self.lue, 'file_path', None)
        if hasattr(self.lue, 'chapters') and self.lue.chapters:
            chapter_titles = content_parser.extract_chapter_titles(self.lue.chapters, file_path)
            self.selected_chapter = len(chapter_titles) - 1
        else:
            self.selected_chapter = len(getattr(self.lue, 'chapters', [])) - 1
        self.update_toc_display()
        
    def action_page_up(self) -> None:
        """Move selection up by a page."""
        # Get actual available height
        container = self.query_one("#toc-container", Container)
        available_height = container.size.height - 4
        visible_height = max(5, available_height - 2)
        page_size = max(1, visible_height // 2)
        
        self.selected_chapter = max(0, self.selected_chapter - page_size)
        self.update_toc_display()
        
    def action_page_down(self) -> None:
        """Move selection down by a page."""
        from . import content_parser
        file_path = getattr(self.lue, 'file_path', None)
        if hasattr(self.lue, 'chapters') and self.lue.chapters:
            chapter_titles = content_parser.extract_chapter_titles(self.lue.chapters, file_path)
            max_chapters = len(chapter_titles) - 1
        else:
            max_chapters = len(getattr(self.lue, 'chapters', [])) - 1
            
        # Get actual available height
        container = self.query_one("#toc-container", Container)
        available_height = container.size.height - 4
        visible_height = max(5, available_height - 2)
        page_size = max(1, visible_height // 2)
        
        self.selected_chapter = min(max_chapters, self.selected_chapter + page_size)
        self.update_toc_display()
            
    def action_select_chapter(self) -> None:
        """Jump to selected chapter."""
        try:
            # Jump to selected chapter in lue instance
            if hasattr(self.lue, 'jump_to_chapter'):
                self.lue.jump_to_chapter(self.selected_chapter)
            else:
                # Fallback: set position manually
                self.lue.chapter_idx = self.selected_chapter
                self.lue.paragraph_idx = 0
                self.lue.sentence_idx = 0
                
                # Update UI state if available
                if hasattr(self.lue, 'ui_chapter_idx'):
                    self.lue.ui_chapter_idx = self.selected_chapter
                    self.lue.ui_paragraph_idx = 0
                    self.lue.ui_sentence_idx = 0
                    
            self.dismiss()
        except Exception:
            self.dismiss()
        
    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
