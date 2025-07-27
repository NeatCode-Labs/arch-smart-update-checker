#!/usr/bin/env python3
"""
Generate SVG icons from existing icon.svg for AUR package
Creates different sizes while preserving the vector quality
"""

import os
import re
from pathlib import Path

def read_svg_content(svg_path):
    """Read the SVG content from file"""
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading SVG file: {e}")
        return None

def create_sized_svg(svg_content, size, filename):
    """Create SVG with specific size while preserving viewBox"""
    # Extract the original viewBox if it exists
    viewbox_match = re.search(r'viewBox="([^"]*)"', svg_content)
    original_viewbox = viewbox_match.group(1) if viewbox_match else "0 0 1024 1024"
    
    # Create new SVG with specified size
    sized_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="{original_viewbox}">
{svg_content.split('<svg')[1].split('>', 1)[1].rsplit('</svg>', 1)[0]}
</svg>'''
    
    return sized_svg

def main():
    """Generate SVG icons in different sizes"""
    # Source SVG file
    source_svg = "icon.svg"
    
    # Check if source exists
    if not os.path.exists(source_svg):
        print(f"Error: {source_svg} not found!")
        return
    
    # Read source SVG content
    svg_content = read_svg_content(source_svg)
    if not svg_content:
        return
    
    # Create icons directory if it doesn't exist
    icons_dir = Path("icons")
    icons_dir.mkdir(exist_ok=True)
    
    # Standard icon sizes for AUR package
    sizes = [16, 32, 48, 64, 128, 256, 512]
    
    print("Generating SVG icons from icon.svg...")
    
    for size in sizes:
        filename = f"asuc-{size}x{size}.svg"
        filepath = icons_dir / filename
        
        # Create sized SVG
        sized_svg = create_sized_svg(svg_content, size, filename)
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(sized_svg)
        
        print(f"✅ Created {filename}")
    
    # Create default icon (128x128)
    default_svg = create_sized_svg(svg_content, 128, "asuc.svg")
    with open(icons_dir / "asuc.svg", 'w', encoding='utf-8') as f:
        f.write(default_svg)
    print("✅ Created asuc.svg (default)")
    
    # Create symbolic link for default
    try:
        if os.path.exists(icons_dir / "asuc-default.svg"):
            os.remove(icons_dir / "asuc-default.svg")
        os.symlink("asuc-128x128.svg", icons_dir / "asuc-default.svg")
        print("✅ Created asuc-default.svg symlink")
    except Exception as e:
        print(f"⚠️  Could not create symlink: {e}")
    
    print(f"\n🎉 Generated {len(sizes) + 1} SVG icons in {icons_dir}/")

if __name__ == "__main__":
    main() 