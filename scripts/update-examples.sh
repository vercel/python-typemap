#!/bin/sh

scripts/py2rst.py tests/test_qblike_2.py --start "Begin PEP section" --end "End PEP section" \
  | scripts/rst_replace_section.py pep.rst qb-impl -i


scripts/py2rst.py tests/test_dataclass_like.py --start "Begin PEP section: dataclass like" --end "End PEP section" \
  | scripts/rst_replace_section.py pep.rst init-impl -i

scripts/py2rst.py tests/test_fastapilike_2.py --start "Begin PEP section: Automatically deriving FastAPI CRUD models" --end "End PEP section" \
  | scripts/rst_replace_section.py pep.rst fastapi-impl -i

scripts/py2rst.py tests/test_nplike.py --start "Begin PEP section" --end "End PEP section" \
  | scripts/rst_replace_section.py pep.rst numpy-impl -i
