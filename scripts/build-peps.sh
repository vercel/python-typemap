#!/bin/sh -ex

export LANG=C.utf8

mkdir -p build
cd build
if [ ! -d peps ]; then
    git clone --depth=1 https://github.com/python/peps/
fi
cd peps/peps
if [ ! -s pep-9999.rst ]; then
    ln -s ../../../pre-pep.rst pep-9999.rst
fi
cd ..
make html || true
rm -rf ../html
cp -r build ../html

find .venv
