import unicodedata
import re

def name_to_logical_key(name: str) -> str:
    """
    Convert a display name to a valid logical_key.
    Steps:
    1. Strip Win32 accelerator characters: '&' (e.g. "&File" → "File")
    2. Strip trailing colons and spaces (form labels often end with ':')
    3. Normalize unicode: decompose accents, keep ASCII only
       ("Prénom" → "Prenom", "Né(e)" → "Nee")
    4. Lowercase
    5. Replace any sequence of non-alphanumeric chars with a single underscore
    6. Strip leading/trailing underscores
    7. Truncate to 40 characters
    Returns "" if the result is empty.
    """
    if not name or not name.strip():
        return ""
    s = name.strip()
    s = s.replace("&", "")           # Win32 accelerator
    s = s.rstrip(": ")               # trailing label colon

    # Custom replacement for common special cases in French/English
    s = s.replace("(", "").replace(")", "")

    # Unicode normalization: decompose + ASCII-only
    nfkd = unicodedata.normalize("NFKD", s)
    s = nfkd.encode("ASCII", "ignore").decode("ASCII")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s[:40]
