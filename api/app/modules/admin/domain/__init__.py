"""Empty on purpose.

``admin`` owns no entities and no tables -- it reads leads through ``quotes``' repository port and
the catalog through ``catalog``'s. This package exists only so the "Domain forbids persistence" and
"Domain isolation" contracts in ``pyproject.toml`` can say *every* module's domain rather than
naming three of four; a module with nothing in it is the line that measures whether the migration
worked.
"""
