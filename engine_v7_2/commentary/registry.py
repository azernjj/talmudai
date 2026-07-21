from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CommentaryDefinition:
    """
    Définition normalisée d’un commentaire talmudique.

    Attributes:
        key:
            Identifiant interne stable utilisé dans les chemins et les commandes.

        display_name:
            Nom destiné à l’affichage.

        sefaria_title:
            Préfixe utilisé pour construire les références Sefaria.
            Exemple : "Rashi on" produit "Rashi on Berakhot 2a".

        priority:
            Priorité éditoriale. Une valeur élevée signifie que le commentaire
            doit être présenté en premier au moteur de traduction.

        enabled:
            Indique si le commentaire peut être utilisé par défaut.

        source:
            Fournisseur principal des données.

        category:
            Catégorie intellectuelle du commentaire.

        aliases:
            Variantes reconnues pour retrouver le commentaire.

        description:
            Présentation courte du rôle du commentaire.
    """

    key: str
    display_name: str
    sefaria_title: str
    priority: int
    enabled: bool = True
    source: str = "sefaria"
    category: str = "commentary"
    aliases: tuple[str, ...] = ()
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["aliases"] = list(self.aliases)
        return payload


COMMENTARY_REGISTRY: dict[str, CommentaryDefinition] = {
    "rashi": CommentaryDefinition(
        key="rashi",
        display_name="Rachi",
        sefaria_title="Rashi on",
        priority=100,
        aliases=("rashi", "rachi", "רש״י", 'רש"י'),
        category="essential",
        description=(
            "Commentaire fondamental expliquant le vocabulaire, "
            "la structure et le sens immédiat de la Guemara."
        ),
    ),
    "tosafot": CommentaryDefinition(
        key="tosafot",
        display_name="Tossefot",
        sefaria_title="Tosafot on",
        priority=95,
        aliases=("tosafot", "tossefot", "תוספות"),
        category="essential",
        description=(
            "Analyse dialectique comparant les souguiot et soulevant "
            "les principales difficultés du texte."
        ),
    ),
    "ritva": CommentaryDefinition(
        key="ritva",
        display_name="Ritva",
        sefaria_title="Ritva on",
        priority=90,
        aliases=("ritva", "ritba", 'ריטב"א', "ריטב״א"),
        category="rishonim",
        description=(
            "Commentaire des Richonim développant le raisonnement "
            "et les conséquences halakhiques."
        ),
    ),
    "rosh": CommentaryDefinition(
        key="rosh",
        display_name="Roch",
        sefaria_title="Rosh on",
        priority=85,
        aliases=("rosh", "roch", 'רא"ש', "רא״ש"),
        category="rishonim",
        description=(
            "Synthèse talmudique et halakhique de Rabbénou Acher."
        ),
    ),
    "ran": CommentaryDefinition(
        key="ran",
        display_name="Ran",
        sefaria_title="Ran on",
        priority=84,
        aliases=("ran", 'ר"ן', "ר״ן"),
        category="rishonim",
        description=(
            "Analyse approfondie de la souguia et de ses implications halakhiques."
        ),
    ),
    "rashba": CommentaryDefinition(
        key="rashba",
        display_name="Rachba",
        sefaria_title="Rashba on",
        priority=83,
        aliases=("rashba", "rachba", 'רשב"א', "רשב״א"),
        category="rishonim",
        description=(
            "Commentaire analytique majeur de Rabbi Chelomo ben Aderet."
        ),
    ),
    "ramban": CommentaryDefinition(
        key="ramban",
        display_name="Ramban",
        sefaria_title="Ramban on",
        priority=82,
        aliases=("ramban", "nahmanides", 'רמב"ן', "רמב״ן"),
        category="rishonim",
        description=(
            "Commentaire de Rabbi Moché ben Na’hman sur les fondements "
            "conceptuels de la souguia."
        ),
    ),
    "maharsha": CommentaryDefinition(
        key="maharsha",
        display_name="Maharsha",
        sefaria_title="Chidushei Agadot on",
        priority=75,
        aliases=("maharsha", 'מהרש"א', "מהרש״א"),
        category="aharonim",
        description=(
            "Analyse des difficultés textuelles, logiques et aggadiques."
        ),
    ),
    "pnei-yehoshua": CommentaryDefinition(
        key="pnei-yehoshua",
        display_name="Pnei Yehoshoua",
        sefaria_title="Penei Yehoshua on",
        priority=72,
        aliases=(
            "pnei yehoshua",
            "penei yehoshua",
            "pnei-yehoshua",
            "פני יהושע",
        ),
        category="aharonim",
        description=(
            "Commentaire analytique approfondi des souguiot du Talmud."
        ),
    ),
    "ben-yehoyada": CommentaryDefinition(
        key="ben-yehoyada",
        display_name="Ben Yehoyada",
        sefaria_title="Ben Yehoyada on",
        priority=65,
        aliases=("ben yehoyada", "ben-yehoyada", "בן יהוידע"),
        category="aggadah",
        description=(
            "Commentaire de Rabbi Yossef ‘Haïm sur les passages aggadiques."
        ),
    ),
}


def normalize_commentary_key(value: str) -> str:
    """
    Transforme un nom de commentaire ou un alias en identifiant interne.

    Raises:
        KeyError:
            Si aucun commentaire enregistré ne correspond.
    """

    normalized = (
        value.strip()
        .lower()
        .replace("_", "-")
        .replace("’", "'")
        .replace("״", '"')
    )

    if normalized in COMMENTARY_REGISTRY:
        return normalized

    normalized_without_spaces = normalized.replace(" ", "-")

    if normalized_without_spaces in COMMENTARY_REGISTRY:
        return normalized_without_spaces

    for key, definition in COMMENTARY_REGISTRY.items():
        candidates = {
            alias.strip()
            .lower()
            .replace("_", "-")
            .replace("’", "'")
            .replace("״", '"')
            for alias in definition.aliases
        }

        if normalized in candidates or normalized_without_spaces in candidates:
            return key

    raise KeyError(f"Commentaire inconnu : {value}")


def get_commentary(value: str) -> CommentaryDefinition:
    """
    Retourne la définition complète d’un commentaire.
    """

    key = normalize_commentary_key(value)
    return COMMENTARY_REGISTRY[key]


def list_commentaries(
    *,
    enabled_only: bool = True,
    category: str | None = None,
) -> list[CommentaryDefinition]:
    """
    Retourne les commentateurs classés par priorité décroissante.
    """

    definitions = list(COMMENTARY_REGISTRY.values())

    if enabled_only:
        definitions = [
            definition
            for definition in definitions
            if definition.enabled
        ]

    if category:
        normalized_category = category.strip().lower()
        definitions = [
            definition
            for definition in definitions
            if definition.category.lower() == normalized_category
        ]

    return sorted(
        definitions,
        key=lambda definition: (
            -definition.priority,
            definition.display_name.lower(),
        ),
    )
