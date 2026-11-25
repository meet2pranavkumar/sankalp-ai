def csv_safe(value) -> str:
    """Spreadsheets run text that starts with = + - @ as a formula. Names and comments come from users, so defuse them."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text
