#!/usr/bin/env python3
"""
Test script to verify the EPUB TOC extraction fix.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lue'))

from lue import content_parser

def test_toc_extraction(epub_file_path):
    """Test the TOC extraction for an EPUB file."""
    print(f"Testing TOC extraction for: {epub_file_path}")
    
    # First, extract content to get chapters
    from rich.console import Console
    console = Console()
    
    print("1. Extracting content from EPUB...")
    chapters = content_parser.extract_content(epub_file_path, console)
    
    if not chapters:
        print("❌ Failed to extract content from EPUB")
        return False
    
    print(f"✅ Extracted {len(chapters)} chapters")
    
    # Test old method (pattern matching)
    print("\n2. Testing old method (pattern matching)...")
    old_titles = content_parser.extract_chapter_titles(chapters, None)  # No file path
    print("Old method titles:")
    for idx, title in old_titles[:5]:  # Show first 5
        print(f"  {idx}: {title}")
    
    # Test new method (EPUB TOC)
    print("\n3. Testing new method (EPUB TOC)...")
    new_titles = content_parser.extract_chapter_titles(chapters, epub_file_path)
    print("New method titles:")
    for idx, title in new_titles[:5]:  # Show first 5
        print(f"  {idx}: {title}")
    
    # Compare results
    print(f"\n4. Comparison:")
    print(f"   Old method found {len(old_titles)} titles")
    print(f"   New method found {len(new_titles)} titles")
    print(f"   Actual chapters in content: {len(chapters)}")
    
    # Check for phantom chapters
    phantom_chapters = len(old_titles) - len(chapters) if len(old_titles) > len(chapters) else 0
    if phantom_chapters > 0:
        print(f"   ⚠️  Old method has {phantom_chapters} phantom chapters")
    
    phantom_chapters_new = len(new_titles) - len(chapters) if len(new_titles) > len(chapters) else 0
    if phantom_chapters_new > 0:
        print(f"   ⚠️  New method has {phantom_chapters_new} phantom chapters")
    elif len(new_titles) <= len(chapters):
        print(f"   ✅ New method has no phantom chapters")
    
    if len(new_titles) > 0 and new_titles != old_titles:
        print("✅ New method produced different results!")
        return True
    else:
        print("⚠️  New method didn't improve results (may fallback to old method)")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_toc_fix.py <epub_file_path>")
        print("Example: python test_toc_fix.py sample.epub")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    if not os.path.exists(epub_file):
        print(f"Error: File '{epub_file}' not found")
        sys.exit(1)
    
    if not epub_file.lower().endswith('.epub'):
        print(f"Error: File '{epub_file}' is not an EPUB file")
        sys.exit(1)
    
    success = test_toc_extraction(epub_file)
    sys.exit(0 if success else 1)
