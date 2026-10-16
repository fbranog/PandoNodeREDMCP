import secrets


def new_id(existing: set[str] | None = None) -> str:
    while True:
        i = secrets.token_hex(8)
        if not existing or i not in existing:
            return i
