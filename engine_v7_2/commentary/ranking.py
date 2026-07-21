from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .loader import LoadedDaf
from .models import CommentaryComment
from .registry import get_commentary


@dataclass
class CommentaryRankingWeights:
    """
    Pondérations utilisées pour calculer la qualité d’un commentaire.

    La priorité éditoriale du commentateur reste le critère principal.
    Les autres valeurs permettent de départager plusieurs commentaires
    appartenant au même commentateur ou au même daf.
    """

    priority_multiplier: float = 10.0
    hebrew_content: float = 30.0
    french_translation: float = 18.0
    english_translation: float = 5.0
    precise_reference: float = 10.0
    base_reference: float = 8.0
    dibur_hamatchil: float = 12.0
    segment_reference: float = 5.0
    metadata_bonus: float = 2.0
    substantial_content: float = 12.0
    long_content: float = 6.0
    empty_penalty: float = 500.0


@dataclass
class RankedComment:
    """
    Commentaire enrichi avec son score de classement.
    """

    commentary_key: str
    commentary: str
    priority: int
    masechet: str
    daf: str
    comment: CommentaryComment
    score: float
    original_position: int = 0
    source_path: str = ""
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "commentary_key": self.commentary_key,
            "commentary": self.commentary,
            "priority": self.priority,
            "masechet": self.masechet,
            "daf": self.daf,
            "score": self.score,
            "original_position": self.original_position,
            "source_path": self.source_path,
            "reasons": list(self.reasons),
            "comment": self.comment.to_dict(),
        }


@dataclass
class CommentaryRankingResult:
    """
    Résultat final du classement d’un ou plusieurs commentaires.
    """

    masechet: str
    daf: str
    comments: list[RankedComment] = field(default_factory=list)
    total_candidates: int = 0
    excluded_empty: int = 0
    excluded_duplicates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "masechet": self.masechet,
            "daf": self.daf,
            "total_candidates": self.total_candidates,
            "selected_comments": len(self.comments),
            "excluded_empty": self.excluded_empty,
            "excluded_duplicates": self.excluded_duplicates,
            "comments": [
                ranked.to_dict()
                for ranked in self.comments
            ],
        }

    def comment_count(self) -> int:
        return len(self.comments)

    def commentary_keys(self) -> list[str]:
        keys: list[str] = []

        for ranked in self.comments:
            if ranked.commentary_key not in keys:
                keys.append(ranked.commentary_key)

        return keys

    def comments_by_commentary(
        self,
    ) -> dict[str, list[RankedComment]]:
        grouped: dict[str, list[RankedComment]] = {}

        for ranked in self.comments:
            grouped.setdefault(
                ranked.commentary_key,
                [],
            ).append(ranked)

        return grouped


class CommentaryRanker:
    """
    Classe les commentaires disponibles pour le moteur TALMUD AI.

    Le classement s’effectue en deux niveaux :

    1. priorité éditoriale du commentateur ;
    2. qualité et richesse du commentaire individuel.

    Par défaut, Rachi reste donc avant Tossefot, Ritva et Roch lorsque
    tous sont présents, conformément au registre.
    """

    def __init__(
        self,
        *,
        weights: CommentaryRankingWeights | None = None,
        remove_duplicates: bool = True,
        exclude_empty: bool = True,
    ) -> None:
        self.weights = weights or CommentaryRankingWeights()
        self.remove_duplicates = remove_duplicates
        self.exclude_empty = exclude_empty

    def score_comment(
        self,
        comment: CommentaryComment,
        *,
        priority: int,
    ) -> tuple[float, list[str]]:
        """
        Calcule le score d’un commentaire individuel.
        """

        score = (
            float(priority)
            * self.weights.priority_multiplier
        )

        reasons = [
            f"priorité éditoriale {priority}",
        ]

        if not comment.has_content():
            score -= self.weights.empty_penalty
            reasons.append("commentaire vide")
            return score, reasons

        hebrew = comment.he.strip()
        french = comment.fr.strip()
        english = comment.en.strip()

        if hebrew:
            score += self.weights.hebrew_content
            reasons.append("texte hébreu présent")

        if french:
            score += self.weights.french_translation
            reasons.append("traduction française présente")

        if english:
            score += self.weights.english_translation
            reasons.append("traduction anglaise présente")

        if comment.ref.strip():
            score += self.weights.precise_reference
            reasons.append("référence précise présente")

        if comment.base_ref.strip():
            score += self.weights.base_reference
            reasons.append("référence de base présente")

        if comment.dibur_hamatchil.strip():
            score += self.weights.dibur_hamatchil
            reasons.append("dibur hamatchil présent")

        if comment.segment not in (None, ""):
            score += self.weights.segment_reference
            reasons.append("segment associé")

        if comment.metadata:
            score += self.weights.metadata_bonus
            reasons.append("métadonnées présentes")

        content_length = max(
            len(hebrew),
            len(french),
            len(english),
        )

        if content_length >= 120:
            score += self.weights.substantial_content
            reasons.append("contenu substantiel")

        if content_length >= 500:
            score += self.weights.long_content
            reasons.append("contenu long")

        return score, reasons

    def rank_loaded_daf(
        self,
        loaded_daf: LoadedDaf,
        *,
        limit: int | None = None,
    ) -> CommentaryRankingResult:
        """
        Classe les commentaires d’un seul commentateur pour un daf.
        """

        return self.rank_loaded_dapim(
            [loaded_daf],
            limit=limit,
        )

    def rank_loaded_dapim(
        self,
        loaded_dapim: Iterable[LoadedDaf],
        *,
        limit: int | None = None,
        per_commentary_limit: int | None = None,
    ) -> CommentaryRankingResult:
        """
        Classe plusieurs commentaires disponibles pour le même daf.

        Args:
            loaded_dapim:
                Résultats issus de CommentaryLoader.load_available_daf().

            limit:
                Nombre maximal total de commentaires à conserver.

            per_commentary_limit:
                Nombre maximal de commentaires conservés pour chaque
                commentateur.
        """

        loaded_list = list(loaded_dapim)

        masechet = ""
        daf = ""

        if loaded_list:
            masechet = loaded_list[0].masechet
            daf = loaded_list[0].daf

        result = CommentaryRankingResult(
            masechet=masechet,
            daf=daf,
        )

        ranked_comments: list[RankedComment] = []
        seen: set[tuple[str, str, str, str, str]] = set()

        for loaded in loaded_list:
            priority = self._resolve_priority(loaded)

            for position, comment in enumerate(
                loaded.comments
            ):
                result.total_candidates += 1

                if (
                    self.exclude_empty
                    and not comment.has_content()
                ):
                    result.excluded_empty += 1
                    continue

                duplicate_key = self._duplicate_key(
                    loaded.commentary_key,
                    comment,
                )

                if (
                    self.remove_duplicates
                    and duplicate_key in seen
                ):
                    result.excluded_duplicates += 1
                    continue

                seen.add(duplicate_key)

                score, reasons = self.score_comment(
                    comment,
                    priority=priority,
                )

                ranked_comments.append(
                    RankedComment(
                        commentary_key=(
                            loaded.commentary_key
                        ),
                        commentary=loaded.commentary,
                        priority=priority,
                        masechet=loaded.masechet,
                        daf=loaded.daf,
                        comment=comment,
                        score=score,
                        original_position=position,
                        source_path=loaded.source_path,
                        reasons=reasons,
                    )
                )

        ranked_comments.sort(
            key=self._sort_key,
        )

        if per_commentary_limit is not None:
            ranked_comments = (
                self._apply_per_commentary_limit(
                    ranked_comments,
                    per_commentary_limit,
                )
            )

        if limit is not None:
            ranked_comments = ranked_comments[:limit]

        result.comments = ranked_comments

        return result

    def select_for_translation(
        self,
        loaded_dapim: Iterable[LoadedDaf],
        *,
        max_comments: int = 12,
        max_per_commentary: int = 4,
    ) -> CommentaryRankingResult:
        """
        Sélectionne un ensemble raisonnable de commentaires pour le
        moteur de traduction ou d’étude détaillée.

        Cette méthode évite qu’un seul commentateur très abondant occupe
        toute la sélection.
        """

        if max_comments < 1:
            raise ValueError(
                "max_comments doit être supérieur ou égal à 1."
            )

        if max_per_commentary < 1:
            raise ValueError(
                "max_per_commentary doit être supérieur ou égal à 1."
            )

        return self.rank_loaded_dapim(
            loaded_dapim,
            limit=max_comments,
            per_commentary_limit=max_per_commentary,
        )

    def rank_raw_comments(
        self,
        commentary: str,
        masechet: str,
        daf: str,
        comments: Iterable[CommentaryComment],
        *,
        source_path: str = "",
        limit: int | None = None,
    ) -> CommentaryRankingResult:
        """
        Classe directement une liste de CommentaryComment.
        """

        definition = get_commentary(commentary)

        loaded = LoadedDaf(
            commentary_key=definition.key,
            commentary=definition.display_name,
            priority=definition.priority,
            masechet=masechet,
            daf=daf,
            comments=list(comments),
            source_path=source_path,
        )

        return self.rank_loaded_daf(
            loaded,
            limit=limit,
        )

    @staticmethod
    def _sort_key(
        ranked: RankedComment,
    ) -> tuple[float, int, str, int]:
        """
        Ordre de classement :

        - score décroissant ;
        - priorité décroissante ;
        - commentaire ;
        - position d’origine.
        """

        return (
            -ranked.score,
            -ranked.priority,
            ranked.commentary.lower(),
            ranked.original_position,
        )

    @staticmethod
    def _duplicate_key(
        commentary_key: str,
        comment: CommentaryComment,
    ) -> tuple[str, str, str, str, str]:
        """
        Construit une signature stable pour détecter les doublons.
        """

        return (
            commentary_key.strip().lower(),
            comment.ref.strip(),
            comment.he.strip(),
            comment.en.strip(),
            comment.fr.strip(),
        )

    @staticmethod
    def _apply_per_commentary_limit(
        ranked_comments: list[RankedComment],
        limit: int,
    ) -> list[RankedComment]:
        if limit < 1:
            return []

        selected: list[RankedComment] = []
        counts: dict[str, int] = {}

        for ranked in ranked_comments:
            current = counts.get(
                ranked.commentary_key,
                0,
            )

            if current >= limit:
                continue

            selected.append(ranked)
            counts[ranked.commentary_key] = (
                current + 1
            )

        return selected

    @staticmethod
    def _resolve_priority(
        loaded: LoadedDaf,
    ) -> int:
        """
        Utilise la priorité chargée, puis le registre en secours.
        """

        if loaded.priority:
            return loaded.priority

        try:
            return get_commentary(
                loaded.commentary_key
            ).priority
        except KeyError:
            return 0


def rank_commentaries(
    loaded_dapim: Iterable[LoadedDaf],
    *,
    limit: int | None = None,
    per_commentary_limit: int | None = None,
) -> CommentaryRankingResult:
    """
    Fonction utilitaire de classement.
    """

    ranker = CommentaryRanker()

    return ranker.rank_loaded_dapim(
        loaded_dapim,
        limit=limit,
        per_commentary_limit=per_commentary_limit,
    )


def select_commentaries_for_translation(
    loaded_dapim: Iterable[LoadedDaf],
    *,
    max_comments: int = 12,
    max_per_commentary: int = 4,
) -> CommentaryRankingResult:
    """
    Fonction utilitaire destinée au moteur de traduction.
    """

    ranker = CommentaryRanker()

    return ranker.select_for_translation(
        loaded_dapim,
        max_comments=max_comments,
        max_per_commentary=max_per_commentary,
    )
