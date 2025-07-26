#!/usr/bin/env python3
"""
Debug Sync Checker
Simple debug tool to see what the sync checker is actually finding
"""

import os
import re
from pathlib import Path

def debug_sync():
    """Debug what the sync checker is finding"""
    print("🔍 Debug: What is the sync checker finding?")
    
    project_root = Path(os.getcwd())
    python_files = list(project_root.glob("**/*.py"))
    
    found_references = []
    
    for file_path in python_files:
        if file_path.name.startswith('.') or 'venv' in str(file_path) or '__pycache__' in str(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for the problematic references
            if 'trip_settings' in content.lower():
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'trip_settings' in line.lower():
                        found_references.append({
                            'file': str(file_path.relative_to(project_root)),
                            'line': i + 1,
                            'content': line.strip(),
                            'table': 'trip_settings'
                        })
            
            if 'information_schema' in content.lower():
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'information_schema' in line.lower():
                        found_references.append({
                            'file': str(file_path.relative_to(project_root)),
                            'line': i + 1,
                            'content': line.strip(),
                            'table': 'information_schema'
                        })
                        
        except Exception as e:
            print(f"   ⚠️  Warning: Could not analyze {file_path}: {e}")
    
    print(f"\n📋 Found {len(found_references)} references:")
    for ref in found_references:
        print(f"   📁 {ref['file']}:{ref['line']}")
        print(f"      🔍 {ref['table']}: {ref['content']}")
        print()

if __name__ == "__main__":
    debug_sync()
