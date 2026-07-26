from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .json_utils import atomic_write_json
from .loader import get_dapim, get_segments


def _ensure_dict(value: Any) -> dict[str, Any]:
    """
    Retourne une copie dictionnaire sûre.

    Cette fonction évite de partager par erreur des références mutables
    entre le résultat du pipeline et le document du corpus.
    """
    if isinstance(value, dict):
        return deepcopy(value)
    return {}


def _ensure_list(value: Any) -> list[Any]:
    """Retourne une copie de liste sûre."""
    if isinstance(value, list):
        return deepcopy(value)
    return []


def _ensure_text(value: Any) -> str:
    """Convertit une valeur en chaîne propre."""
    if value is None:
        return ""
    return str(value).strip()


def _ensure_number(value: Any, default: float = 0.0) -> float:
    """
    Convertit une valeur en nombre sans interrompre l'écriture du corpus.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_editorial_payload(
    *,
    final: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Construit le bloc technique et éditorial conservé dans le segment.

    Les métadonnées du pipeline sont incluses sans supprimer les champs
    historiques utilisés par les outils V7.1.
    """
    metadata_copy = _ensure_dict(metadata)

    return {
        "sources_used": _ensure_list(
            final.get("sources_used", [])
        ),
        "confidence": _ensure_number(
            final.get("confidence", 0.0)
        ),
        "review_note": _ensure_text(
            final.get("review_note", "")
        ),
        "issues": _ensure_list(
            final.get("issues", [])
        ),
        **metadata_copy,
    }


def _validate_final_payload(final: dict[str, Any]) -> None:
    """
    Vérifie que le résultat contient les données minimales nécessaires
    avant toute modification du document source.
    """
    if not isinstance(final, dict):
        raise TypeError(
            "final doit être un dictionnaire."
        )

    translation = final.get("translation_fr")
    explanation = final.get("explanation_fr")
    html = final.get("html")

    if not isinstance(translation, str) or not translation.strip():
        raise ValueError(
            "final.translation_fr est vide ou invalide."
        )

    if not isinstance(explanation, str):
        raise ValueError(
            "final.explanation_fr doit être une chaîne."
        )

    if not isinstance(html, str):
        raise ValueError(
            "final.html doit être une chaîne."
        )

    study = final.get("study")
    if study is not None and not isinstance(study, dict):
        raise ValueError(
            "final.study doit être un objet lorsqu'il est présent."
        )


def apply_translation_to_segment(
    *,
    document: dict[str, Any],
    daf: str,
    segment_index: int,
    final: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    """
    Applique le résultat éditorial V7.2 à un segment du corpus.

    Champs historiques conservés :
    - fr
    - fr_explanation
    - fr_html
    - fr_editorial

    Nouveau champ V7.2 :
    - study

    Le champ `study` contient la structure complète destinée à l'étude :
    traduction, explication, commentaires, halakha, applications,
    glossaire, résumé, points clés et références.
    """
    if not isinstance(document, dict):
        raise TypeError(
            "document doit être un dictionnaire."
        )

    if not isinstance(daf, str) or not daf.strip():
        raise ValueError(
            "daf doit être une chaîne non vide."
        )

    if not isinstance(segment_index, int):
        raise TypeError(
            "segment_index doit être un entier."
        )

    if not isinstance(metadata, dict):
        raise TypeError(
            "metadata doit être un dictionnaire."
        )

    _validate_final_payload(final)

    dapim = get_dapim(document)

    if daf not in dapim:
        raise KeyError(
            f"Daf {daf} introuvable."
        )

    segments = get_segments(dapim[daf])

    if segment_index < 0 or segment_index >= len(segments):
        raise IndexError(
            "Segment hors limites."
        )

    segment = segments[segment_index]

    if not isinstance(segment, dict):
        raise TypeError(
            "Le segment ciblé doit être un dictionnaire."
        )

    translation = _ensure_text(
        final["translation_fr"]
    )
    explanation = _ensure_text(
        final["explanation_fr"]
    )
    html = _ensure_text(
        final["html"]
    )

    segment["fr"] = translation
    segment["fr_explanation"] = explanation
    segment["fr_html"] = html
    segment["fr_editorial"] = _build_editorial_payload(
        final=final,
        metadata=metadata,
    )

    study = final.get("study")

    if isinstance(study, dict):
        study_copy = deepcopy(study)

        # Cohérence stricte entre les champs historiques et V7.2.
        study_copy["translation"] = translation
        study_copy["explanation"] = explanation

        segment["study"] = study_copy
    else:
        # Compatibilité avec un ancien résultat ne contenant pas encore
        # de bloc study.
        segment["study"] = {
            "translation": translation,
            "explanation": explanation,
            "commentaries": {},
            "halakha": {
                "available": False,
                "text": "",
                "sources": [],
            },
            "applications": [],
            "glossary": [],
            "summary": "",
            "key_points": [],
            "references": [],
            "confidence": _ensure_number(
                final.get("confidence", 0.0)
            ),
            "issues": _ensure_list(
                final.get("issues", [])
            ),
            "review_note": _ensure_text(
                final.get("review_note", "")
            ),
        }


def save_document(
    path: str | Path,
    document: dict[str, Any],
) -> None:
    """
    Sauvegarde atomiquement le document JSON.

    Le parent est créé si nécessaire afin d'éviter une erreur lors de
    l'écriture dans un nouveau répertoire de sortie.
    """
    if not isinstance(document, dict):
        raise TypeError(
            "document doit être un dictionnaire."
        )

    output_path = Path(path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    atomic_write_json(
        output_path,
        document,
    )
