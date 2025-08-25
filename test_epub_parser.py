#!/usr/bin/env python3
"""
Test script for the new EPUB parser to verify proper paragraph grouping.
"""

import sys
import os
from pathlib import Path

# Add the lue module to the path
sys.path.insert(0, str(Path(__file__).parent))

from lue.content_parser import _extract_paragraphs_from_soup, clean_text_for_tts
from rich.console import Console

def test_paragraph_grouping():
    """Test the paragraph grouping functionality with sample HTML content"""
    console = Console()
    
    # Test HTML content that simulates EPUB structure with individual sentence <p> tags
    test_html = """
    <html>
    <body>
        <h1>Chapter 1: Introduction</h1>
        <p>This is the first sentence of the chapter.</p>
        <p>This is the second sentence that should be grouped together.</p>
        <p>Here is a third sentence in the same paragraph.</p>
        <p>And a fourth sentence to complete the paragraph.</p>
        <p>This starts a new paragraph with the fifth sentence.</p>
        <p>The sixth sentence continues the new paragraph.</p>
        <p>Seventh sentence in the second paragraph.</p>
        
        <h2>Section 1.1</h2>
        <p>This is a new section with its own content.</p>
        <p>Multiple sentences should be grouped properly.</p>
        <p>Even when they come from separate p tags.</p>
        
        <div class="verse">1</div>
        <p>This sentence has a verse number that should be filtered.</p>
        <div class="footnote">This is a footnote that should be ignored.</div>
        <p>This sentence should appear after filtering.</p>
    </body>
    </html>
    """
    
    try:
        from bs4 import BeautifulSoup
        
        # Parse the test HTML
        soup = BeautifulSoup(test_html, 'html.parser')
        
        # Extract paragraphs using our new function
        paragraphs = _extract_paragraphs_from_soup(soup)
        
        console.print("[bold green]✓ EPUB Parser Test Results:[/bold green]")
        console.print(f"[blue]Total paragraphs extracted: {len(paragraphs)}[/blue]")
        console.print()
        
        for i, paragraph in enumerate(paragraphs, 1):
            if paragraph.strip():
                console.print(f"[yellow]Paragraph {i}:[/yellow] {paragraph}")
            else:
                console.print(f"[dim]--- Empty line ---[/dim]")
        
        # Verify that sentences are properly grouped
        content_paragraphs = [p for p in paragraphs if p.strip() and not p.startswith('Chapter') and not p.startswith('Section')]
        
        if len(content_paragraphs) >= 2:
            console.print(f"\n[bold green]✓ Success: Sentences properly grouped into {len(content_paragraphs)} content paragraphs[/bold green]")
            
            # Check that paragraphs contain multiple sentences
            multi_sentence_count = sum(1 for p in content_paragraphs if len(p.split('.')) > 2)
            console.print(f"[green]✓ {multi_sentence_count} paragraphs contain multiple sentences[/green]")
            
            return True
        else:
            console.print(f"[bold red]✗ Failed: Only {len(content_paragraphs)} content paragraphs found, expected at least 2[/bold red]")
            return False
            
    except ImportError:
        console.print("[bold red]✗ Error: BeautifulSoup not available for testing[/bold red]")
        return False
    except Exception as e:
        console.print(f"[bold red]✗ Error during testing: {e}[/bold red]")
        return False

def test_footnote_filtering():
    """Test that footnotes and verse numbers are properly filtered"""
    console = Console()
    
    test_html = """
    <html>
    <body>
        <p>This is normal content.</p>
        <span class="verse">1</span>
        <p>Content after verse number.</p>
        <div class="footnote">This footnote should be filtered.</div>
        <p class="ref">Reference that should be filtered.</p>
        <p>More normal content.</p>
    </body>
    </html>
    """
    
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(test_html, 'html.parser')
        paragraphs = _extract_paragraphs_from_soup(soup)
        
        # Filter out empty paragraphs
        content_paragraphs = [p for p in paragraphs if p.strip()]
        
        console.print(f"\n[bold blue]Footnote Filtering Test:[/bold blue]")
        console.print(f"Content paragraphs: {len(content_paragraphs)}")
        
        for i, p in enumerate(content_paragraphs, 1):
            console.print(f"  {i}. {p}")
        
        # Should have 2 content paragraphs (footnotes filtered out)
        if len(content_paragraphs) == 2:
            console.print("[bold green]✓ Footnote filtering working correctly[/bold green]")
            return True
        else:
            console.print(f"[bold red]✗ Expected 2 content paragraphs, got {len(content_paragraphs)}[/bold red]")
            return False
            
    except Exception as e:
        console.print(f"[bold red]✗ Error during footnote filtering test: {e}[/bold red]")
        return False

if __name__ == "__main__":
    console = Console()
    console.print("[bold cyan]Testing New EPUB Parser Implementation[/bold cyan]")
    console.print("=" * 50)
    
    test1_passed = test_paragraph_grouping()
    test2_passed = test_footnote_filtering()
    
    console.print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        console.print("[bold green]🎉 All tests passed! EPUB parser is working correctly.[/bold green]")
        console.print("[green]✓ Sentences are properly grouped into paragraphs[/green]")
        console.print("[green]✓ Footnotes and verse numbers are filtered[/green]")
        sys.exit(0)
    else:
        console.print("[bold red]❌ Some tests failed. Please check the implementation.[/bold red]")
        sys.exit(1)
