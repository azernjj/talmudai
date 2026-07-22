from __future__ import annotations

import html
import json
import random
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .index import CommentaryIndexer
from .loader import CommentaryLoader
from .models import (
    CommentaryComment,
    CommentaryDaf,
    CommentaryDocument,
)
from .registry import (
    get_commentary,
    normalize_commentary_key,
)
from .validator import CommentaryValidator
from .writer import CommentaryWriter


SEFARIA_BASE_URL = "https://www.sefaria.org"

DEFAULT_SEFARIA_TITLES: dict[str, str] = {
    "rashi": "Rashi on {masechet}",
    "tosafot": "Tosafot on {masechet}",
    "ritva": "Ritva on {masechet}",
    "rosh": "Rosh on {masechet}",
    "rashba": "Rashba on {masechet}",
    "ran": "Ran on {masechet}",
    "maharsha": "Chidushei Halachot on {masechet}",
    "pnei-yehoshua": "Penei Yehoshua on {masechet}",
}


class CommentaryDownloadError(RuntimeError):
    """
    Erreur générale du téléchargeur de commentaires.
    """


class CommentaryHTTPError(CommentaryDownloadError):
    """
    Erreur HTTP ou réseau lors d’un appel à une source distante.

    Le code HTTP, l'URL et le corps de la réponse sont conservés
    afin de distinguer une véritable erreur d'un texte absent.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str = "",
        response_body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_body = response_body


class CommentaryResponseError(CommentaryDownloadError):
    """
    Réponse distante absente, invalide ou incohérente.
    """


@dataclass
class DownloadOptions:
    """
    Paramètres généraux de téléchargement.
    """

    timeout: float = 45.0
    retries: int = 5
    retry_delay: float = 2.0
    retry_backoff: float = 2.0
    request_delay: float = 0.35
    jitter: float = 0.15
    user_agent: str = (
        "TalmudAI-V7.2-CommentaryDownloader/1.0 "
        "(educational Torah text project)"
    )
    source_version: str = "source"
    include_translation: bool = True
    translation_version: str = "translation"
    fill_missing_segments: bool = True

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout doit être supérieur à zéro.")

        if self.retries < 0:
            raise ValueError("retries ne peut pas être négatif.")

        if self.retry_delay < 0:
            raise ValueError(
                "retry_delay ne peut pas être négatif."
            )

        if self.retry_backoff < 1:
            raise ValueError(
                "retry_backoff doit être supérieur ou égal à 1."
            )

        if self.request_delay < 0:
            raise ValueError(
                "request_delay ne peut pas être négatif."
            )

        if self.jitter < 0:
            raise ValueError("jitter ne peut pas être négatif.")


@dataclass
class DownloadedDaf:
    """
    Résultat du téléchargement d’un daf.
    """

    commentary_key: str
    commentary: str
    masechet: str
    daf: str
    sefaria_ref: str
    comments: list[CommentaryComment] = field(
        default_factory=list
    )
    source_version_title: str = ""
    translation_version_title: str = ""
    warnings: list[str] = field(default_factory=list)
    request_count: int = 0

    @property
    def comment_count(self) -> int:
        return len(self.comments)

    def to_commentary_daf(self) -> CommentaryDaf:
        return CommentaryDaf(
            daf=self.daf,
            comments=list(self.comments),
            metadata={
                "sefaria_ref": self.sefaria_ref,
                "source_version_title": (
                    self.source_version_title
                ),
                "translation_version_title": (
                    self.translation_version_title
                ),
                "warnings": list(self.warnings),
            },
        )


@dataclass
class DownloadResult:
    """
    Résultat du téléchargement d’un traité.
    """

    commentary_key: str
    commentary: str
    masechet: str
    destination: Path
    document: CommentaryDocument
    downloaded_dapim: list[str] = field(default_factory=list)
    skipped_dapim: list[str] = field(default_factory=list)
    empty_dapim: list[str] = field(default_factory=list)
    failed_dapim: dict[str, str] = field(default_factory=dict)
    request_count: int = 0
    elapsed_seconds: float = 0.0
    index_rebuilt: bool = False

    @property
    def success(self) -> bool:
        return not self.failed_dapim

    def statistics(self) -> dict[str, Any]:
        return {
            "commentary_key": self.commentary_key,
            "commentary": self.commentary,
            "masechet": self.masechet,
            "destination": str(self.destination),
            "downloaded_dapim": len(self.downloaded_dapim),
            "skipped_dapim": len(self.skipped_dapim),
            "empty_dapim": len(self.empty_dapim),
            "failed_dapim": len(self.failed_dapim),
            "requests": self.request_count,
            "dapim_in_document": self.document.daf_count(),
            "comments_in_document": self.document.comment_count(),
            "elapsed_seconds": round(
                self.elapsed_seconds,
                2,
            ),
            "index_rebuilt": self.index_rebuilt,
        }


@dataclass
class BatchDownloadResult:
    """
    Résultat d’un téléchargement de plusieurs traités.
    """

    results: list[DownloadResult] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return not self.failures and all(
            result.success for result in self.results
        )

    def statistics(self) -> dict[str, Any]:
        return {
            "treatises": len(self.results),
            "batch_failures": len(self.failures),
            "downloaded_dapim": sum(
                len(result.downloaded_dapim)
                for result in self.results
            ),
            "failed_dapim": sum(
                len(result.failed_dapim)
                for result in self.results
            ),
            "comments": sum(
                result.document.comment_count()
                for result in self.results
            ),
            "requests": sum(
                result.request_count
                for result in self.results
            ),
        }


class SefariaHTTPClient:
    """
    Client HTTP léger destiné à l’API Sefaria.

    Il utilise uniquement la bibliothèque standard Python :
    aucune dépendance externe n’est nécessaire.
    """

    RETRYABLE_STATUS_CODES = {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }

    def __init__(
        self,
        *,
        base_url: str = SEFARIA_BASE_URL,
        options: DownloadOptions | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.options = options or DownloadOptions()
        self.request_count = 0
        self._last_request_at = 0.0

    def get_json(
        self,
        path: str,
        *,
        params: (
            dict[str, Any]
            | Sequence[tuple[str, Any]]
            | None
        ) = None,
    ) -> Any:
        url = self.build_url(
            path,
            params=params,
        )

        last_error: Exception | None = None

        for attempt in range(
            self.options.retries + 1
        ):
            self._wait_before_request()

            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.options.user_agent,
                },
                method="GET",
            )

            try:
                self.request_count += 1

                with urllib.request.urlopen(
                    request,
                    timeout=self.options.timeout,
                ) as response:
                    raw_data = response.read()

                try:
                    decoded = raw_data.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CommentaryResponseError(
                        f"Réponse non UTF-8 reçue depuis {url}."
                    ) from exc

                try:
                    payload = json.loads(decoded)
                except json.JSONDecodeError as exc:
                    preview = decoded[:300].replace(
                        "\n",
                        " ",
                    )

                    raise CommentaryResponseError(
                        "Réponse JSON invalide reçue depuis "
                        f"{url}. Aperçu : {preview}"
                    ) from exc

                if isinstance(payload, dict):
                    self._raise_api_error(
                        payload,
                        url=url,
                    )

                return payload

            except urllib.error.HTTPError as exc:
                last_error = exc

                if (
                    exc.code
                    not in self.RETRYABLE_STATUS_CODES
                ):
                    body = self._read_http_error_body(exc)

                    raise CommentaryHTTPError(
                        (
                            f"Erreur HTTP {exc.code} pour "
                            f"{url}: {body}"
                        ),
                        status_code=exc.code,
                        url=url,
                        response_body=body,
                    ) from exc

                retry_after = self._retry_after_seconds(exc)

                if attempt >= self.options.retries:
                    break

                self._sleep_before_retry(
                    attempt,
                    minimum_delay=retry_after,
                )

            except (
                urllib.error.URLError,
                TimeoutError,
                socket.timeout,
                ConnectionError,
                CommentaryResponseError,
            ) as exc:
                last_error = exc

                if attempt >= self.options.retries:
                    break

                self._sleep_before_retry(attempt)

        raise CommentaryHTTPError(
            f"Échec après {self.options.retries + 1} "
            f"tentative(s) pour {url}: {last_error}"
        ) from last_error

    def build_url(
        self,
        path: str,
        *,
        params: (
            dict[str, Any]
            | Sequence[tuple[str, Any]]
            | None
        ) = None,
    ) -> str:
        if path.startswith(("http://", "https://")):
            base = path
        else:
            base = f"{self.base_url}/{path.lstrip('/')}"

        if not params:
            return base

        query = urllib.parse.urlencode(
            params,
            doseq=True,
        )

        separator = "&" if "?" in base else "?"

        return f"{base}{separator}{query}"

    def _wait_before_request(self) -> None:
        delay = self.options.request_delay

        if self.options.jitter:
            delay += random.uniform(
                0,
                self.options.jitter,
            )

        if delay <= 0:
            return

        elapsed = time.monotonic() - self._last_request_at
        remaining = delay - elapsed

        if remaining > 0:
            time.sleep(remaining)

        self._last_request_at = time.monotonic()

    def _sleep_before_retry(
        self,
        attempt: int,
        *,
        minimum_delay: float = 0.0,
    ) -> None:
        delay = (
            self.options.retry_delay
            * (
                self.options.retry_backoff
                ** attempt
            )
        )

        delay = max(delay, minimum_delay)

        if self.options.jitter:
            delay += random.uniform(
                0,
                self.options.jitter,
            )

        time.sleep(delay)

    @staticmethod
    def _retry_after_seconds(
        exc: urllib.error.HTTPError,
    ) -> float:
        raw_value = exc.headers.get("Retry-After")

        if not raw_value:
            return 0.0

        try:
            return max(0.0, float(raw_value))
        except ValueError:
            return 0.0

    @staticmethod
    def _read_http_error_body(
        exc: urllib.error.HTTPError,
    ) -> str:
        try:
            raw_body = exc.read()
            return raw_body.decode(
                "utf-8",
                errors="replace",
            )[:500]
        except Exception:
            return str(exc.reason)

    @staticmethod
    def _raise_api_error(
        payload: dict[str, Any],
        *,
        url: str,
    ) -> None:
        error = (
            payload.get("error")
            or payload.get("detail")
        )

        if error:
            raise CommentaryResponseError(
                f"Erreur API pour {url}: {error}"
            )


class CommentaryDownloader:
    """
    Télécharge, normalise et sauvegarde les commentaires.

    Les téléchargements sont enregistrés après chaque daf afin qu’une
    interruption ne fasse pas perdre le travail déjà accompli.
    """

    def __init__(
        self,
        *,
        data_root: str | Path = (
            "public/data/commentaries"
        ),
        base_url: str = SEFARIA_BASE_URL,
        options: DownloadOptions | None = None,
        writer: CommentaryWriter | None = None,
        loader: CommentaryLoader | None = None,
        validator: CommentaryValidator | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.options = options or DownloadOptions()

        self.client = SefariaHTTPClient(
            base_url=base_url,
            options=self.options,
        )

        self.writer = writer or CommentaryWriter(
            create_backups=True
        )

        self.loader = loader or CommentaryLoader(
            root=self.data_root
        )

        self.validator = (
            validator or CommentaryValidator()
        )

    def download_daf(
        self,
        *,
        commentary: str,
        masechet: str,
        daf: str,
        sefaria_title: str | None = None,
    ) -> DownloadedDaf:
        """
        Télécharge un seul daf depuis Sefaria Texts v3.
        """

        definition = get_commentary(commentary)
        commentary_key = definition.key

        resolved_title = self.resolve_sefaria_title(
            commentary_key,
            masechet,
            override=sefaria_title,
        )

        normalized_daf = self.normalize_daf(daf)
        sefaria_ref = (
            f"{resolved_title} {normalized_daf}"
        )

        parameters: list[tuple[str, Any]] = [
            ("version", self.options.source_version),
        ]

        if self.options.include_translation:
            parameters.append(
                (
                    "version",
                    self.options.translation_version,
                )
            )

        if self.options.fill_missing_segments:
            parameters.append(
                ("fill_in_missing_segments", "1")
            )

        encoded_ref = urllib.parse.quote(
            sefaria_ref,
            safe="",
        )

        requests_before = self.client.request_count

        payload = self.client.get_json(
            f"/api/v3/texts/{encoded_ref}",
            params=parameters,
        )

        comments, source_title, translation_title = (
            self._parse_v3_text_response(
                payload,
                sefaria_ref=sefaria_ref,
            )
        )

        warnings = self._extract_warnings(payload)

        if comments:
            warnings.extend(
                self._attach_base_refs(
                    comments,
                    commentary_daf_ref=sefaria_ref,
                    masechet=masechet,
                    daf=normalized_daf,
                )
            )

        return DownloadedDaf(
            commentary_key=commentary_key,
            commentary=definition.display_name,
            masechet=masechet,
            daf=normalized_daf,
            sefaria_ref=sefaria_ref,
            comments=comments,
            source_version_title=source_title,
            translation_version_title=(
                translation_title
            ),
            warnings=warnings,
            request_count=(
                self.client.request_count
                - requests_before
            ),
        )

    def download_masechet(
        self,
        *,
        commentary: str,
        masechet: str,
        dapim: Iterable[str] | None = None,
        start_daf: str | None = None,
        end_daf: str | None = None,
        sefaria_title: str | None = None,
        destination: str | Path | None = None,
        force: bool = False,
        keep_empty_dapim: bool = False,
        stop_on_error: bool = False,
        backup: bool = True,
        rebuild_index: bool = False,
    ) -> DownloadResult:
        """
        Télécharge un traité complet ou une sélection de dapim.

        La méthode sauvegarde le document après chaque daf réussi.
        """

        started_at = time.monotonic()
        requests_before = self.client.request_count

        definition = get_commentary(commentary)
        commentary_key = definition.key

        target_path = (
            Path(destination)
            if destination is not None
            else self.destination_path(
                commentary_key,
                masechet,
            )
        )

        document = self._load_or_create_document(
            commentary_key=commentary_key,
            commentary_name=definition.display_name,
            masechet=masechet,
            destination=target_path,
        )

        requested_dapim = self.resolve_dapim(
            dapim=dapim,
            start_daf=start_daf,
            end_daf=end_daf,
        )

        result = DownloadResult(
            commentary_key=commentary_key,
            commentary=definition.display_name,
            masechet=masechet,
            destination=target_path,
            document=document,
        )

        for daf in requested_dapim:
            normalized_daf = self.normalize_daf(daf)

            if (
                not force
                and document.has_daf(normalized_daf)
            ):
                result.skipped_dapim.append(
                    normalized_daf
                )
                continue

            try:
                downloaded = self.download_daf(
                    commentary=commentary_key,
                    masechet=masechet,
                    daf=normalized_daf,
                    sefaria_title=sefaria_title,
                )

                if (
                    not downloaded.comments
                    and not keep_empty_dapim
                ):
                    result.empty_dapim.append(
                        normalized_daf
                    )
                    continue

                document.add_or_replace_daf(
                    downloaded.to_commentary_daf()
                )

                document.metadata.update(
                    {
                        "download_source": "sefaria",
                        "sefaria_title": (
                            self.resolve_sefaria_title(
                                commentary_key,
                                masechet,
                                override=sefaria_title,
                            )
                        ),
                        "download_api": "texts-v3",
                    }
                )

                self.writer.save_document(
                    document,
                    target_path,
                    backup=backup,
                )

                result.downloaded_dapim.append(
                    normalized_daf
                )

            except CommentaryHTTPError as exc:
                body = exc.response_body.lower()

                is_missing_text = (
                    exc.status_code == 404
                    and (
                        "we have no text for" in body
                        or "no text for" in body
                    )
                )

                if is_missing_text:
                    result.empty_dapim.append(
                        normalized_daf
                    )

                    if keep_empty_dapim:
                        document.add_or_replace_daf(
                            CommentaryDaf(
                                daf=normalized_daf,
                                comments=[],
                                metadata={
                                    "empty": True,
                                    "reason": (
                                        "sefaria_no_text"
                                    ),
                                },
                            )
                        )

                        self.writer.save_document(
                            document,
                            target_path,
                            backup=backup,
                        )

                    continue

                result.failed_dapim[
                    normalized_daf
                ] = str(exc)

                if stop_on_error:
                    break

            except Exception as exc:
                result.failed_dapim[
                    normalized_daf
                ] = str(exc)

                if stop_on_error:
                    break

        result.request_count = (
            self.client.request_count
            - requests_before
        )

        result.elapsed_seconds = (
            time.monotonic() - started_at
        )

        if rebuild_index:
            self.rebuild_index()
            result.index_rebuilt = True

        return result

    def download_batch(
        self,
        *,
        commentary: str,
        masechtot: Iterable[str],
        dapim_by_masechet: (
            dict[str, Iterable[str]] | None
        ) = None,
        force: bool = False,
        stop_on_error: bool = False,
        rebuild_index: bool = True,
    ) -> BatchDownloadResult:
        """
        Télécharge plusieurs traités du même commentaire.
        """

        batch = BatchDownloadResult()

        for masechet in masechtot:
            masechet_name = str(masechet).strip()

            if not masechet_name:
                continue

            try:
                result = self.download_masechet(
                    commentary=commentary,
                    masechet=masechet_name,
                    dapim=(
                        dapim_by_masechet.get(
                            masechet_name
                        )
                        if dapim_by_masechet
                        else None
                    ),
                    force=force,
                    stop_on_error=stop_on_error,
                    rebuild_index=False,
                )

                batch.results.append(result)

                if stop_on_error and not result.success:
                    break

            except Exception as exc:
                batch.failures[
                    masechet_name
                ] = str(exc)

                if stop_on_error:
                    break

        if rebuild_index:
            self.rebuild_index()

        return batch

    def import_local_file(
        self,
        source: str | Path,
        *,
        destination: str | Path | None = None,
        backup: bool = True,
        rebuild_index: bool = False,
    ) -> CommentaryDocument:
        """
        Importe et normalise un fichier JSON local.
        """

        source_path = Path(source)

        document = self.loader.load_file(
            source_path
        )

        report = self.validator.validate_document(
            document,
            source_path=source_path,
        )

        if not report.is_valid:
            error_messages = [
                issue.message
                for issue in report.errors
            ]

            raise CommentaryDownloadError(
                "Le fichier local est invalide : "
                + " | ".join(error_messages)
            )

        target_path = (
            Path(destination)
            if destination is not None
            else self.destination_path(
                document.commentary_key,
                document.masechet,
            )
        )

        self.writer.save_document(
            document,
            target_path,
            backup=backup,
        )

        if rebuild_index:
            self.rebuild_index()

        return document

    def import_local_directory(
        self,
        source_directory: str | Path,
        *,
        pattern: str = "*.json",
        rebuild_index: bool = True,
    ) -> list[CommentaryDocument]:
        """
        Importe récursivement les fichiers JSON d’un dossier.
        """

        source_root = Path(source_directory)

        if not source_root.exists():
            raise CommentaryDownloadError(
                f"Dossier introuvable : {source_root}"
            )

        documents: list[CommentaryDocument] = []

        for source_path in sorted(
            source_root.rglob(pattern)
        ):
            if source_path.name == "index.json":
                continue

            documents.append(
                self.import_local_file(
                    source_path,
                    rebuild_index=False,
                )
            )

        if rebuild_index:
            self.rebuild_index()

        return documents

    def rebuild_index(self) -> Path:
        """
        Reconstruit l’index global des commentaires.
        """

        indexer = CommentaryIndexer(
            root_directory=self.data_root
        )

        index = indexer.build()

        return indexer.save(index)

    def destination_path(
        self,
        commentary: str,
        masechet: str,
    ) -> Path:
        commentary_key = normalize_commentary_key(
            commentary
        )

        filename = (
            self.slugify_filename(masechet)
            + ".json"
        )

        return (
            self.data_root
            / commentary_key
            / filename
        )

    def resolve_sefaria_title(
        self,
        commentary: str,
        masechet: str,
        *,
        override: str | None = None,
    ) -> str:
        """
        Résout le titre du texte tel qu’il est connu par Sefaria.

        Ordre de priorité :
        1. titre fourni explicitement avec `override` ;
        2. titre déclaré dans le registre des commentaires ;
        3. dictionnaire historique `DEFAULT_SEFARIA_TITLES` ;
        4. titre construit depuis le nom d’affichage.
        """

        if override and override.strip():
            return override.strip()

        commentary_key = normalize_commentary_key(
            commentary
        )

        definition = get_commentary(
            commentary_key
        )

        template = getattr(
            definition,
            "sefaria_title",
            None,
        )

        if not template:
            template = DEFAULT_SEFARIA_TITLES.get(
                commentary_key
            )

        if not template:
            template = (
                f"{definition.display_name} "
                "on {masechet}"
            )

        template = str(template).strip()

        if "{masechet}" in template:
            return template.format(
                masechet=masechet
            )

        if template.endswith(" on"):
            return f"{template} {masechet}"

        return template

    def resolve_dapim(
        self,
        *,
        dapim: Iterable[str] | None,
        start_daf: str | None,
        end_daf: str | None,
    ) -> list[str]:
        """
        Résout la liste exacte des dapim à télécharger.

        Pour un traité complet, il faut fournir au moins `end_daf`.
        Cela empêche le téléchargeur de deviner une fin de traité
        incorrecte.
        """

        if dapim is not None:
            resolved: list[str] = []

            for daf in dapim:
                normalized = self.normalize_daf(daf)

                if normalized not in resolved:
                    resolved.append(normalized)

            if not resolved:
                raise CommentaryDownloadError(
                    "La liste des dapim est vide."
                )

            return resolved

        resolved_start = self.normalize_daf(
            start_daf or "2a"
        )

        if not end_daf:
            raise CommentaryDownloadError(
                "Indique `end_daf` pour télécharger un traité "
                "ou fournis explicitement `dapim`."
            )

        resolved_end = self.normalize_daf(
            end_daf
        )

        return self.generate_daf_range(
            resolved_start,
            resolved_end,
        )

    def _load_or_create_document(
        self,
        *,
        commentary_key: str,
        commentary_name: str,
        masechet: str,
        destination: Path,
    ) -> CommentaryDocument:
        if destination.exists():
            document = self.loader.load_file(
                destination
            )

            if (
                normalize_commentary_key(
                    document.commentary_key
                )
                != commentary_key
            ):
                raise CommentaryDownloadError(
                    "Le commentaire du fichier existant ne "
                    "correspond pas au téléchargement demandé."
                )

            if (
                document.masechet.strip().lower()
                != masechet.strip().lower()
            ):
                raise CommentaryDownloadError(
                    "Le traité du fichier existant ne "
                    "correspond pas au téléchargement demandé."
                )

            return document

        return CommentaryDocument(
            masechet=masechet,
            file=destination.name,
            commentary=commentary_name,
            commentary_key=commentary_key,
            source="sefaria",
            dapim=[],
            version="1.0",
            metadata={
                "download_source": "sefaria",
                "download_api": "texts-v3",
            },
        )

    def _parse_v3_text_response(
        self,
        payload: dict[str, Any],
        *,
        sefaria_ref: str,
    ) -> tuple[
        list[CommentaryComment],
        str,
        str,
    ]:
        """
        Analyse une réponse Sefaria Texts v3 sans perdre les
        coordonnées canoniques des commentaires.

        Exemple pour Tosafot :

            text[0][0]
                -> Tosafot ... 2a:1:1

            text[6][0]
                -> Tosafot ... 2a:7:1

            text[9][1]
                -> Tosafot ... 2a:10:2

        L'ancienne version aplatissait ces listes et produisait
        artificiellement :1, :2, :3, etc.
        """

        versions = payload.get("versions", [])

        if not isinstance(versions, list):
            raise CommentaryResponseError(
                "Le champ `versions` de la réponse Sefaria "
                "n’est pas une liste."
            )

        def collect_segments(
            value: Any,
            path: tuple[int, ...] = (),
        ) -> dict[tuple[int, ...], str]:
            """
            Transforme une structure imbriquée Sefaria en dictionnaire :

                (segment, sous-segment) -> texte

            Les indices sont conservés en base 1.
            """

            collected: dict[
                tuple[int, ...],
                str,
            ] = {}

            if isinstance(value, list):
                for index, child in enumerate(
                    value,
                    start=1,
                ):
                    collected.update(
                        collect_segments(
                            child,
                            path + (index,),
                        )
                    )

                return collected

            if value is None:
                return collected

            if not isinstance(value, str):
                value = str(value)

            text = value.strip()

            if not text:
                return collected

            coordinates = path

            # Les commentaires dépendants de Sefaria possèdent
            # normalement deux niveaux sous le daf :
            # segment talmudique + commentaire dans ce segment.
            #
            # Si une version renvoie exceptionnellement une liste
            # simple, on lui ajoute le sous-segment 1.
            if len(coordinates) == 1:
                coordinates = (
                    coordinates[0],
                    1,
                )

            if not coordinates:
                coordinates = (1, 1)

            collected[coordinates] = text

            return collected

        source_texts: dict[
            tuple[int, ...],
            str,
        ] = {}

        translation_texts: dict[
            tuple[int, ...],
            str,
        ] = {}

        source_title = ""
        translation_title = ""

        for version in versions:
            if not isinstance(version, dict):
                continue

            texts = collect_segments(
                version.get("text")
            )

            if not texts:
                continue

            language = self._version_language(
                version
            )

            version_title = str(
                version.get("versionTitle", "")
            ).strip()

            if self._is_source_language(
                version,
                language,
            ):
                if not source_texts:
                    source_texts = texts
                    source_title = version_title

            elif self._is_translation_language(
                version,
                language,
            ):
                if not translation_texts:
                    translation_texts = texts
                    translation_title = version_title

        if not source_texts:
            fallback_text = payload.get("text")

            if fallback_text is not None:
                source_texts = collect_segments(
                    fallback_text
                )

        if not source_texts and not translation_texts:
            return (
                [],
                source_title,
                translation_title,
            )

        all_coordinates = sorted(
            set(source_texts)
            | set(translation_texts)
        )

        comments: list[CommentaryComment] = []

        for coordinates in all_coordinates:
            hebrew = source_texts.get(
                coordinates,
                "",
            )

            english = translation_texts.get(
                coordinates,
                "",
            )

            if not hebrew and not english:
                continue

            segment_number = coordinates[0]

            subsegment_number = (
                coordinates[1]
                if len(coordinates) > 1
                else 1
            )

            reference_suffix = ":".join(
                str(number)
                for number in coordinates
            )

            metadata: dict[str, Any] = {
                "sefaria_segment": (
                    segment_number
                ),
                "sefaria_subsegment": (
                    subsegment_number
                ),
                "sefaria_coordinates": list(
                    coordinates
                ),
            }

            comments.append(
                CommentaryComment(
                    ref=(
                        f"{sefaria_ref}:"
                        f"{reference_suffix}"
                    ),
                    he=hebrew,
                    en=english,
                    fr="",
                    segment=segment_number,
                    base_ref="",
                    dibur_hamatchil=(
                        self.extract_dibur_hamatchil(
                            hebrew
                        )
                    ),
                    metadata=metadata,
                )
            )

        return (
            comments,
            source_title,
            translation_title,
        )

    def _attach_base_refs(
        self,
        comments: list[CommentaryComment],
        *,
        commentary_daf_ref: str,
        masechet: str,
        daf: str,
    ) -> list[str]:
        """
        Relie chaque commentaire au segment talmudique correspondant.

        Un seul appel à l'API Links est effectué pour tout le daf.
        Les renvois secondaires vers d'autres dapim ne sont pas choisis
        comme rattachement principal.
        """

        warnings: list[str] = []

        encoded_ref = urllib.parse.quote(
            commentary_daf_ref,
            safe="",
        )

        try:
            payload = self.client.get_json(
                f"/api/links/{encoded_ref}"
            )
        except CommentaryDownloadError as exc:
            return [
                "Impossible de récupérer les liens Sefaria pour "
                f"{commentary_daf_ref}: {exc}"
            ]

        if not isinstance(payload, list):
            return [
                "La réponse Links de Sefaria n'est pas une liste "
                f"pour {commentary_daf_ref}."
            ]

        links = [
            item
            for item in payload
            if isinstance(item, dict)
        ]

        for comment in comments:
            selected = self._select_primary_base_link(
                links,
                commentary_ref=comment.ref,
                masechet=masechet,
                daf=daf,
            )

            if selected is None:
                warnings.append(
                    "Aucun rattachement talmudique principal trouvé "
                    f"pour {comment.ref}."
                )
                continue

            base_ref, anchor_ref, link = selected

            comment.base_ref = base_ref

            comment.metadata[
                "sefaria_anchor_ref"
            ] = anchor_ref

            comment.metadata[
                "sefaria_base_ref"
            ] = base_ref

            link_type = str(
                link.get("type", "")
            ).strip()

            category = str(
                link.get("category", "")
            ).strip()

            if link_type:
                comment.metadata[
                    "sefaria_link_type"
                ] = link_type

            if category:
                comment.metadata[
                    "sefaria_link_category"
                ] = category

        return warnings

    @classmethod
    def _select_primary_base_link(
        cls,
        links: list[dict[str, Any]],
        *,
        commentary_ref: str,
        masechet: str,
        daf: str,
    ) -> tuple[
        str,
        str,
        dict[str, Any],
    ] | None:
        """
        Sélectionne le lien principal commentaire -> Talmud.

        Priorités :
        1. l'ancre correspond exactement au commentaire ;
        2. la cible appartient au même daf ;
        3. le lien est de type commentary ;
        4. la catégorie de la cible est Talmud.
        """

        commentary_ref = str(
            commentary_ref
        ).strip()

        expected_base_prefix = (
            f"{masechet.strip()} {daf.strip()}"
        ).lower()

        candidates: list[
            tuple[
                int,
                str,
                str,
                dict[str, Any],
            ]
        ] = []

        for link in links:
            ref = str(
                link.get("ref", "")
            ).strip()

            anchor_ref = str(
                link.get("anchorRef", "")
            ).strip()

            source_ref = str(
                link.get("sourceRef", "")
            ).strip()

            category = str(
                link.get("category", "")
            ).strip().lower()

            link_type = str(
                link.get("type", "")
            ).strip().lower()

            base_ref = ""
            commentary_anchor = ""

            anchor_matches = (
                anchor_ref == commentary_ref
                or anchor_ref.startswith(
                    commentary_ref + ":"
                )
            )

            ref_matches = (
                ref == commentary_ref
                or ref.startswith(
                    commentary_ref + ":"
                )
            )

            source_matches = (
                source_ref == commentary_ref
                or source_ref.startswith(
                    commentary_ref + ":"
                )
            )

            if anchor_matches:
                base_ref = ref or source_ref
                commentary_anchor = anchor_ref

            elif ref_matches:
                base_ref = anchor_ref or source_ref
                commentary_anchor = ref

            elif source_matches:
                base_ref = anchor_ref or ref
                commentary_anchor = source_ref

            else:
                continue

            if not base_ref:
                continue

            # Le rattachement principal doit être un passage du Talmud.
            is_talmud = (
                category == "talmud"
                or base_ref.lower().startswith(
                    expected_base_prefix
                )
            )

            if not is_talmud:
                continue

            score = 0

            if category == "talmud":
                score += 100

            if (
                base_ref.lower()
                .startswith(expected_base_prefix)
            ):
                score += 80

            if link_type == "commentary":
                score += 40

            if anchor_ref == commentary_ref:
                score += 20

            if anchor_ref.startswith(
                commentary_ref + ":"
            ):
                score += 15

            # Une référence précise est préférable à un daf entier.
            if re.search(
                r"\d+[ab]:\d+(?:-\d+)?$",
                base_ref,
                flags=re.IGNORECASE,
            ):
                score += 10

            candidates.append(
                (
                    score,
                    base_ref,
                    commentary_anchor,
                    link,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        _, base_ref, anchor_ref, link = (
            candidates[0]
        )

        return base_ref, anchor_ref, link

    def _extract_version_segments(
        self,
        version: dict[str, Any],
    ) -> list[str]:
        for field_name in (
            "text",
            "chapter",
            "contents",
        ):
            if field_name in version:
                return self.flatten_segments(
                    version[field_name]
                )

        return []

    @staticmethod
    def _version_language(
        version: dict[str, Any],
    ) -> str:
        for field_name in (
            "languageFamilyName",
            "language",
            "actualLanguage",
        ):
            value = str(
                version.get(field_name, "")
            ).strip().lower()

            if value:
                return value

        return ""

    @staticmethod
    def _is_source_language(
        version: dict[str, Any],
        language: str,
    ) -> bool:
        if version.get("isSource") is True:
            return True

        if version.get("isPrimary") is True:
            if language in {
                "hebrew",
                "aramaic",
                "he",
            }:
                return True

        return language in {
            "hebrew",
            "aramaic",
            "he",
        }

    @staticmethod
    def _is_translation_language(
        version: dict[str, Any],
        language: str,
    ) -> bool:
        return language in {
            "english",
            "en",
        }

    @classmethod
    def flatten_segments(
        cls,
        value: Any,
    ) -> list[str]:
        """
        Aplatit les structures de texte renvoyées par Sefaria.
        """

        if value is None:
            return []

        if isinstance(value, str):
            cleaned = cls.clean_text(value)
            return [cleaned] if cleaned else []

        if isinstance(value, list):
            output: list[str] = []

            for item in value:
                output.extend(
                    cls.flatten_segments(item)
                )

            return output

        if isinstance(value, dict):
            for field_name in (
                "text",
                "he",
                "en",
                "contents",
            ):
                if field_name in value:
                    return cls.flatten_segments(
                        value[field_name]
                    )

        return []

    @staticmethod
    def clean_text(value: str) -> str:
        """
        Nettoie le HTML sans supprimer le texte hébreu.
        """

        text = str(value)

        text = re.sub(
            r"<br\s*/?>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"</p\s*>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"<[^>]+>",
            "",
            text,
        )

        text = html.unescape(text)

        text = text.replace(
            "\u00a0",
            " ",
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n[ \t]+",
            "\n",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    @staticmethod
    def extract_dibur_hamatchil(
        hebrew_text: str,
    ) -> str:
        """
        Extrait prudemment un éventuel dibour hamathil.

        On ne force aucune extraction lorsque le format est ambigu.
        """

        text = str(hebrew_text).strip()

        if not text:
            return ""

        bold_match = re.match(
            r"^\s*(.{1,180}?)\s*[-–—]\s+",
            text,
        )

        if bold_match:
            candidate = bold_match.group(1).strip()

            if len(candidate.split()) <= 18:
                return candidate

        return ""

    @staticmethod
    def _extract_warnings(
        payload: dict[str, Any],
    ) -> list[str]:
        raw_warnings = payload.get("warnings", [])

        if isinstance(raw_warnings, str):
            return [raw_warnings.strip()]

        if isinstance(raw_warnings, list):
            return [
                str(warning).strip()
                for warning in raw_warnings
                if str(warning).strip()
            ]

        if isinstance(raw_warnings, dict):
            return [
                f"{key}: {value}"
                for key, value in raw_warnings.items()
            ]

        return []

    @staticmethod
    def normalize_daf(daf: str) -> str:
        value = (
            str(daf)
            .strip()
            .lower()
            .replace(" ", "")
        )

        match = re.fullmatch(
            r"(\d+)([ab])",
            value,
        )

        if not match:
            raise CommentaryDownloadError(
                f"Daf invalide : {daf}. "
                "Format attendu, par exemple : 2a ou 17b."
            )

        number = int(match.group(1))
        side = match.group(2)

        if number < 1:
            raise CommentaryDownloadError(
                f"Numéro de daf invalide : {daf}"
            )

        return f"{number}{side}"

    @classmethod
    def generate_daf_range(
        cls,
        start_daf: str,
        end_daf: str,
    ) -> list[str]:
        start = cls.daf_to_position(start_daf)
        end = cls.daf_to_position(end_daf)

        if end < start:
            raise CommentaryDownloadError(
                "Le daf de fin précède le daf de départ."
            )

        return [
            cls.position_to_daf(position)
            for position in range(
                start,
                end + 1,
            )
        ]

    @classmethod
    def daf_to_position(
        cls,
        daf: str,
    ) -> int:
        normalized = cls.normalize_daf(daf)

        number = int(normalized[:-1])
        side = normalized[-1]

        return number * 2 + (
            0 if side == "a" else 1
        )

    @staticmethod
    def position_to_daf(
        position: int,
    ) -> str:
        number, side_index = divmod(
            int(position),
            2,
        )

        side = "a" if side_index == 0 else "b"

        return f"{number}{side}"

    @staticmethod
    def slugify_filename(value: str) -> str:
        cleaned = str(value).strip().lower()

        transliterations = {
            "’": "",
            "'": "",
            " ": "-",
            "_": "-",
            "/": "-",
            "\\": "-",
        }

        for source, target in (
            transliterations.items()
        ):
            cleaned = cleaned.replace(
                source,
                target,
            )

        cleaned = re.sub(
            r"[^a-z0-9\-]+",
            "",
            cleaned,
        )

        cleaned = re.sub(
            r"-{2,}",
            "-",
            cleaned,
        )

        return cleaned.strip("-") or "unknown"


def download_commentary_daf(
    *,
    commentary: str,
    masechet: str,
    daf: str,
    data_root: str | Path = (
        "public/data/commentaries"
    ),
) -> DownloadedDaf:
    """
    Fonction utilitaire pour télécharger un daf.
    """

    downloader = CommentaryDownloader(
        data_root=data_root
    )

    return downloader.download_daf(
        commentary=commentary,
        masechet=masechet,
        daf=daf,
    )


def download_commentary_masechet(
    *,
    commentary: str,
    masechet: str,
    end_daf: str,
    start_daf: str = "2a",
    data_root: str | Path = (
        "public/data/commentaries"
    ),
    force: bool = False,
    rebuild_index: bool = True,
) -> DownloadResult:
    """
    Fonction utilitaire pour télécharger un traité.
    """

    downloader = CommentaryDownloader(
        data_root=data_root
    )

    return downloader.download_masechet(
        commentary=commentary,
        masechet=masechet,
        start_daf=start_daf,
        end_daf=end_daf,
        force=force,
        rebuild_index=rebuild_index,
    )
