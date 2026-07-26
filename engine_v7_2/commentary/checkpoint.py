from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_utils import atomic_write_json, read_json


class CheckpointStore:
    """
    Enregistre l'état de progression du moteur V7.2.

    Un checkpoint est un petit fichier JSON permettant de reprendre un
    traitement interrompu. Il ne crée aucune copie du corpus et aucun
    fichier .bak.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, masechet: str) -> Path:
        safe = masechet.lower().replace(" ", "_")
        return self.directory / f"{safe}.v7_2.json"

    def load(self, masechet: str) -> dict[str, Any]:
        path = self.path_for(masechet)
        if not path.exists():
            return {}

        payload = read_json(path)
        return payload if isinstance(payload, dict) else {}

    def save(self, masechet: str, payload: dict[str, Any]) -> Path:
        path = self.path_for(masechet)
        atomic_write_json(path, payload)
        return path
