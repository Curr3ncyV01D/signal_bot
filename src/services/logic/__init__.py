"""
Lightweight package marker for logic services.

Do not import submodules here. Package-level reexports create side effects during
Python's package initialization and can easily introduce circular imports.
Callers should import concrete modules directly, for example:
`src.services.logic.trigger_engine` or `src.services.logic.billing_processor`.
"""

__all__: list[str] = []
