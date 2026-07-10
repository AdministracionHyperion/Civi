from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .schemas import GetInfraccionDetailRequest, GetInfraccionDetailResponse


def _load_infracciones() -> dict[str, Any]:
    resource = files("quote_service.data").joinpath("infracciones_cnt.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _build_infraccion_index() -> dict[str, dict[str, Any]]:
    data = _load_infracciones()
    infracciones = data.get("infracciones") or []
    index: dict[str, dict[str, Any]] = {}
    for inf in infracciones:
        codigo = str(inf.get("codigo", "")).strip().upper()
        if codigo:
            index[codigo] = inf
    return index


_INFRACCION_INDEX: dict[str, dict[str, Any]] | None = None


def _get_index() -> dict[str, dict[str, Any]]:
    global _INFRACCION_INDEX
    if _INFRACCION_INDEX is None:
        _INFRACCION_INDEX = _build_infraccion_index()
    return _INFRACCION_INDEX


async def get_infraccion_detail(payload: GetInfraccionDetailRequest) -> GetInfraccionDetailResponse:
    codigo = payload.codigo.strip().upper()
    index = _get_index()
    inf = index.get(codigo)

    if inf is None:
        return GetInfraccionDetailResponse(
            success=False,
            codigo=codigo,
            message=f"Infraccion con codigo {codigo} no encontrada en la base de datos.",
        )

    return GetInfraccionDetailResponse(
        success=True,
        codigo=codigo,
        categoria=str(inf.get("categoria", "")),
        smdlv=inf.get("smdlv") if isinstance(inf.get("smdlv"), (int, float)) else None,
        monto_cop_2026=inf.get("monto_cop_2026") if isinstance(inf.get("monto_cop_2026"), (int, float)) else None,
        descripcion=str(inf.get("descripcion_oficial") or ""),
        articulo=str(inf.get("articulo") or ""),
        admite_descuento_curso=bool(inf.get("admite_descuento_curso")),
        sancion_adicional=str(inf["sancion_adicional"]) if inf.get("sancion_adicional") else None,
        consejo=str(inf.get("consejos") or "") if inf.get("consejos") else "",
    )
