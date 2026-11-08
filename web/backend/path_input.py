"""Normalize paths pasted with Windows Explorer's Copy as path command."""


def clean_path_input(value):
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] in {'"', "'"} and text[-1] == text[0]:
        text = text[1:-1].strip()
    if "\x00" in text:
        raise ValueError("Path contains a null character")
    return text
