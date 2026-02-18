#!/bin/bash
# Icon generation script for Sage PWA
# This creates placeholder icons - replace with your custom Sage logo

echo "Creating PWA icons..."

cd "$(dirname "$0")/public"

# Check if ImageMagick is installed
if command -v convert &> /dev/null; then
    echo "Using ImageMagick to generate icons..."

    # Create 192x192 icon
    convert -size 192x192 xc:"#00ff88" \
        -fill "#0a0a0a" \
        -pointsize 120 \
        -gravity center \
        -annotate +0+0 "🧠" \
        icon-192.png

    # Create 512x512 icon
    convert -size 512x512 xc:"#00ff88" \
        -fill "#0a0a0a" \
        -pointsize 320 \
        -gravity center \
        -annotate +0+0 "🧠" \
        icon-512.png

    echo "✓ Icons created successfully!"
else
    echo "ImageMagick not found. Creating placeholder files..."
    echo "Please replace these with proper icons manually."

    # Create empty placeholder files
    touch icon-192.png
    touch icon-512.png

    echo "⚠ Placeholder files created. Install ImageMagick or add custom icons."
fi

echo ""
echo "Icon locations:"
echo "  - public/icon-192.png"
echo "  - public/icon-512.png"
echo ""
echo "You can replace these with custom Sage logo images."
