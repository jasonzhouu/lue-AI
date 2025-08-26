import os
import re
import fitz
import markdown
from docx import Document
from striprtf.striprtf import rtf_to_text
import subprocess
from html.parser import HTMLParser
from html import unescape
from audiblez.core import find_document_chapters_and_extract_texts, find_good_chapters


def split_into_sentences(paragraph: str) -> list[str]:
    """
    Splits a paragraph into sentences, intelligently handling common abbreviations and initials.
    """
    # A list of common English abbreviations that can be followed by a period.
    abbreviations = [
        "Mr", "Mrs", "Ms", "Dr", "Prof", "Rev", "Hon", "Jr", "Sr",
        "Cpl", "Sgt", "Gen", "Col", "Capt", "Lt", "Pvt",
        "vs", "viz", "etc", "eg", "ie",
        "Co", "Inc", "Ltd", "Corp",
        "St", "Ave", "Blvd"
    ]
    
    # Create a regex pattern for these abbreviations.
    abbrev_pattern = r"\b(" + "|".join(abbreviations) + r")\."
    
    # Use a unique placeholder that is highly unlikely to be in the original text.
    placeholder = "<LUE_PERIOD>"
    
    # 1. Protect periods in abbreviations by replacing them with the placeholder.
    paragraph = re.sub(abbrev_pattern, r"\1" + placeholder, paragraph, flags=re.IGNORECASE)
    
    # 2. Protect periods in initials (e.g., "J. F. Kennedy").
    # This looks for a single capital letter, a period, a space, and another capital letter.
    initial_pattern = r"\b([A-Z])\.(?=\s[A-Z])"
    paragraph = re.sub(initial_pattern, r"\1" + placeholder, paragraph)
    
    # 3. Split the text into sentences using the remaining punctuation.
    # The lookbehind `(?<=[.!?])` keeps the delimiter with the sentence.
    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
    
    # 4. Restore the periods and clean up the results.
    restored_sentences = []
    for sentence in sentences:
        if sentence:
            restored = sentence.replace(placeholder, ".")
            if restored:
                restored_sentences.append(restored)
                
    # If splitting resulted in an empty list, return the original paragraph as a single sentence.
    return restored_sentences if restored_sentences else [paragraph]


def clean_text_for_tts(text):
    """
    Global text cleaning function to make content more TTS-friendly.
    Applied to all parsers to handle common issues.
    """
    if not text or not isinstance(text, str):
        return text
    
    # Check if this is a code block line - if so, preserve it mostly as-is
    if text.startswith('__CODE_BLOCK__'):
        # Remove the marker and preserve the content with NO cleaning
        code_content = text[14:]  # Remove '__CODE_BLOCK__' marker

        # Preserve all formatting, spaces, and special characters for code
        return code_content
    
    # 1. Handle spaced dots - collapse patterns like " . . . " to "..."
    # First, handle sequences of 3 or more dots with any amount of spacing
    text = re.sub(r'\s*\.\s*\.\s*\.\s*(\.\s*)*', '...', text)  # " . . . " or more -> "..."
    # Then handle exactly 2 spaced dots
    text = re.sub(r'\s*\.\s*\.\s*(?!\s*\.)', '..', text)  # " . . " -> ".." (not followed by another dot)
    # Handle any remaining multiple consecutive dots
    text = re.sub(r'\.{4,}', '...', text)  # 4+ consecutive dots -> 3 dots
    
    # 2. Remove long sequences of repeated non-alphanumeric characters
    # But preserve bullet points (•), ellipsis (...), and common punctuation
    text = re.sub(r'[-_=~`^]{3,}', '', text)           # Remove ---- or ____ etc.
    text = re.sub(r'[*]{4,}', '', text)                # Remove **** but keep *** and less
    text = re.sub(r'[#]{4,}', '', text)                # Remove #### but keep ### and less
    text = re.sub(r'[+]{3,}', '', text)                # Remove +++ 
    text = re.sub(r'[|]{3,}', '', text)                # Remove |||
    text = re.sub(r'[\\]{3,}', '', text)               # Remove \
    text = re.sub(r'[/]{3,}', '', text)                # Remove ///
    
    # 3. Clean up problematic Unicode characters that TTS struggles with
    # Keep common ones like bullet points, quotes, dashes
    unicode_replacements = {
        # Various quote marks -> standard quotes
        '“': '"', '”': '"', '‘': "'", '’': "'",
        '„': '"', '‚': "'", '‹': "'", '›': "'",
        
        # Various dashes -> standard dash
        '–': '-', '—': '-', '―': '-',
        
        # Mathematical and special symbols -> text equivalents
        '×': 'x', '÷': '/', '±': '+/-',
        '≤': '<=', '≥': '>=', '≠': '!=',
        '≈': '~', '∞': 'infinity',
        
        # Currency symbols -> text
        '€': ' euros', '£': ' pounds', '$': ' dollars',
        
        # Degree and other symbols
        '°': ' degrees', '™': 'TM', '®': 'R',
        '©': 'Copyright', '§': 'Section',
        
        # Remove zero-width and invisible characters
        '\u200b': '', '\u200c': '', '\u200d': '',  # Zero-width spaces
        '\ufeff': '',  # Byte order mark
        '\u00ad': '',  # Soft hyphen
    }
    
    for old_char, new_char in unicode_replacements.items():
        text = text.replace(old_char, new_char)
    
    # 4. Remove other problematic Unicode characters (keep basic Latin, common punctuation, and bullet)
    # This regex keeps: letters, numbers, basic punctuation, spaces, and bullet points
    text = re.sub(r'[^\w\s.,!?;:()[\]{}"\'-•…\n]', '', text)
    
    # 5. Handle ellipsis properly (before whitespace cleanup to avoid interference)
    text = re.sub(r'\.{4,}', '...', text)  # Multiple dots -> ellipsis
    text = re.sub(r'…+', '...', text)      # Unicode ellipsis -> ASCII ellipsis
    
    # 6. Clean up excessive whitespace
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces -> single space
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines -> double newline max
    
    # 7. Remove markdown formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** -> bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic* -> italic
    text = re.sub(r'__([^_]+)__', r'\1', text)      # __bold__ -> bold
    text = re.sub(r'_([^_]+)_', r'\1', text)        # _italic_ -> italic
    text = re.sub(r'`([^`]+)`', r'\1', text)        # `code` -> code
    text = re.sub(r'~~([^~]+)~~', r'\1', text)      # ~~strikethrough~~ -> strikethrough
    
    # Remove markdown links but keep the text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\[[^\ ]*\]', r'\1', text)  # [text][ref] -> text
    
    # Remove reference link definitions
    text = re.sub(r'^\s*\[[^\ ]+\]:\s*\S+.*$', '', text, flags=re.MULTILINE)  # [ref]: url -> (remove)
    
    # Remove markdown headers (# symbols)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # # Header -> Header
    
    # 8. Fix common formatting issues (but preserve ellipsis)
    text = re.sub(r'\s+([,!?;:])', r'\1', text)  # Remove space before punctuation (except dots)
    text = re.sub(r'([,!?;:])\s*([,!?;:])', r'\1 \2', text)  # Ensure space between punctuation
    
    return text.strip()


class HTMLtoLines(HTMLParser):
    """HTML parser"""
    para = {"p", "div"}
    inde = {"q", "dt", "dd", "blockquote"}
    pref = {"pre"}
    bull = {"li"}
    hide = {"script", "style", "head"}

    def __init__(self):
        HTMLParser.__init__(self)
        self.text = [""]
        self.imgs = []
        self.ishead = False
        self.isinde = False
        self.isbull = False
        self.ispref = False
        self.ishidden = False
        self.idhead = set()
        self.idinde = set()
        self.idbull = set()
        self.idpref = set()
        self.hiding_tags = []  # Stack to track which tags are causing hiding
        self._current_span_attrs = {}

    def handle_starttag(self, tag, attrs):
        if re.match("h[1-6]", tag) is not None:
            self.ishead = True
        elif tag in self.inde:
            self.isinde = True
        elif tag in self.pref:
            self.ispref = True
        elif tag in self.bull:
            self.isbull = True
        elif tag in self.hide:
            self.ishidden = True
            self.hiding_tags.append(tag)
        elif tag == "sup":
            # Hide sup content for TTS
            self.ishidden = True
            self.hiding_tags.append("sup")
        elif tag == "sub":
            # Hide sub content for TTS
            self.ishidden = True
            self.hiding_tags.append("sub")
        elif tag == "span":
            # Store span attributes to check for common footnote patterns
            self._current_span_attrs = dict(attrs)
            # Check for common footnote-related class patterns
            span_class = self._current_span_attrs.get('class', '')
            if (len(span_class) <= 3 and  # Short class names are often footnote markers
                (span_class.isdigit() or  # Numeric classes
                 span_class in {'su', 'sit', 'bs', 'is', 'fn', 'note', 'ref'} or  # Common footnote classes
                 'footnote' in span_class.lower() or
                 'note' in span_class.lower() or
                 'ref' in span_class.lower())):
                self.ishidden = True
                self.hiding_tags.append("span")
        elif tag in {"img", "image"}:
            # Skip images completely - don't add anything to text
            pass

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.text += [""]
        elif tag in {"img", "image"}:
            # Skip images completely
            pass

    def handle_endtag(self, tag):
        if re.match("h[1-6]", tag) is not None:
            self.text.append("")
            self.text.append("")
            self.ishead = False
        elif tag in self.para:
            self.text.append("")
        elif tag in self.hide:
            if self.hiding_tags and self.hiding_tags[-1] == tag:
                self.hiding_tags.pop()
                self.ishidden = len(self.hiding_tags) > 0
        elif tag in self.inde:
            if self.text[-1] != "":
                self.text.append("")
            self.isinde = False
        elif tag in self.pref:
            if self.text[-1] != "":
                self.text.append("")
            self.ispref = False
        elif tag in self.bull:
            if self.text[-1] != "":
                self.text.append("")
            self.isbull = False
        elif tag == "sup":
            # End of sup tag - stop hiding content if this was the hiding tag
            if self.hiding_tags and self.hiding_tags[-1] == "sup":
                self.hiding_tags.pop()
                self.ishidden = len(self.hiding_tags) > 0
        elif tag == "sub":
            # End of sub tag - stop hiding content if this was the hiding tag
            if self.hiding_tags and self.hiding_tags[-1] == "sub":
                self.hiding_tags.pop()
                self.ishidden = len(self.hiding_tags) > 0
        elif tag == "span":
            # End of span tag - stop hiding content if this was a hiding span
            if self.hiding_tags and self.hiding_tags[-1] == "span":
                self.hiding_tags.pop()
                self.ishidden = len(self.hiding_tags) > 0
        elif tag in {"img", "image"}:
            # Skip images
            pass

    def handle_data(self, raw):
        if raw and not self.ishidden:
            if self.text[-1] == "":
                tmp = raw.lstrip()
            else:
                tmp = raw
            if self.ispref:
                line = unescape(tmp)
            else:
                line = unescape(re.sub(r"\s+", " ", tmp))
            self.text[-1] += line
            if self.ishead:
                self.idhead.add(len(self.text)-1)
            elif self.isbull:
                self.idbull.add(len(self.text)-1)
            elif self.inde:
                self.idinde.add(len(self.text)-1)
            elif self.ispref:
                self.idpref.add(len(self.text)-1)

    def get_lines(self):
        """Get clean text lines with proper formatting for different content types"""
        clean_lines = []
        for i, line in enumerate(self.text):
            line = line.strip()
            if line and len(line) > 3:  # Skip very short lines
                # Clean up footnote markers and image references
                line = self._clean_line(line)
                # Apply global TTS-friendly cleaning
                line = clean_text_for_tts(line)
                if line and len(line) > 3:  # Check again after cleaning
                    # Apply formatting based on content type
                    if i in self.idhead:
                        # Headers - add some visual separation
                        clean_lines.append("")
                        clean_lines.append(line)
                        clean_lines.append("")
                    elif i in self.idbull:
                        # List items - add bullet point
                        clean_lines.append(f"• {line}")
                    elif i in self.idinde:
                        # Indented content (blockquotes) - add indentation
                        clean_lines.append(f"    {line}")
                    elif i in self.idpref:
                        # Preformatted text (code blocks) - preserve as-is with indentation
                        clean_lines.append(f"    {line}")
                    else:
                        # Regular paragraphs
                        clean_lines.append(line)
        
        # Remove excessive empty lines (more than 2 consecutive)
        result = []
        empty_count = 0
        for line in clean_lines:
            if line == "":
                empty_count += 1
                if empty_count <= 2:  # Allow up to 2 consecutive empty lines
                    result.append(line)
            else:
                empty_count = 0
                result.append(line)
        
        return result
    
    def _is_footnote_reference(self, content):
        """
        Detect if content looks like a footnote reference based on patterns.
        This is more general than hardcoding specific class names.
        """
        if not content or len(content.strip()) == 0:
            return False
            
        content = content.strip()
        
        # Very short content that's just numbers, letters, or footnote symbols
        if len(content) <= 3:
            # Pure numbers (verse numbers, sentence numbers, footnote numbers)
            if re.match(r'^\d+$', content):
                return True
            # Footnote symbols
            if re.match(r'^[*†‡§¶]+$', content):
                return True
            # Single letters (footnote markers)
            if re.match(r'^[a-zA-Z]$', content):
                return True
        
        # Slightly longer but still footnote-like patterns
        if len(content) <= 5:
            # Numbers with punctuation
            if re.match(r'^\d+[.,;:]?$', content):
                return True
            # Roman numerals
            if re.match(r'^[ivxlcdm]+$', content.lower()):
                return True
        
        return False

    def _clean_line(self, line):
        """Clean footnote markers and image references from a line"""
        # Remove footnote markers like ^{12}, _{sub}
        line = re.sub(r'\^{[^}]*}', '', line)
        line = re.sub(r'_{[^}]*}', '', line)
        
        # Remove image references like [IMG:0]
        line = re.sub(r'\[IMG:\d+\]', '', line)
        
        # Remove bracketed footnote references
        line = re.sub(r'\[\d+\]', '', line)
        line = re.sub(r'\[[a-zA-Z]+\d*\]', '', line)
        
        # Remove footnote symbols
        line = re.sub(r'[*†‡§¶]+', '', line)
        
        # Remove superscript numbers (since we're handling sup tags at HTML level, 
        # any remaining ones are likely Unicode superscripts)
        line = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', line)
        
        # Clean up extra whitespace
        line = re.sub(r'\s+', ' ', line).strip()
        
        return line


def extract_content(file_path, console):
    """Extract content from the file based on its extension."""
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.epub':
        return _extract_content_epub(file_path, console)
    elif file_extension == '.pdf':
        return _extract_content_pdf(file_path, console)
    elif file_extension == '.txt':
        return _extract_content_txt(file_path, console)
    elif file_extension == '.docx':
        return _extract_content_docx(file_path, console)
    elif file_extension == '.doc':
        return _extract_content_doc(file_path, console)
    elif file_extension == '.html':
        return _extract_content_html(file_path, console)
    elif file_extension == '.rtf':
        return _extract_content_rtf(file_path, console)
    elif file_extension == '.md':
        return _extract_content_md(file_path, console)
    else:
        console.print(f"[bold red]Error: Unsupported file type '{file_extension}'. "
                     f"Supported formats: .epub, .pdf, .txt, .docx, .doc, .html, .rtf, .md[/bold red]")
        return []

def _extract_content_epub(file_path, console):
    """Extract content from EPUB using enhanced audiblez-inspired approach"""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError:
        console.print("[bold red]Error: ebooklib and beautifulsoup4 are required for EPUB parsing. Install with: pip install ebooklib beautifulsoup4[/bold red]")
        return []
    
    try:
        # Open EPUB file using ebooklib
        book = epub.read_epub(file_path)
    except Exception as e:
        console.print(f"[bold red]Error: Failed to open EPUB file: {e}[/bold red]")
        return []
    
    try:
        # Use audiblez approach for smart chapter extraction
        document_chapters = find_document_chapters_and_extract_texts(book)
        good_chapters = find_good_chapters(document_chapters)
        
        console.print(f"[green]Found {len(document_chapters)} total chapters, {len(good_chapters)} content chapters[/green]")
        
        if not good_chapters:
            console.print("[bold red]Error: No readable content chapters found in EPUB[/bold red]")
            return []
        
        # Convert audiblez chapters to our format with enhanced processing
        chapters = []
        for chapter in good_chapters:
            try:
                # Get the raw extracted text from audiblez
                raw_text = chapter.extracted_text
                if not raw_text or len(raw_text.strip()) < 10:
                    continue
                
                # Process the text to separate titles from content and improve formatting
                processed_paragraphs = _process_audiblez_chapter_text(raw_text, chapter.get_name())
                
                if processed_paragraphs:
                    chapters.append(processed_paragraphs)
                    
            except Exception as e:
                console.print(f"[yellow]Warning: Error processing chapter {chapter.get_name()}: {e}[/yellow]")
                continue
        
        return chapters
        
    except Exception as e:
        console.print(f"[bold red]Error processing EPUB content: {e}[/bold red]")
        return []


def _process_audiblez_chapter_text(raw_text, chapter_name):
    """
    Process audiblez extracted text to separate titles from content and improve formatting.
    Addresses the issue where chapter titles get merged with content on the same line.
    """
    if not raw_text:
        return []
    
    # Split text into lines and clean them
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    if not lines:
        return []
    
    processed_paragraphs = []
    current_paragraph = []
    
    for i, line in enumerate(lines):
        # Apply global TTS cleaning
        cleaned_line = clean_text_for_tts(line)
        if not cleaned_line or len(cleaned_line) < 3:
            continue
        
        # Detect if this line is likely a chapter title or heading
        is_title = _is_likely_title(cleaned_line, i == 0)
        
        if is_title:
            # Finish current paragraph before adding title
            if current_paragraph:
                processed_paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
            
            # Add title with proper spacing
            processed_paragraphs.append('')  # Empty line before title
            processed_paragraphs.append(cleaned_line)
            processed_paragraphs.append('')  # Empty line after title
            
        else:
            # Regular content - split into sentences and group intelligently
            sentences = split_into_sentences(cleaned_line)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    current_paragraph.append(sentence)
                    
                    # Group 2-3 sentences per paragraph for better reading flow
                    if len(current_paragraph) >= 3:
                        processed_paragraphs.append(' '.join(current_paragraph))
                        current_paragraph = []
    
    # Add any remaining sentences
    if current_paragraph:
        processed_paragraphs.append(' '.join(current_paragraph))
    
    # Clean up excessive empty lines
    final_paragraphs = []
    empty_count = 0
    
    for para in processed_paragraphs:
        if para == '':
            empty_count += 1
            if empty_count <= 1:  # Allow only single empty lines
                final_paragraphs.append('')
        else:
            empty_count = 0
            final_paragraphs.append(para)
    
    return final_paragraphs


def _is_likely_title(text, is_first_line):
    """
    Determine if a line of text is likely a chapter title or heading.
    This helps separate titles from content to prevent them from being merged.
    """
    if not text:
        return False
    
    text = text.strip()
    
    # Very short lines are likely titles
    if len(text) < 50:
        # Check for title patterns
        if (text.isupper() or  # ALL CAPS
            text.istitle() or  # Title Case
            re.match(r'^Chapter\s+\d+', text, re.IGNORECASE) or  # "Chapter 1"
            re.match(r'^\d+\.?\s+', text) or  # "1. Title" or "1 Title"
            re.match(r'^[IVXLCDM]+\.?\s+', text, re.IGNORECASE) or  # Roman numerals
            not text.endswith('.') and not text.endswith('!') and not text.endswith('?')):  # No ending punctuation
            return True
    
    # First line of chapter is often a title if it's short and doesn't end with punctuation
    if is_first_line and len(text) < 100 and not text.endswith(('.', '!', '?')):
        return True
    
    # Lines that are clearly not titles
    if (len(text) > 200 or  # Too long
        text.endswith('.') or text.endswith('!') or text.endswith('?') or  # Ends with punctuation
        ' and ' in text.lower() or ' the ' in text.lower() or ' of ' in text.lower()):  # Contains common sentence words
        return False
    
    return False

def _extract_content_pdf(file_path, console):
    from . import config
    
    def is_footnote_block(block, page_height, bottom_margin):
        """
        Detect footnotes and page numbers in bottom margin of pages.
        Filters any text that starts in the bottom margin area.
        """
        x0, y0, x1, y1, text = block[:5]
        text = text.strip()
        
        # Check if block STARTS in the bottom margin
        if y0 < page_height * bottom_margin:
            return False
            
        # If we're in the bottom margin, apply additional checks
        if text:
            # Always filter very short text in bottom margin (likely page numbers)
            if len(text) < 20:
                return True
            
            # Filter text that looks like page numbers or footers
            # Page numbers: just digits, or digits with simple text
            if re.match(r'^\d+$', text):  # Just a number
                return True
            if re.match(r'^Page\s+\d+', text, re.IGNORECASE):  # "Page 123"
                return True
            if re.match(r'^\d+\s*[-–—]\s*\d+$', text):  # "123 - 456" (page ranges)
                return True
            if re.match(r'^\d+\s*/\s*\d+$', text):  # "123 / 456" (page x of y)
                return True
            
            # Filter footnote markers and footnotes
            if re.match(r'^\d+[\.\s]', text):  # "1. footnote text"
                return True
            if re.match(r'^[*†‡§¶]', text):  # Footnote symbols
                return True
            
            # Filter common footer patterns
            if len(text) < 100 and any(word in text.lower() for word in ['chapter', 'page', 'copyright', '©']):
                return True
                
        return False

    def is_header_block(block, page_height, top_margin):
        """Check if a block is in the header area"""
        block_y0 = block[1]  # Top Y coordinate of block
        return block_y0 < page_height * top_margin

    def clean_footnote_references(text):
        cleaned = re.sub(r'\[\d+\]', '', text)
        cleaned = re.sub(r'\[[a-zA-Z]\]', '', cleaned)
        cleaned = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', cleaned)
        cleaned = re.sub(r'[*†‡§¶]', '', cleaned)
        cleaned = re.sub(r'^\d+\.\s', '', cleaned)
        cleaned = ' '.join(cleaned.split())
        return cleaned

    def detect_repeated_headers(doc, console, repetition_threshold):
        """Detect headers by finding text that repeats in the same position across pages"""
        from collections import Counter
        
        all_text_blocks = []
        page_count = len(doc)
        
        # Collect all text blocks with their positions
        for page_num, page in enumerate(doc):
            page_height = page.rect.height
            page_width = page.rect.width
            blocks = page.get_text("blocks")
            
            for block in blocks:
                x0, y0, x1, y1, text = block[:5]
                text = text.strip()
                if text and len(text) > 2:
                    # Normalize position as percentage of page dimensions
                    norm_x = x0 / page_width
                    norm_y = y0 / page_height
                    
                    # Create a position key (rounded to handle slight variations)
                    pos_key = (round(norm_x, 2), round(norm_y, 2))
                    
                    # Remove page numbers from text for comparison
                    text_normalized = re.sub(r'\b\d+\b', '', text).strip()
                    if text_normalized:
                        all_text_blocks.append((pos_key, text_normalized, page_num))
        
        # Find text that appears in the same position on multiple pages
        position_text_counts = Counter()
        for pos_key, text, page_num in all_text_blocks:
            position_text_counts[(pos_key, text)] += 1
        
        # Identify headers using configurable threshold
        threshold = max(2, int(page_count * repetition_threshold))
        repeated_headers = set()
        
        for (pos_key, text), count in position_text_counts.items():
            if count >= threshold:
                repeated_headers.add((pos_key, text))
        
        return repeated_headers

    def is_repeated_header(block, page_height, page_width, repeated_headers):
        """Check if a block matches any of the detected repeated headers"""
        x0, y0, x1, y1, text = block[:5]
        text = text.strip()
        if not text:
            return False
            
        # Normalize position
        norm_x = round(x0 / page_width, 2)
        norm_y = round(y0 / page_height, 2)
        pos_key = (norm_x, norm_y)
        
        # Remove page numbers for comparison
        text_normalized = re.sub(r'\b\d+\b', '', text).strip()
        
        # Check if this matches any repeated header
        for header_pos, header_text in repeated_headers:
            if header_pos == pos_key and header_text == text_normalized:
                return True
        return False

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        console.print(f"[bold red]Error: Failed to open file with fitz: {e}[/bold red]")
        return []

    # Initialize filtering based on config
    repeated_headers = set()
    if config.PDF_FILTERS_ENABLED and config.PDF_FILTER_HEADERS_BY_REPETITION:
        repeated_headers = detect_repeated_headers(doc, console, config.PDF_HEADER_REPETITION_THRESHOLD)
    
    all_paragraphs = []
    headers_filtered = 0
    footnotes_filtered = 0
    
    for page in doc:
        page_height = page.rect.height
        page_width = page.rect.width
        main_content_blocks = []
        blocks = sorted(page.get_text("blocks"), key=lambda b: b[1])

        for block in blocks:
            # Skip footnotes (if enabled)
            if config.PDF_FILTERS_ENABLED and config.PDF_FILTER_FOOTNOTES and is_footnote_block(block, page_height, config.PDF_FOOTNOTE_BOTTOM_MARGIN):
                footnotes_filtered += 1
                continue
                
            # Skip headers by position (if enabled)
            if config.PDF_FILTERS_ENABLED and config.PDF_FILTER_HEADERS_BY_POSITION and is_header_block(block, page_height, config.PDF_HEADER_TOP_MARGIN):
                headers_filtered += 1
                continue
                
            # Skip repeated headers detected by pattern analysis (if enabled)
            if config.PDF_FILTERS_ENABLED and config.PDF_FILTER_HEADERS_BY_REPETITION and is_repeated_header(block, page_height, page_width, repeated_headers):
                headers_filtered += 1
                continue
                
            main_content_blocks.append(block)

        page_text = ""
        for block in main_content_blocks:
            block_text = block[4].replace('-\n', '').replace('\n', ' ').strip()
            page_text += block_text + " "
        
        cleaned_page_text = clean_footnote_references(page_text)
        paragraphs = cleaned_page_text.split('  ')
        
        for para in paragraphs:
            if len(para.strip()) > 25:
                cleaned_para = clean_text_for_tts(para.strip())
                if cleaned_para and len(cleaned_para) > 10:
                    all_paragraphs.append(cleaned_para)

    doc.close() 
    
    chapters = []
    current_chapter = []
    
    for paragraph in all_paragraphs:
        if "chapter" in paragraph.lower() and len(paragraph.split()) < 10:
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = [paragraph]
        else:
            current_chapter.append(paragraph)
            
    if current_chapter:
        chapters.append(current_chapter)
        
    if not chapters:
        return [all_paragraphs]

    return chapters

def _extract_content_txt(file_path, console):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            console.print(f"[bold red]Error: Failed to read TXT file: {e}[/bold red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error: Failed to read TXT file: {e}[/bold red]")
        return []

    # Normalize newlines to handle mixed cases
    content = content.replace('\r\n', '\n')
    
    # Attempt to split by double newline first
    paragraphs = [clean_text_for_tts(p.strip()) for p in content.split('\n\n') if p.strip()]
    paragraphs = [p for p in paragraphs if p and len(p) > 3]
    
    # If that results in very few paragraphs (i.e., the whole file is one paragraph),
    # and there are single newlines, then split by single newlines.
    if len(paragraphs) <= 1 and '\n' in content:
        paragraphs = [clean_text_for_tts(p.strip()) for p in content.split('\n') if p.strip()]
        paragraphs = [p for p in paragraphs if p and len(p) > 3]

    if not paragraphs:
        console.print("[bold red]No text content found in the TXT file.[/bold red]")
        return []

    return [paragraphs]


def _extract_content_docx(file_path, console):
    """
    Extracts content from a .docx file, preserving paragraphs.
    It uses the 'python-docx' library.
    """
    try:
        doc = Document(file_path)
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text and not para.text.isspace()])
        paragraphs = [clean_text_for_tts(p.strip()) for p in full_text.split('\n') if p.strip()]
        paragraphs = [p for p in paragraphs if p and len(p) > 3]
        
        return [paragraphs]
    except Exception as e:
        console.print(f"[bold red]Error: Failed to read DOCX file: {e}[/bold red]")
        return []
        
def _extract_content_doc(file_path, console):
    try:
        # Try using antiword first
        result = subprocess.run(
            ['antiword', file_path],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='ignore'
        )
        content = result.stdout.replace('\r\n', '\n').replace('\r', '\n')
        
        # Merge single newlines into spaces, keep paragraph breaks
        content = re.sub(r'(?<!\n)\n(?!\n)', ' ', content)
        content = re.sub(r' +', ' ', content)  # collapse multiple spaces
        
        lines = [clean_text_for_tts(line.strip()) for line in content.split('\n') if line.strip()]
        lines = [line for line in lines if line and len(line) > 3]
        return [lines]

    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            # Fallback: raw binary read
            with open(file_path, 'rb') as f:
                content = f.read()
            
            text = "".join(
                chr(c) for c in content
                if 32 <= c <= 126 or c in (9, 10, 13)
            )
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            
            # Merge single newlines into spaces, keep paragraph breaks
            text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
            text = re.sub(r' +', ' ', text)  # collapse multiple spaces
            
            lines = [clean_text_for_tts(line.strip()) for line in text.split('\n') if line.strip()]
            lines = [line for line in lines if line and len(line) > 3]
            return [lines]

        except Exception as e:
            console.print(f"[bold red]Error: Failed to read DOC file with fallback: {e}[/bold red]")
            return []

def _extract_content_rtf(file_path, console):
    """
    Extracts content from an .rtf file using the 'striprtf' library.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            rtf_content = f.read()
            
        text_content = rtf_to_text(rtf_content, errors="ignore")
        
        text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
        
        lines = [clean_text_for_tts(line.strip()) for line in text_content.split('\n') if line.strip()]
        lines = [line for line in lines if line and len(line) > 3]

        return [lines]
    except Exception as e:
        console.print(f"[bold red]Error: Failed to parse RTF file: {e}[/bold red]")
        return []


        
def _extract_content_md(file_path, console):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                md_content = f.read()
        except Exception as e:
            console.print(f"[bold red]Error: Failed to read Markdown file: {e}[/bold red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error: Failed to read Markdown file: {e}[/bold red]")
        return []

    try:
        # Use enhanced raw markdown parsing for better structure preservation
        return [_parse_raw_markdown(md_content)]
        
    except Exception as e:
        # If raw parsing fails, try HTML conversion as fallback
        try:
            html_content = markdown.markdown(md_content, extensions=['codehilite', 'fenced_code'])
            parser = HTMLtoLines()
            parser.feed(html_content)
            parser.close()
            
            lines = parser.get_lines()
            if lines:
                return [lines]
            else:
                console.print(f"[bold red]Error parsing Markdown content: {e}[/bold red]")
                return []
                
        except Exception as e2:
            console.print(f"[bold red]Error parsing Markdown content: {e2}[/bold red]")
            return []


def _parse_raw_markdown(md_content):
    """Parse raw markdown content while preserving structure"""
    lines = md_content.split('\n')
    result = []
    in_code_block = False
    code_fence = None
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Handle code blocks
        if line.startswith('```') or line.startswith('~~~'):
            if not in_code_block:
                # Starting a code block
                in_code_block = True
                code_fence = line[:3]
                result.append("")  # Add spacing before code block
                # Extract language if specified
                lang = line[3:].strip()
                if lang:
                    result.append(f"Code ({lang}):")
                else:
                    result.append("Code:")
                i += 1
                continue
            elif line.startswith(code_fence):
                # Ending a code block
                in_code_block = False
                code_fence = None
                result.append("")  # Add spacing after code block
                i += 1
                continue
        
        if in_code_block:
            # Inside code block - preserve indentation and mark as code to skip cleaning
            result.append(f"__CODE_BLOCK__    {line}")
        elif line.startswith('#'):
            # Headers
            level = len(line) - len(line.lstrip('#'))
            header_text = line.lstrip('# ').strip()
            if header_text:
                result.append("")
                result.append(header_text)
                result.append("")
        elif line.startswith(('- ', '* ', '+ ')) or re.match(r'^\d+\.\s', line):
            # List items
            if line.startswith(('- ', '* ', '+ ')):
                list_text = line[2:].strip()
                result.append(f"• {list_text}")
            else:
                # Numbered list
                list_text = re.sub(r'^\d+\.\s', '', line).strip()
                result.append(f"• {list_text}")
        elif re.match(r'^\s+(-|\*|\+|\d+\.)\s+', line):
            # Indented list items (should be cleaned, not treated as code)
            # Extract the list content after the indentation and list marker
            indented_list_text = re.sub(r'^\s+(-|\*|\+|\d+\.)\s+', '', line)
            result.append(f"    • {indented_list_text}")
        elif line.startswith('    ') or line.startswith('\t'):
            # Indented content (code blocks) - preserve formatting
            result.append(f"__CODE_BLOCK__    {line.strip()}")
        elif line.startswith('>'):
            # Blockquotes
            quote_text = line.lstrip('> ').strip()
            if quote_text:
                result.append(f"    {quote_text}")
        elif line.strip() == '':
            # Empty lines - preserve but limit consecutive ones
            if result and result[-1] != '':
                result.append('')
        else:
            # Regular paragraphs
            if line.strip():
                result.append(line.strip())
        
        i += 1
    
    # Apply global TTS-friendly cleaning to all lines
    result = [clean_text_for_tts(line) if line.strip() else line for line in result]
    
    # Clean up excessive empty lines
    clean_result = []
    empty_count = 0
    for line in result:
        if line == '':
            empty_count += 1
            if empty_count <= 2:
                clean_result.append(line)
        else:
            empty_count = 0
            clean_result.append(line)
    
    return [line for line in clean_result if line or len(clean_result) < 100]  # Keep empty lines for short docs



def extract_chapter_titles(chapters, file_path=None):
    """
    Extract chapter titles from the chapters data structure.
    For EPUB files, tries to use the actual TOC structure first.
    Returns a list of tuples: (chapter_index, title)
    """
    # Try to extract from EPUB TOC if file path is provided and it's an EPUB
    if file_path and file_path.lower().endswith('.epub'):
        epub_titles = _extract_epub_toc_titles(file_path, len(chapters))
        if epub_titles:
            return epub_titles
    
    # Fallback to pattern matching for non-EPUB files or when EPUB TOC extraction fails
    chapter_titles = []
    
    for chapter_idx, chapter in enumerate(chapters):
        title = f"Chapter {chapter_idx + 1}"  # Default title
        
        # Look for chapter title in the first few paragraphs
        for paragraph_idx, paragraph in enumerate(chapter[:3]):  # Check first 3 paragraphs
            if not paragraph.strip():
                continue
                
            # Check for common chapter title patterns
            paragraph_clean = paragraph.strip()
            
            # Pattern 1: "Chapter X: Title" or "Chapter X - Title"
            chapter_pattern = re.match(r'^Chapter\s+(\d+)[\s:.-]+(.+)$', paragraph_clean, re.IGNORECASE)
            if chapter_pattern:
                chapter_num = chapter_pattern.group(1)
                chapter_title = chapter_pattern.group(2).strip()
                title = f"Ch.{chapter_num}: {chapter_title}"
                break
                
            # Pattern 2: Just "Chapter X"
            chapter_only = re.match(r'^Chapter\s+(\d+)$', paragraph_clean, re.IGNORECASE)
            if chapter_only:
                chapter_num = chapter_only.group(1)
                title = f"Chapter {chapter_num}"
                break
                
            # Pattern 3: Numbered title like "1. Introduction"
            numbered_pattern = re.match(r'^(\d+)[\s.-]+(.+)$', paragraph_clean)
            if numbered_pattern:
                chapter_num = numbered_pattern.group(1)
                chapter_title = numbered_pattern.group(2).strip()
                title = f"{chapter_num}. {chapter_title}"
                break
                
            # Pattern 4: If first paragraph looks like a title (short, no punctuation at end)
            if (paragraph_idx == 0 and len(paragraph_clean) < 100 and 
                not paragraph_clean.endswith('.') and not paragraph_clean.endswith('!')):
                title = paragraph_clean[:50] + ("..." if len(paragraph_clean) > 50 else "")
                break
        
        chapter_titles.append((chapter_idx, title))
    
    return chapter_titles


def _extract_epub_toc_titles(file_path, num_chapters):
    """
    Extract chapter titles from EPUB's actual table of contents structure.
    Returns a list of tuples: (chapter_index, title) or None if extraction fails.
    """
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        return None
    
    try:
        # Open EPUB file
        book = epub.read_epub(file_path)
        
        # Get the table of contents
        toc_items = []
        
        # Method 1: Try to get TOC from book.toc
        if hasattr(book, 'toc') and book.toc:
            toc_items = _flatten_toc_structure(book.toc)
        
        # Method 2: If no TOC, try to get from NCX file
        if not toc_items:
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_NAVIGATION:
                    # Try to parse navigation document
                    try:
                        from bs4 import BeautifulSoup
                        nav_content = item.get_content().decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(nav_content, 'html.parser')
                        
                        # Look for nav elements or ol/li structures
                        nav_elements = soup.find_all(['nav', 'ol'])
                        for nav_elem in nav_elements:
                            links = nav_elem.find_all('a')
                            for link in links:
                                title = link.get_text(strip=True)
                                if title and len(title) > 1:
                                    toc_items.append(title)
                    except Exception:
                        continue
        
        # Method 3: If still no TOC, try to get from spine items with titles
        if not toc_items:
            spine_items = book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            for item in spine_items:
                # Try to get title from item properties or content
                title = getattr(item, 'title', None) or item.get_name()
                if title:
                    # Clean up the title
                    title = title.replace('.xhtml', '').replace('.html', '')
                    title = title.replace('_', ' ').replace('-', ' ')
                    title = ' '.join(word.capitalize() for word in title.split())
                    toc_items.append(title)
        
        # Convert to the expected format - only use actual TOC entries
        if toc_items:
            chapter_titles = []
            # Only create entries for TOC items that exist, don't pad with defaults
            actual_toc_count = min(len(toc_items), num_chapters)
            for i in range(actual_toc_count):
                title = toc_items[i]
                # Clean and format the title
                if len(title) > 60:
                    title = title[:57] + "..."
                chapter_titles.append((i, title))
            
            return chapter_titles
    
    except Exception as e:
        # If any error occurs, return None to fall back to pattern matching
        pass
    
    return None


def _flatten_toc_structure(toc):
    """
    Flatten the hierarchical TOC structure into a simple list of titles.
    """
    titles = []
    
    def extract_titles(items):
        for item in items:
            if hasattr(item, 'title'):
                titles.append(item.title)
            elif hasattr(item, '__iter__') and not isinstance(item, str):
                # Handle nested structures
                try:
                    extract_titles(item)
                except (TypeError, AttributeError):
                    pass
            elif isinstance(item, str):
                titles.append(item)
    
    try:
        extract_titles(toc)
    except Exception:
        pass
    
    return titles


def _extract_content_html(file_path, console):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            console.print(f"[bold red]Error: Failed to read HTML file: {e}[/bold red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error: Failed to read HTML file: {e}[/bold red]")
        return []

    try:
        parser = HTMLtoLines()
        parser.feed(content)
        parser.close()
        
        # Get clean lines
        lines = parser.get_lines()
        
        if not lines:
            console.print("[bold red]No text content found in the HTML file.[/bold red]")
            return []

        return [lines]
    except Exception as e:
        console.print(f"[bold red]Error: Failed to parse HTML file: {e}[/bold red]")
        return []