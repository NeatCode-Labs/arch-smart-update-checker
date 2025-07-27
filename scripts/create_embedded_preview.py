#!/usr/bin/env python3
"""
Create embedded preview of ASUC icons
Generates a self-contained HTML file with base64-encoded images
"""

import os
import glob
import base64

def image_to_base64(image_path):
    """Convert image file to base64 string"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def svg_to_base64(svg_path):
    """Convert SVG file to base64 string"""
    with open(svg_path, 'r') as f:
        svg_content = f.read()
    return base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')

def create_embedded_preview():
    """Create HTML preview with embedded images"""
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
            image-rendering: pixelated;
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
        .svg-item img {
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            margin-bottom: 10px;
        }
        .info-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .info-section code {
            background: #f0f0f0;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', monospace;
        }
    </style>
</head>
<body>
    <h1>Arch Smart Update Checker (ASUC) Icons Preview</h1>
    
    <div class="icon-section">
        <h2>PNG Icons - Main Design</h2>
        <div class="icon-grid">
'''
    
    # Add PNG icons with embedded base64
    png_files = sorted(glob.glob('icons/asuc-*.png'))
    for png_file in png_files:
        if 'alt' not in png_file:
            filename = os.path.basename(png_file)
            size = filename.replace('asuc-', '').replace('.png', '')
            
            # Convert to base64
            try:
                base64_data = image_to_base64(png_file)
                mime_type = 'image/png'
                img_src = f'data:{mime_type};base64,{base64_data}'
                
                html_content += f'''
            <div class="icon-item">
                <img src="{img_src}" alt="{filename}" title="{filename}" width="{size.split('x')[0]}" height="{size.split('x')[1]}">
                <div class="icon-name">{filename}</div>
                <div class="icon-size">{size}</div>
            </div>'''
            except Exception as e:
                print(f"Error processing {png_file}: {e}")
    
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
        
        try:
            base64_data = image_to_base64(png_file)
            mime_type = 'image/png'
            img_src = f'data:{mime_type};base64,{base64_data}'
            
            html_content += f'''
            <div class="icon-item">
                <img src="{img_src}" alt="{filename}" title="{filename}" width="{size.split('x')[0]}" height="{size.split('x')[1]}">
                <div class="icon-name">{filename}</div>
                <div class="icon-size">{size}</div>
            </div>'''
        except Exception as e:
            print(f"Error processing {png_file}: {e}")
    
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
        
        try:
            base64_data = svg_to_base64(svg_file)
            mime_type = 'image/svg+xml'
            img_src = f'data:{mime_type};base64,{base64_data}'
            
            html_content += f'''
            <div class="svg-item">
                <img src="{img_src}" alt="{filename}" title="{filename}" width="128" height="128">
                <div class="icon-name">{filename}</div>
                <div class="icon-size">Scalable Vector Graphics</div>
            </div>'''
        except Exception as e:
            print(f"Error processing {svg_file}: {e}")
    
    html_content += '''
        </div>
    </div>
    
    <div class="info-section">
        <h2>Usage Information</h2>
        <p><strong>For AUR Package:</strong> Use the PNG icons in your PKGBUILD to install them in the appropriate hicolor theme directories.</p>
        <p><strong>For Desktop Integration:</strong> The <code>asuc.desktop</code> file provides proper desktop menu integration.</p>
        <p><strong>For High-DPI Displays:</strong> The SVG icons provide the best scalability and quality.</p>
        <p><strong>PKGBUILD Integration:</strong> Copy the commands from <code>icons/PKGBUILD_ICON_SECTION.txt</code> to your PKGBUILD's package() function.</p>
    </div>
</body>
</html>'''
    
    return html_content

def main():
    """Create embedded icon preview HTML page"""
    print("Creating embedded icon preview page...")
    
    html_content = create_embedded_preview()
    
    with open('icons/preview-embedded.html', 'w') as f:
        f.write(html_content)
    
    print("Created icons/preview-embedded.html")
    print("This file contains embedded images and will work when opened directly in a browser")
    print("Open icons/preview-embedded.html to view all icons")

if __name__ == '__main__':
    main() 