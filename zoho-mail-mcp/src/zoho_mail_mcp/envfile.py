"""Úprava .env súboru bez toho, aby sa hodnoty prepisovali rukou."""

from __future__ import annotations

from collections.abc import Mapping


def parse_env_text(text: str) -> dict[str, str]:
    """Prečíta .env súbor do slovníka. Komentáre a prázdne riadky ignoruje."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        value = value.strip()
        # Ak si niekto hodnotu obalil úvodzovkami, zhodíme ich.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def update_env_text(text: str, values: Mapping[str, str]) -> str:
    """Prepíše hodnoty známych kľúčov, ostatné riadky nechá tak.

    Kľúč, ktorý v súbore nie je, sa pridá na koniec. Komentáre, poradie
    riadkov aj neznáme kľúče zostávajú nedotknuté – v súbore býva aj to,
    čo tento skript nezaujíma.
    """
    remaining = dict(values)
    lines = text.splitlines()
    output: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)

    for key, value in remaining.items():
        output.append(f"{key}={value}")

    return "\n".join(output) + "\n"
