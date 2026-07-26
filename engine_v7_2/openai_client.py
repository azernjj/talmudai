from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any


class OpenAIEngineError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        super().__init__(message)
        self.input_tokens = int(input_tokens)
        self.output_tokens = int(output_tokens)
        self.total_tokens = (
            self.input_tokens + self.output_tokens
        )


@dataclass
class ModelResult:
    data: dict[str, Any]
    response_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    raw_text: str
    attempts: int = 1


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start < 0 or end <= start:
            raise OpenAIEngineError(
                "Le modèle n'a pas renvoyé d'objet JSON."
            )

        try:
            payload = json.loads(
                cleaned[start:end + 1]
            )
        except json.JSONDecodeError as exc:
            raise OpenAIEngineError(
                f"JSON du modèle invalide : {exc}"
            ) from exc

    if not isinstance(payload, dict):
        raise OpenAIEngineError(
            "La réponse JSON doit être un objet."
        )

    return payload


def _usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)

    input_tokens = int(
        getattr(usage, "input_tokens", 0) or 0
    )
    output_tokens = int(
        getattr(usage, "output_tokens", 0) or 0
    )

    return input_tokens, output_tokens


class ResponsesJsonClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 180.0,
        json_attempts: int = 2,
    ) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise OpenAIEngineError(
                "OPENAI_API_KEY est absente de l'environnement."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIEngineError(
                "Le paquet openai manque. "
                "Installe-le avec : pip install -U openai"
            ) from exc

        self.client = OpenAI(
            timeout=timeout_seconds,
            max_retries=2,
        )
        self.json_attempts = max(
            1,
            int(json_attempts),
        )

    def create_json(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        max_output_tokens: int = 3200,
    ) -> ModelResult:
        total_input_tokens = 0
        total_output_tokens = 0

        for attempt in range(
            1,
            self.json_attempts + 1,
        ):
            retry_instruction = ""

            if attempt > 1:
                retry_instruction = (
                    "\n\nRetourne impérativement un unique "
                    "objet JSON complet et valide, sans Markdown "
                    "et sans texte avant ou après."
                )

            response = self.client.responses.create(
                model=model,
                instructions=(
                    instructions + retry_instruction
                ),
                input=input_text,
                max_output_tokens=max_output_tokens,
                reasoning={"effort": "minimal"},
            )

            input_tokens, output_tokens = _usage(
                response
            )
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            raw_text = (
                getattr(response, "output_text", "")
                or ""
            )

            try:
                data = _extract_json(raw_text)
            except OpenAIEngineError as exc:
                if attempt >= self.json_attempts:
                    raise OpenAIEngineError(
                        (
                            "JSON invalide après "
                            f"{self.json_attempts} tentative(s) : "
                            f"{exc}"
                        ),
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                    ) from exc

                print(
                    "⚠️ JSON invalide — nouvelle tentative "
                    f"{attempt + 1}/{self.json_attempts}."
                )
                time.sleep(1.5)
                continue

            return ModelResult(
                data=data,
                response_id=getattr(
                    response,
                    "id",
                    None,
                ),
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=(
                    total_input_tokens
                    + total_output_tokens
                ),
                raw_text=raw_text,
                attempts=attempt,
            )

        raise OpenAIEngineError(
            "Échec JSON inattendu.",
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
