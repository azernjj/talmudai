"""
Moteur de gestion des commentaires de TALMUD AI V7.2.
"""

from .index import (
    CommentaryFileIndex,
    CommentaryIndex,
    CommentaryIndexError,
    CommentaryIndexer,
    build_commentary_index,
    load_commentary_index,
)
from .loader import (
    CommentaryLoader,
    CommentarySearchResult,
    LoadedDaf,
)
from .models import (
    CommentaryComment,
    CommentaryDaf,
    CommentaryDocument,
)
from .ranking import (
    CommentaryRanker,
    CommentaryRankingResult,
    CommentaryRankingWeights,
    RankedComment,
    rank_commentaries,
    select_commentaries_for_translation,
)
from .registry import (
    COMMENTARY_REGISTRY,
    CommentaryDefinition,
    get_commentary,
    list_commentaries,
    normalize_commentary_key,
)
from .validator import (
    CommentaryValidator,
    ValidationIssue,
    ValidationReport,
    validate_commentary_file,
)
from .writer import (
    CommentaryWriteResult,
    CommentaryWriter,
    CommentaryWriterError,
    save_commentary_document,
    update_commentary_translation,
)

from .checkpoint import (
    CommentaryCheckpoint,
    CommentaryCheckpointError,
    CommentaryCheckpointItem,
    CommentaryCheckpointManager,
    CommentaryCheckpointSaveResult,
    load_commentary_checkpoint,
    save_commentary_checkpoint,
)
from .downloader import (
    BatchDownloadResult,
    CommentaryDownloadError,
    CommentaryDownloader,
    CommentaryHTTPError,
    CommentaryResponseError,
    DownloadedDaf,
    DownloadOptions,
    DownloadResult,
    SefariaHTTPClient,
    download_commentary_daf,
    download_commentary_masechet,
)
__all__ = [
    "CommentaryDefinition",
    "CommentaryComment",
    "CommentaryDaf",
    "CommentaryDocument",
    "CommentaryLoader",
    "CommentarySearchResult",
    "LoadedDaf",
    "CommentaryValidator",
    "ValidationIssue",
    "ValidationReport",
    "CommentaryFileIndex",
    "CommentaryIndex",
    "CommentaryIndexError",
    "CommentaryIndexer",
    "CommentaryRanker",
    "CommentaryRankingResult",
    "CommentaryRankingWeights",
    "RankedComment",
    "COMMENTARY_REGISTRY",
    "get_commentary",
    "list_commentaries",
    "normalize_commentary_key",
    "validate_commentary_file",
    "build_commentary_index",
    "load_commentary_index",
    "rank_commentaries",
    "select_commentaries_for_translation",
    "CommentaryWriteResult",
    "CommentaryWriter",
    "CommentaryWriterError",
    "save_commentary_document",
    "update_commentary_translation",
    "CommentaryCheckpoint",
    "CommentaryCheckpointError",
    "CommentaryCheckpointItem",
    "CommentaryCheckpointManager",
    "CommentaryCheckpointSaveResult",
    "load_commentary_checkpoint",
    "save_commentary_checkpoint",
    "BatchDownloadResult",
    "CommentaryDownloadError",
    "CommentaryDownloader",
    "CommentaryHTTPError",
    "CommentaryResponseError",
    "DownloadedDaf",
    "DownloadOptions",
    "DownloadResult",
    "SefariaHTTPClient",
    "download_commentary_daf",
    "download_commentary_masechet",
]


