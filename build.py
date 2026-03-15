"""DualSoul build script — minify index.html for production.

Usage: python build.py
Output: web/index.min.html (served by main.py if it exists)
"""

import os
import re
import sys


def minify_css(css: str) -> str:
    """Simple CSS minification — remove comments and collapse whitespace."""
    # Remove CSS comments
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    # Collapse whitespace (but not inside strings)
    css = re.sub(r'\s+', ' ', css)
    # Remove spaces around special chars
    for ch in '{}:;,>+~':
        css = css.replace(f' {ch} ', ch).replace(f' {ch}', ch).replace(f'{ch} ', ch)
    return css.strip()


def minify_js(js: str) -> str:
    """Minify JS using rjsmin (fast, safe, no variable renaming)."""
    try:
        import rjsmin
        return rjsmin.jsmin(js)
    except ImportError:
        print("Warning: rjsmin not installed, skipping JS minification")
        return js


def minify_html(html: str) -> str:
    """Minify HTML — compress inline CSS and JS blocks."""
    # Minify inline <style> blocks
    def minify_style_block(m):
        return f'<style>{minify_css(m.group(1))}</style>'

    html = re.sub(
        r'<style>(.*?)</style>',
        minify_style_block,
        html,
        flags=re.DOTALL,
    )

    # Minify inline <script> blocks (but not external scripts with src=)
    def minify_script_block(m):
        tag_open = m.group(1)
        if 'src=' in tag_open:
            return m.group(0)  # Don't touch external scripts
        content = m.group(2)
        return f'{tag_open}{minify_js(content)}</script>'

    html = re.sub(
        r'(<script[^>]*>)(.*?)</script>',
        minify_script_block,
        html,
        flags=re.DOTALL,
    )

    # Collapse HTML whitespace (between tags only)
    html = re.sub(r'>\s+<', '><', html)

    return html


def main():
    src = os.path.join(os.path.dirname(__file__), 'web', 'index.html')
    dst = os.path.join(os.path.dirname(__file__), 'web', 'index.min.html')

    if not os.path.exists(src):
        print(f"Error: {src} not found")
        sys.exit(1)

    with open(src, encoding='utf-8') as f:
        original = f.read()

    minified = minify_html(original)

    with open(dst, 'w', encoding='utf-8') as f:
        f.write(minified)

    orig_size = len(original.encode('utf-8'))
    min_size = len(minified.encode('utf-8'))
    ratio = (1 - min_size / orig_size) * 100

    print(f"Original:  {orig_size:>8,} bytes")
    print(f"Minified:  {min_size:>8,} bytes")
    print(f"Saved:     {orig_size - min_size:>8,} bytes ({ratio:.1f}%)")
    print(f"Output:    {dst}")

    # Auto-update SW cache version from content hash
    import hashlib

    sw_path = os.path.join(os.path.dirname(__file__), 'web', 'sw.js')
    if os.path.exists(sw_path):
        content_hash = hashlib.md5(minified.encode('utf-8')).hexdigest()[:8]
        with open(sw_path, 'r', encoding='utf-8') as f:
            sw_content = f.read()
        new_sw = re.sub(
            r"const CACHE_NAME = 'dualsoul-v\w+';",
            f"const CACHE_NAME = 'dualsoul-v{content_hash}';",
            sw_content,
        )
        if new_sw != sw_content:
            with open(sw_path, 'w', encoding='utf-8') as f:
                f.write(new_sw)
            print(f"SW cache:  dualsoul-v{content_hash}")


if __name__ == '__main__':
    main()
