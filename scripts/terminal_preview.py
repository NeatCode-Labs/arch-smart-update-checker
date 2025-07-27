#!/usr/bin/env python3
"""
Terminal preview of ASUC icons
Shows a simple text-based preview of all generated icons
"""

import os
import glob

def get_file_size(filepath):
    """Get file size in human readable format"""
    size = os.path.getsize(filepath)
    for unit in ['B', 'KB', 'MB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"

def main():
    """Show terminal preview of icons"""
    print("🎨 ASUC Icons Preview")
    print("=" * 50)
    print()
    
    # Main PNG icons
    print("📱 PNG Icons - Main Design:")
    print("-" * 30)
    png_files = sorted(glob.glob('icons/asuc-*.png'))
    for png_file in png_files:
        if 'alt' not in png_file and 'asuc.png' not in png_file:
            filename = os.path.basename(png_file)
            size = filename.replace('asuc-', '').replace('.png', '')
            file_size = get_file_size(png_file)
            print(f"  {filename:<20} {size:<10} {file_size}")
    
    print()
    
    # Alternative PNG icons
    print("🔄 PNG Icons - Alternative Design:")
    print("-" * 35)
    alt_png_files = sorted(glob.glob('icons/asuc-alt-*.png'))
    for png_file in alt_png_files:
        filename = os.path.basename(png_file)
        size = filename.replace('asuc-alt-', '').replace('.png', '')
        file_size = get_file_size(png_file)
        print(f"  {filename:<20} {size:<10} {file_size}")
    
    print()
    
    # SVG icons
    print("📐 SVG Icons (Scalable Vector Graphics):")
    print("-" * 40)
    svg_files = glob.glob('icons/*.svg')
    for svg_file in svg_files:
        filename = os.path.basename(svg_file)
        file_size = get_file_size(svg_file)
        print(f"  {filename:<20} {'Scalable':<10} {file_size}")
    
    print()
    
    # Other files
    print("📄 Other Files:")
    print("-" * 15)
    other_files = ['asuc.desktop', 'README.md', 'PKGBUILD_ICON_SECTION.txt', 'SUMMARY.txt']
    for filename in other_files:
        filepath = os.path.join('icons', filename)
        if os.path.exists(filepath):
            file_size = get_file_size(filepath)
            print(f"  {filename:<25} {file_size}")
    
    print()
    print("📋 Summary:")
    print("-" * 10)
    total_png = len(png_files) + len(alt_png_files)
    total_svg = len(svg_files)
    total_files = len(os.listdir('icons'))
    
    print(f"  Total PNG icons: {total_png}")
    print(f"  Total SVG icons: {total_svg}")
    print(f"  Total files: {total_files}")
    print()
    
    print("💡 Usage:")
    print("-" * 8)
    print("  • Open 'icons/preview-embedded.html' in a browser for visual preview")
    print("  • Use PNG icons in PKGBUILD for desktop integration")
    print("  • Use SVG icons for high-DPI displays")
    print("  • Copy commands from 'icons/PKGBUILD_ICON_SECTION.txt' to your PKGBUILD")
    print()
    print("✅ Icon set ready for AUR package integration!")

if __name__ == '__main__':
    main() 