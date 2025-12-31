#!/bin/bash
# debug.sh - Debug script for PKGBUILD

set -x  # Turn on command tracing
set -e  # Exit on error

# Run makepkg with debug flags
makepkg --clean --syncdeps --install --noconfirm --log --verbose

# Show package info
pkgfile=$(ls -1t *.pkg.tar.zst | head -1)
echo "=== PACKAGE INFO ==="
tar -tvf "$pkgfile" | head -20