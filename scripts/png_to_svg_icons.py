#!/usr/bin/env python3
"""
Convert icon.png to SVG icons for AUR package
Creates scalable vector graphics from the existing PNG icon
"""

import os
import base64
from PIL import Image
import io

def png_to_svg_data_url(png_path):
    """Convert PNG to SVG with embedded data URL"""
    try:
        with open(png_path, 'rb') as f:
            png_data = f.read()
        
        # Encode PNG data as base64
        base64_data = base64.b64encode(png_data).decode('utf-8')
        data_url = f"data:image/png;base64,{base64_data}"
        
        return data_url
    except Exception as e:
        print(f"Error reading PNG file: {e}")
        return None

def create_svg_icon(size, data_url, filename):
    """Create SVG icon with embedded PNG data"""
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <image width="{size}" height="{size}" href="{data_url}"/>
</svg>'''
    
    return svg_content

def create_optimized_svg_icon(size, data_url, filename):
    """Create optimized SVG icon with proper scaling"""
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <image width="128" height="128" href="{data_url}"/>
</svg>'''
    
    return svg_content

def main():
    """Generate SVG icons from icon.png"""
    png_path = 'icon.png'
    
    # Check if icon.png exists
    if not os.path.exists(png_path):
        print(f"Error: {png_path} not found!")
        return
    
    # Create icons directory if it doesn't exist
    os.makedirs('icons', exist_ok=True)
    
    # Convert PNG to data URL
    print("Converting icon.png to SVG format...")
    data_url = png_to_svg_data_url(png_path)
    
    if not data_url:
        print("Failed to convert PNG to data URL")
        return
    
    # Standard icon sizes for AUR packages
    sizes = [16, 32, 48, 64, 128, 256, 512]
    
    print("Generating SVG icons for AUR package...")
    
    for size in sizes:
        # Create optimized SVG (uses viewBox for proper scaling)
        svg_content = create_optimized_svg_icon(size, data_url, f'asuc-{size}x{size}.svg')
        
        filename = f'icons/asuc-{size}x{size}.svg'
        with open(filename, 'w') as f:
            f.write(svg_content)
        print(f"Created {filename}")
    
    # Create default icon (128x128)
    default_svg = create_optimized_svg_icon(128, data_url, 'asuc.svg')
    with open('icons/asuc.svg', 'w') as f:
        f.write(default_svg)
    print("Created icons/asuc.svg (default)")
    
    # Create symbolic link for default icon
    try:
        if os.path.exists('icons/asuc-128x128.svg'):
            os.symlink('asuc-128x128.svg', 'icons/asuc-default.svg')
            print("Created symbolic link: icons/asuc-default.svg")
    except FileExistsError:
        print("Symbolic link already exists: icons/asuc-default.svg")
    
    print("\nSVG icon generation complete!")
    print("All icons are scalable and maintain the original design")
    print("Icons are ready for AUR package use")

if __name__ == '__main__':
    main() 