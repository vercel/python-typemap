#!/bin/sh

PEP=${1:-pep.rst}

scripts/py2rst.py tests/test_qblike_2.py --start "Begin PEP section" --end "End PEP section" \
  | scripts/rst_replace_section.py "$PEP" pep827-qb-impl -i


scripts/py2rst.py tests/test_dataclass_like.py --start "Begin PEP section: dataclass like" --end "End PEP section" \
  | scripts/rst_replace_section.py "$PEP" pep827-init-impl -i

scripts/py2rst.py tests/test_fastapilike_2.py --start "Begin PEP section: Automatically deriving FastAPI CRUD models" --end "End PEP section" \
  | scripts/rst_replace_section.py "$PEP" pep827-fastapi-impl -i

scripts/py2rst.py tests/test_nplike.py --start "Begin PEP section" --end "End PEP section" \
  | scripts/rst_replace_section.py "$PEP" pep827-numpy-impl -i
