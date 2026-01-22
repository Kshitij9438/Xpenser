#!/usr/bin/env python3
"""
Debug the date parsing issue
"""

import re
from datetime import datetime

# Test the exact pattern
text = "how much have I spent through netbanking on 8th of August 2025"
pattern = r'(\d{1,2})[st|nd|rd|th]?\s+of\s+(\w+)\s+(\d{4})'

print(f"Testing text: {text}")
print(f"Pattern: {pattern}")

match = re.search(pattern, text, re.IGNORECASE)
if match:
    print(f"Match found: {match.group(0)}")
    print(f"Groups: {match.groups()}")
else:
    print("No match found")

# Test dateparser
try:
    import dateparser
    print(f"Dateparser available: {dateparser}")
    parsed = dateparser.parse("8th of August 2025")
    print(f"Parsed date: {parsed}")
except Exception as e:
    print(f"Dateparser error: {e}")
