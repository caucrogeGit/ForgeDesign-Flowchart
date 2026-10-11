"""Codec de la ressource Flowchart V0.1 : octets ↔ FlowDocument, sans filesystem.

Le JSON est contrôlé strictement par le cœur (UTF-8, clés uniques, constantes
non standard refusées) avant la validation Pydantic en mode JSON strict. Les
erreurs deviennent des diagnostics bornés du contrat spécialisé, localisés dans
le document.
"""

import json
from collections.abc import Iterator

from forge_design.specialized import (
    MAX_SPECIALIZED_ISSUES,
    MAX_SPECIALIZED_LOCATION_DEPTH,
    SpecializedFormatError,
    SpecializedIssue,
    SpecializedValidationResult,
    loads_strict_json,
)
from pydantic import ValidationError
from pydantic_core import ErrorDetails, PydanticSerializationError

from forge_design_flowchart.models import FlowDocument
from forge_design_flowchart.validation import STRUCTURE, validate_flowchart

_IDENTITY_FIELDS = frozenset({"id", "source", "target"})
_LIMIT_TYPES = frozenset(
    {"too_long", "string_too_long", "less_than_equal", "greater_than_equal"}
)
# Erreurs propres au modèle : code du diagnostic et champ fautif.
_CUSTOM = {
    "flowchart_identity_duplicate": ("flowchart.identity-duplicate", "id"),
    "flowchart_endpoint_unknown": ("flowchart.endpoint-unknown", None),
    "flowchart_self_loop": ("flowchart.self-loop", "target"),
}
_MESSAGES = {
    "flowchart.json-invalid": "JSON invalide",
    "flowchart.validation-error": "Structure invalide",
    "flowchart.identity-invalid": "Identité invalide",
    "flowchart.identity-duplicate": "Identité dupliquée",
    "flowchart.endpoint-unknown": "Extrémité inconnue",
    "flowchart.self-loop": "Boucle sur un même nœud",
    "flowchart.label-invalid": "Libellé invalide",
    "flowchart.limit-exceeded": "Limite dépassée",
}


def _issue(
    code: str, detail: str, location: tuple[str | int, ...] = ()
) -> SpecializedIssue:
    return SpecializedIssue(
        code,
        "error",
        f"{_MESSAGES[code]} : {detail}",
        STRUCTURE,
        location[:MAX_SPECIALIZED_LOCATION_DEPTH],
    )


def _location(data: object, loc: tuple[str | int, ...]) -> tuple[str | int, ...]:
    """Chemin réel dans le document : seuls les éléments existants sont repris."""
    path: list[str | int] = []
    current = data
    for position, element in enumerate(loc):
        last = position == len(loc) - 1
        if isinstance(current, dict) and isinstance(element, str):
            if element in current:
                path.append(element)
                current = current[element]  # pyright: ignore[reportUnknownVariableType]
            elif last:
                path.append(element)
        elif (
            isinstance(current, list)
            and isinstance(element, int)
            and 0 <= element < len(current)  # pyright: ignore[reportUnknownArgumentType]
        ):
            path.append(element)
            current = current[element]  # pyright: ignore[reportUnknownVariableType]
    return tuple(path)


def _code(error: ErrorDetails, location: tuple[str | int, ...]) -> str:
    if error["type"] == "flowchart_label":
        return "flowchart.label-invalid"
    if error["type"] in _LIMIT_TYPES:
        return "flowchart.limit-exceeded"
    if location and location[-1] in _IDENTITY_FIELDS:
        return "flowchart.identity-invalid"
    return "flowchart.validation-error"


def _issues(error: ValidationError, data: object) -> Iterator[SpecializedIssue]:
    for detail in error.errors(include_url=False, include_input=False):
        custom = _CUSTOM.get(detail["type"])
        if custom is not None:
            context = detail.get("ctx") or {}
            code, field = custom
            collection = str(context.get("collection", "edges"))
            field = field or str(context["end"])
            location = (collection, int(context["index"]), field)
            yield _issue(code, detail["msg"], location)
            continue
        location = _location(data, tuple(detail["loc"]))
        yield _issue(_code(detail, location), detail["msg"], location)


def _bounded(issues: Iterator[SpecializedIssue]) -> tuple[SpecializedIssue, ...]:
    # Une issue de plus que le plafond signale la troncature au socle.
    result: list[SpecializedIssue] = []
    for issue in issues:
        result.append(issue)
        if len(result) > MAX_SPECIALIZED_ISSUES:
            break
    return tuple(result)


def _strict_json(data: bytes) -> tuple[str, object]:
    text = data.decode("utf-8")
    return text, loads_strict_json(text)


class FlowCodec:
    """Implémente SpecializedResourceCodec[FlowDocument]."""

    def detect_version(self, data: bytes) -> str | None:
        # Lecture du seul champ format_version, sans validation métier.
        try:
            _, parsed = _strict_json(data)
        except (UnicodeError, ValueError, RecursionError):
            return None
        if isinstance(parsed, dict):
            version = parsed.get("format_version")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(version, str):
                return version
        return None

    def decode(self, data: bytes) -> FlowDocument:
        try:
            text, parsed = _strict_json(data)
        except UnicodeError:
            raise SpecializedFormatError(
                (_issue("flowchart.json-invalid", "UTF-8 attendu."),)
            ) from None
        except (ValueError, RecursionError) as error:
            raise SpecializedFormatError(
                (_issue("flowchart.json-invalid", str(error) or "JSON illisible."),)
            ) from None
        try:
            return FlowDocument.model_validate_json(text)
        except ValidationError as error:
            raise SpecializedFormatError(_bounded(_issues(error, parsed))) from None

    def encode(self, resource: FlowDocument) -> bytes:
        """Sérialisation canonique : ordre des champs du modèle et des collections."""
        payload = resource.model_dump(mode="json", exclude_none=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        return (text + "\n").encode("utf-8")

    def validate(self, resource: FlowDocument) -> SpecializedValidationResult:
        """Format (copie sérialisée revalidée) puis domaine. Un format invalide
        n'est pas évalué plus loin."""
        try:
            text = resource.model_dump_json(exclude_none=True)
        except (PydanticSerializationError, AttributeError, TypeError, ValueError):
            return SpecializedValidationResult.bounded(
                (_issue("flowchart.validation-error", "Document non sérialisable."),)
            )
        try:
            document = FlowDocument.model_validate_json(text)
        except ValidationError as error:
            return SpecializedValidationResult.bounded(_issues(error, json.loads(text)))
        return validate_flowchart(document)
