#!/usr/bin/env python3
"""
Test script to verify verse number handling in EPUB parsing and TTS cleaning.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from lue.content_parser import _is_verse_number_element, _is_footnote_element
from lue.audio import clean_tts_text
from bs4 import BeautifulSoup

def test_verse_number_detection():
    """Test verse number element detection"""
    print("Testing verse number detection...")
    
    # Test HTML with verse numbers
    html_content = '''
    <div>
        <span class="verse">1</span>In the beginning God created the heaven and the earth.
        <span class="verse">2</span>And the earth was without form, and void.
        <span id="verse3">3</span>And God said, Let there be light.
        <span>4</span>And there was light.
        <span class="footnote">a</span>This is a footnote.
    </div>
    '''
    
    soup = BeautifulSoup(html_content, 'html.parser')
    spans = soup.find_all('span')
    
    for span in spans:
        text = span.get_text(strip=True)
        is_verse = _is_verse_number_element(span)
        is_footnote = _is_footnote_element(span)
        print(f"  Text: '{text}' | Verse: {is_verse} | Footnote: {is_footnote}")
    
    print()

def test_verse_marker_processing():
    """Test verse marker processing in UI"""
    print("Testing verse marker processing...")
    
    # Import the function from ui.py
    from lue.ui import _process_verse_markers
    
    test_text = "__VERSE__1__/VERSE__In the beginning God created the heaven and the earth. __VERSE__2__/VERSE__And the earth was without form, and void."
    
    styled_text = _process_verse_markers(test_text)
    print(f"  Input: {test_text}")
    print(f"  Processed: {styled_text.plain}")
    print()

def test_tts_cleaning():
    """Test TTS text cleaning with verse markers"""
    print("Testing TTS text cleaning...")
    
    test_cases = [
        "__VERSE__1__/VERSE__In the beginning God created the heaven and the earth.",
        "1 In the beginning God created the heaven and the earth.",
        "__VERSE__12__/VERSE__And God said, Let there be light: and there was light.",
        "Some regular text without verse numbers.",
    ]
    
    for text in test_cases:
        cleaned = clean_tts_text(text)
        print(f"  Original: {text}")
        print(f"  Cleaned:  {cleaned}")
        print()

def main():
    print("=== Verse Number Handling Test ===\n")
    
    test_verse_number_detection()
    test_verse_marker_processing()
    test_tts_cleaning()
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    main()
