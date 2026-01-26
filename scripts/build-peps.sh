#!/bin/sh -e

echo LANG: $LANG

echo locale:
locale

echo "locale -a:"
locale -a

# Load the default locale in a python script. Sphinx does this.
python3 -c 'import locale; locale.setlocale(locale.LC_ALL, "")'

mkdir -p build/html
echo 'OK' > build/html/index.html
