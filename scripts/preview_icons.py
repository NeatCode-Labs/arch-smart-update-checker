#!/usr/bin/env python3
"""
Preview ASUC icons
Creates an HTML page to preview all generated icons
"""

import os
import glob

def create_preview_html():
    """Create HTML preview of all icons"""
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASUC Icons Preview</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #0D47A1;
            text-align: center;
            margin-bottom: 30px;
        }
        .icon-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .icon-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        .icon-item {
            text-align: center;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            background: #fafafa;
        }
        .icon-item img {
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            margin-bottom: 10px;
        }
        .icon-name {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        .icon-size {
            color: #666;
            font-size: 0.9em;
        }
        .svg-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .svg-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        .svg-item {
            text-align: center;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            background: #fafafa;
        }
        .svg-item svg {
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <h1>Arch Smart Update Checker (ASUC) Icons Preview</h1>
    
    <div class="icon-section">
        <h2>PNG Icons - Main Design</h2>
        <div class="icon-grid">
'''
    
    # Add PNG icons
    png_files = sorted(glob.glob('icons/asuc-*.png'))
    for png_file in png_files:
        if 'alt' not in png_file:
            filename = os.path.basename(png_file)
            size = filename.replace('asuc-', '').replace('.png', '')
            html_content += f'''
            <div class="icon-item">
                <img src="{png_file}" alt="{filename}" title="{filename}">
                <div class="icon-name">{filename}</div>
                <div class="icon-size">{size}</div>
            </div>'''
    
    html_content += '''
        </div>
    </div>
    
    <div class="icon-section">
        <h2>PNG Icons - Alternative Design</h2>
        <div class="icon-grid">
'''
    
    # Add alternative PNG icons
    alt_png_files = sorted(glob.glob('icons/asuc-alt-*.png'))
    for png_file in alt_png_files:
        filename = os.path.basename(png_file)
        size = filename.replace('asuc-alt-', '').replace('.png', '')
        html_content += f'''
            <div class="icon-item">
                <img src="{png_file}" alt="{filename}" title="{filename}">
                <div class="icon-name">{filename}</div>
                <div class="icon-size">{size}</div>
            </div>'''
    
    html_content += '''
        </div>
    </div>
    
    <div class="svg-section">
        <h2>SVG Icons (Scalable Vector Graphics)</h2>
        <div class="svg-grid">
'''
    
    # Add SVG icons
    svg_files = glob.glob('icons/*.svg')
    for svg_file in svg_files:
        filename = os.path.basename(svg_file)
        with open(svg_file, 'r') as f:
            svg_content = f.read()
        
        html_content += f'''
            <div class="svg-item">
                {svg_content}
                <div class="icon-name">{filename}</div>
                <div class="icon-size">Scalable Vector Graphics</div>
            </div>'''
    
    html_content += '''
        </div>
    </div>
    
    <div class="icon-section">
        <h2>Usage Information</h2>
        <p><strong>For AUR Package:</strong> Use the PNG icons in your PKGBUILD to install them in the appropriate hicolor theme directories.</p>
        <p><strong>For Desktop Integration:</strong> The <code>asuc.desktop</code> file provides proper desktop menu integration.</p>
        <p><strong>For High-DPI Displays:</strong> The SVG icons provide the best scalability and quality.</p>
    </div>
</body>
</html>'''
    
    return html_content

def main():
    """Create icon preview HTML page"""
    import os
    
    print("Creating icon preview page...")
    
    html_content = create_preview_html()
    
    with open('icons/preview.html', 'w') as f:
        f.write(html_content)
    
    print("Created icons/preview.html")
    print("Open this file in a web browser to preview all icons")
    
    # Also create a simple text summary
    summary = []
    summary.append("ASUC Icons Summary")
    summary.append("=" * 50)
    summary.append("")
    
    # Count PNG icons
    png_files = glob.glob('icons/*.png')
    svg_files = glob.glob('icons/*.svg')
    desktop_files = glob.glob('icons/*.desktop')
    
    summary.append(f"PNG Icons: {len(png_files)} files")
    summary.append(f"SVG Icons: {len(svg_files)} files")
    summary.append(f"Desktop Files: {len(desktop_files)} files")
    summary.append("")
    
    summary.append("Icon Sizes Available:")
    sizes = set()
    for png_file in png_files:
        if 'alt' not in png_file and 'asuc.png' not in png_file:
            size = os.path.basename(png_file).replace('asuc-', '').replace('.png', '')
            if 'x' in size:
                sizes.add(size)
    
    for size in sorted(sizes, key=lambda x: int(x.split('x')[0])):
        summary.append(f"  - {size}")
    
    summary.append("")
    summary.append("Files Created:")
    for file in sorted(os.listdir('icons')):
        summary.append(f"  - {file}")
    
    with open('icons/SUMMARY.txt', 'w') as f:
        f.write('\n'.join(summary))
    
    print("Created icons/SUMMARY.txt")
    print("\nIcon set complete! Ready for AUR package integration.")

if __name__ == '__main__':
    main() 