from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


LIGHT_BUDGET_EUR = 45.0
RESERVE_PER_CALL_EUR = 0.02

MODEL_PRICES_EUR_PER_MILLION = {
    "gpt-5-nano": {
        "input": 0.05,
        "output": 0.40,
    },
    "gpt-5-mini": {
        "input": 0.25,
        "output": 2.00,
    },
}


class BudgetError(RuntimeError):
    pass


def _pricing(model: str) -> dict[str, float]:
    name = str(model or "").strip().lower()

    for prefix, prices in MODEL_PRICES_EUR_PER_MILLION.items():
        if name == prefix or name.startswith(prefix + "-"):
            return prices

    raise BudgetError(
        f"Tarif inconnu pour le modèle {model!r}. "
        "Appel refusé pour protéger le budget."
    )


def _call_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    prices = _pricing(model)

    return (
        int(input_tokens) * prices["input"]
        + int(output_tokens) * prices["output"]
    ) / 1_000_000


class BudgetGuard:
    def __init__(
        self,
        project_root: str | Path,
        limit_eur: float = LIGHT_BUDGET_EUR,
    ) -> None:
        self.path = (
            Path(project_root).resolve()
            / ".talmud_ai_v7_2"
            / "budget.json"
        )
        self.limit_eur = min(
            float(limit_eur),
            LIGHT_BUDGET_EUR,
        )
        self.state = self._load()

    def _empty_state(self) -> dict[str, Any]:
        return {
            "version": 1,
            "limit_eur": self.limit_eur,
            "spent_eur": 0.0,
            "segments_billed": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_state()

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise BudgetError(
                f"Budget illisible : {self.path} — {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise BudgetError(
                "Le fichier budget.json doit contenir un objet."
            )

        state = self._empty_state()
        state["limit_eur"] = min(
            float(payload.get("limit_eur", self.limit_eur)),
            self.limit_eur,
        )
        state["spent_eur"] = float(
            payload.get("spent_eur", 0.0)
        )
        state["segments_billed"] = int(
            payload.get("segments_billed", 0)
        )
        state["input_tokens"] = int(
            payload.get("input_tokens", 0)
        )
        state["output_tokens"] = int(
            payload.get("output_tokens", 0)
        )
        state["total_tokens"] = int(
            payload.get("total_tokens", 0)
        )
        return state

    @property
    def spent_eur(self) -> float:
        return float(self.state["spent_eur"])

    @property
    def remaining_eur(self) -> float:
        return max(
            0.0,
            float(self.state["limit_eur"])
            - self.spent_eur,
        )

    def ensure_call_allowed(self) -> None:
        if self.remaining_eur < RESERVE_PER_CALL_EUR:
            raise BudgetError(
                "Budget insuffisant avant appel API : "
                f"{self.remaining_eur:.6f} € restant(s), "
                f"{RESERVE_PER_CALL_EUR:.6f} € requis."
            )

    def _save(self) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary = self.path.with_name(
            self.path.name + ".writing"
        )

        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                self.state,
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, self.path)

    def _record(
        self,
        *,
        cost_eur: float,
        input_tokens: int,
        output_tokens: int,
        segment_billed: bool,
    ) -> float:
        self.state["spent_eur"] = (
            self.spent_eur + float(cost_eur)
        )
        self.state["input_tokens"] += int(input_tokens)
        self.state["output_tokens"] += int(output_tokens)
        self.state["total_tokens"] += (
            int(input_tokens) + int(output_tokens)
        )

        if segment_billed:
            self.state["segments_billed"] += 1

        self._save()
        return float(cost_eur)

    def record_result(
        self,
        metadata: dict[str, Any],
    ) -> float:
        tokens = metadata.get("tokens", {})
        total_cost = 0.0
        total_input = 0
        total_output = 0

        for role in ("translator", "reviewer"):
            usage = tokens.get(role, {})
            input_tokens = int(
                usage.get("input", 0) or 0
            )
            output_tokens = int(
                usage.get("output", 0) or 0
            )

            if not input_tokens and not output_tokens:
                continue

            model = metadata.get(f"{role}_model")
            total_cost += _call_cost(
                str(model or ""),
                input_tokens,
                output_tokens,
            )
            total_input += input_tokens
            total_output += output_tokens

        return self._record(
            cost_eur=total_cost,
            input_tokens=total_input,
            output_tokens=total_output,
            segment_billed=True,
        )

    def record_error(
        self,
        model: str,
        error: Any,
    ) -> float:
        input_tokens = int(
            getattr(error, "input_tokens", 0) or 0
        )
        output_tokens = int(
            getattr(error, "output_tokens", 0) or 0
        )

        cost = _call_cost(
            model,
            input_tokens,
            output_tokens,
        )

        return self._record(
            cost_eur=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            segment_billed=bool(
                input_tokens or output_tokens
            ),
        )
