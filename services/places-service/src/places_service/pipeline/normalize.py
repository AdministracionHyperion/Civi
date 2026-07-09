from __future__ import annotations

import re
import unicodedata


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(ch))


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_text(value: str) -> str:
    return collapse_spaces(strip_accents(value).upper())


def title_case_es(value: str) -> str:
    text = collapse_spaces(value)
    if not text:
        return ""
    return " ".join(part.capitalize() for part in text.lower().split())


# Official Colombian NIT verification digit (DIAN / Cámara de Comercio algorithm).
_NIT_WEIGHTS = (71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3)


def compute_nit_verification_digit(number: str) -> str | None:
    digits = re.sub(r"\D", "", number or "")
    if not digits or len(digits) > 15:
        return None
    total = 0
    for idx, ch in enumerate(reversed(digits)):
        if idx >= len(_NIT_WEIGHTS):
            return None
        total += int(ch) * _NIT_WEIGHTS[idx]
    remainder = total % 11
    if remainder in (0, 1):
        return str(remainder)
    return str(11 - remainder)


def normalize_document(raw: str | None) -> dict:
    document_raw = collapse_spaces(raw or "") if raw else None
    digits = re.sub(r"\D", "", document_raw or "")
    result = {
        "document_raw": document_raw,
        "document_type": "UNKNOWN",
        "document_number": None,
        "verification_digit": None,
        "document_valid": False,
        "flags": [],
    }
    if not digits:
        result["flags"].append("missing_document")
        return result

    # Only claim NIT when the trailing verification digit matches the official algorithm.
    # Never mark a bare number as a valid NIT just because a DV can be computed for it.
    if len(digits) >= 6:
        body, maybe_dv = digits[:-1], digits[-1]
        expected = compute_nit_verification_digit(body)
        if expected is not None and expected == maybe_dv and 8 <= len(body) <= 10:
            result.update(
                {
                    "document_type": "NIT",
                    "document_number": body,
                    "verification_digit": maybe_dv,
                    "document_valid": True,
                }
            )
            result["flags"].append("nit_with_verification_digit")
            return result
        if expected is not None and expected == maybe_dv:
            result.update(
                {
                    "document_type": "NIT",
                    "document_number": body,
                    "verification_digit": maybe_dv,
                    "document_valid": True,
                }
            )
            result["flags"].append("nit_with_verification_digit")
            result["flags"].append("nit_body_length_unusual")
            return result
        if 9 <= len(digits) <= 11:
            # Possible NIT with DV attached but invalid check digit — keep raw digits, do not invent type.
            result.update(
                {
                    "document_type": "UNKNOWN",
                    "document_number": digits,
                    "document_valid": False,
                }
            )
            result["flags"].append("possible_nit_invalid_verification_digit")
            return result

    if len(digits) in {6, 7, 8, 9, 10}:
        result.update(
            {
                "document_type": "CC_OR_NIT_UNKNOWN",
                "document_number": digits,
                "document_valid": False,
            }
        )
        result["flags"].append("ambiguous_document_type")
        return result

    result["document_number"] = digits
    result["flags"].append("atypical_document_length")
    return result


_FAKE_PHONES = frozenset(
    {
        "0",
        "0000000",
        "00000000",
        "1111111",
        "1234567",
        "3000000",
        "3000000000",
        "7777777",
        "9999999",
        "9999999999",
    }
)


def _is_repetitive(digits: str) -> bool:
    return len(digits) >= 6 and len(set(digits)) == 1


def split_phone_candidates(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[\s,;/|]+", raw.strip())
    return [p for p in parts if p]


def normalize_phone(raw: str | None) -> list[dict]:
    results: list[dict] = []
    for part in split_phone_candidates(raw):
        digits = re.sub(r"\D", "", part)
        item = {
            "value_raw": part,
            "value_normalized": digits or None,
            "e164": None,
            "contact_type": "unknown",
            "is_valid": False,
            "flags": [],
        }
        if not digits or digits in _FAKE_PHONES or _is_repetitive(digits):
            item["flags"].append("fake_or_empty")
            results.append(item)
            continue
        if digits.startswith("57") and len(digits) == 12 and digits[2] == "3":
            mobile = digits[2:]
            item.update(
                {
                    "value_normalized": mobile,
                    "e164": f"+{digits}",
                    "contact_type": "mobile",
                    "is_valid": True,
                }
            )
        elif len(digits) == 10 and digits.startswith("3"):
            item.update(
                {
                    "value_normalized": digits,
                    "e164": f"+57{digits}",
                    "contact_type": "mobile",
                    "is_valid": True,
                }
            )
        elif 7 <= len(digits) <= 10:
            item.update(
                {
                    "value_normalized": digits,
                    "contact_type": "landline",
                    "is_valid": True,
                }
            )
        else:
            item["flags"].append("unrecognized_phone")
        results.append(item)
    return results


_ADDR_REPLACEMENTS = (
    (r"\b(CRA|CR|KR|KRA)\b\.?", "CARRERA"),
    (r"\b(CL|CLL|CALL)\b\.?", "CALLE"),
    (r"\b(AV|AVE)\b\.?", "AVENIDA"),
    (r"\b(AK)\b\.?", "AVENIDA CARRERA"),
    (r"\b(DG|DIAG)\b\.?", "DIAGONAL"),
    (r"\b(TV|TR|TRANS)\b\.?", "TRANSVERSAL"),
    (r"\b(BRR|BARRIO)\b\.?", "BARRIO"),
    (r"\b(VDA|VEREDA)\b\.?", "VEREDA"),
    (r"\b(KM|KILOMETRO|KILÓMETRO)\b\.?", "KILOMETRO"),
    (r"\b(NO|NRO|NUM|NUMERO|NÚMERO)\b\.?", "#"),
)


def normalize_address(raw: str | None, *, city: str | None = None, department: str | None = None) -> dict:
    address_raw = collapse_spaces(raw or "")
    flags: list[str] = []
    if not address_raw:
        return {
            "address_raw": "",
            "address_normalized": "",
            "address_quality": "missing",
            "flags": ["missing_address"],
        }

    normalized = normalize_text(address_raw)
    for pattern, repl in _ADDR_REPLACEMENTS:
        normalized = re.sub(pattern, repl, normalized, flags=re.IGNORECASE)
    normalized = collapse_spaces(normalized)

    city_n = normalize_text(city or "")
    dept_n = normalize_text(department or "")
    only_city_dept = False
    if city_n and dept_n and normalized in {f"{city_n}, {dept_n}", f"{city_n} {dept_n}", city_n}:
        only_city_dept = True
        flags.append("city_department_only")

    if normalized in {"0", "N/A", "NA", "S/N", "SIN DIRECCION", "NO REPORTA"}:
        flags.append("invalid_placeholder")
        return {
            "address_raw": address_raw,
            "address_normalized": normalized,
            "address_quality": "invalid",
            "flags": flags,
        }

    has_street_token = bool(
        re.search(r"\b(CALLE|CARRERA|AVENIDA|DIAGONAL|TRANSVERSAL|KILOMETRO|VEREDA|AUTOPISTA|VIA)\b", normalized)
    )
    has_number = bool(re.search(r"\d", normalized))

    if only_city_dept or (not has_street_token and not has_number):
        if only_city_dept and "insufficient_for_geocoding" not in flags:
            flags.append("insufficient_for_geocoding")
        if not has_street_token and not has_number and "insufficient_for_geocoding" not in flags:
            flags.append("insufficient_for_geocoding")
        return {
            "address_raw": address_raw,
            "address_normalized": normalized,
            "address_quality": "partial" if normalized else "missing",
            "flags": flags or ["insufficient_for_geocoding"],
        }

    if has_street_token and has_number:
        return {
            "address_raw": address_raw,
            "address_normalized": normalized,
            "address_quality": "valid",
            "flags": flags,
        }

    flags.append("partial_address")
    return {
        "address_raw": address_raw,
        "address_normalized": normalized,
        "address_quality": "partial",
        "flags": flags,
    }


_STATUS_NAME_HINTS = (
    ("RETIRADO", "retired"),
    ("CANCELADO", "retired"),
    ("INACTIVO", "inactive"),
    ("SUSPENDIDO", "suspended"),
)


def infer_operational_status(name: str | None, *, source_status: str | None = None) -> dict:
    name_n = normalize_text(name or "")
    for token, status in _STATUS_NAME_HINTS:
        if token in name_n:
            return {
                "operational_status": status,
                "status_verified": False,
                "status_source": "name_inference",
                "status_inferred_from_name": True,
                "requires_manual_review": True,
                "exclude_from_normal_search": status in {"retired", "inactive", "suspended"},
            }
    if source_status and source_status.lower() in OPERATIONAL_FROM_SOURCE:
        return {
            "operational_status": source_status.lower(),
            "status_verified": True,
            "status_source": "official_source",
            "status_inferred_from_name": False,
            "requires_manual_review": False,
            "exclude_from_normal_search": source_status.lower() in {"retired", "inactive", "suspended"},
        }
    return {
        "operational_status": "unknown",
        "status_verified": False,
        "status_source": None,
        "status_inferred_from_name": False,
        "requires_manual_review": False,
        "exclude_from_normal_search": False,
    }


OPERATIONAL_FROM_SOURCE = frozenset({"active", "inactive", "suspended", "retired", "unknown"})


# Common municipality aliases aligned with bot extractors + DIVIPOLA-ish names.
MUNICIPALITY_ALIASES: dict[str, tuple[str, str, str | None]] = {
    # canonical_name, department, municipality_code (None if unknown without DIVIPOLA dump)
    "BOGOTA": ("Bogota", "Bogota D.C.", "11001"),
    "BOGOTA D.C.": ("Bogota", "Bogota D.C.", "11001"),
    "BOGOTA, D.C.": ("Bogota", "Bogota D.C.", "11001"),
    "BOGOTA, D. C.": ("Bogota", "Bogota D.C.", "11001"),
    "MEDELLIN": ("Medellin", "Antioquia", "05001"),
    "CALI": ("Cali", "Valle del Cauca", "76001"),
    "BUCARAMANGA": ("Bucaramanga", "Santander", "68001"),
    "BARRANQUILLA": ("Barranquilla", "Atlantico", "08001"),
    "CARTAGENA": ("Cartagena", "Bolivar", "13001"),
    "CUCUTA": ("Cucuta", "Norte de Santander", "54001"),
    "IBAGUE": ("Ibague", "Tolima", "73001"),
    "PEREIRA": ("Pereira", "Risaralda", "66001"),
    "MANIZALES": ("Manizales", "Caldas", "17001"),
    "VILLAVICENCIO": ("Villavicencio", "Meta", "50001"),
    "SANTA MARTA": ("Santa Marta", "Magdalena", "47001"),
    "PASTO": ("Pasto", "Narino", "52001"),
    "NEIVA": ("Neiva", "Huila", "41001"),
    "ARMENIA": ("Armenia", "Quindio", "63001"),
    "MONTERIA": ("Monteria", "Cordoba", "23001"),
    "VALLEDUPAR": ("Valledupar", "Cesar", "20001"),
    "POPAYAN": ("Popayan", "Cauca", "19001"),
    "SINCELEJO": ("Sincelejo", "Sucre", "70001"),
    "TUNJA": ("Tunja", "Boyaca", "15001"),
    "YOPAL": ("Yopal", "Casanare", "85001"),
}


DEPARTMENT_ALIASES: dict[str, str] = {
    "BOGOTA D.C.": "Bogota D.C.",
    "BOGOTA, D.C.": "Bogota D.C.",
    "BOGOTA": "Bogota D.C.",
    "N. DE SANTANDER": "Norte de Santander",
    "NORTE DE SANTANDER": "Norte de Santander",
    "VALLE DEL CAUCA": "Valle del Cauca",
    "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA": "San Andres",
    "SAN ANDRES": "San Andres",
}


_DIVIPOLA_INDEX: dict[str, dict[str, str]] | None = None
_DIVIPOLA_BY_NAME: dict[str, list[dict[str, str]]] | None = None


def _load_divipola() -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    global _DIVIPOLA_INDEX, _DIVIPOLA_BY_NAME
    if _DIVIPOLA_INDEX is not None and _DIVIPOLA_BY_NAME is not None:
        return _DIVIPOLA_INDEX, _DIVIPOLA_BY_NAME
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parents[3] / "data" / "reference" / "divipola_municipios.json"
    by_code: dict[str, dict[str, str]] = {}
    by_name: dict[str, list[dict[str, str]]] = {}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("municipalities") or []:
            code = str(row.get("municipality_code") or "").strip()
            name = title_case_es(str(row.get("municipality") or ""))
            dept = title_case_es(str(row.get("department") or ""))
            dcode = str(row.get("department_code") or "").strip() or None
            if not code or not name:
                continue
            item = {
                "municipality": name,
                "department": dept,
                "municipality_code": code,
                "department_code": dcode or (code[:2] if len(code) >= 2 else None),
            }
            by_code[code] = item
            by_name.setdefault(normalize_text(name), []).append(item)
    _DIVIPOLA_INDEX = by_code
    _DIVIPOLA_BY_NAME = by_name
    return by_code, by_name


def resolve_territory(city: str | None, department: str | None) -> dict:
    raw_city = collapse_spaces(city or "")
    raw_department = collapse_spaces(department or "")
    city_n = normalize_text(raw_city)
    dept_n = normalize_text(raw_department)
    population_center = None
    locality = None
    flags: list[str] = []

    # Split "Municipio - Centro Poblado"
    if " - " in raw_city:
        left, right = raw_city.split(" - ", 1)
        left_n = normalize_text(left)
        if left_n in MUNICIPALITY_ALIASES or len(left) <= 40:
            city_n = left_n
            population_center = title_case_es(right)
            flags.append("population_center_split")
            if left_n.startswith("BOGOTA"):
                locality = title_case_es(right)
                population_center = None

    dept_canonical = DEPARTMENT_ALIASES.get(dept_n, title_case_es(raw_department) if raw_department else "")
    if city_n in MUNICIPALITY_ALIASES:
        mun_name, mun_dept, mun_code = MUNICIPALITY_ALIASES[city_n]
        return {
            "municipality": mun_name,
            "department": mun_dept,
            "municipality_code": mun_code,
            "department_code": mun_code[:2] if mun_code else None,
            "population_center": population_center,
            "locality": locality,
            "raw_city": raw_city,
            "raw_department": raw_department,
            "confidence": "high",
            "flags": flags,
        }

    if not city_n:
        flags.append("missing_city")
        return {
            "municipality": "",
            "department": dept_canonical,
            "municipality_code": None,
            "department_code": None,
            "population_center": population_center,
            "locality": locality,
            "raw_city": raw_city,
            "raw_department": raw_department,
            "confidence": "none",
            "flags": flags,
        }

    _, by_name = _load_divipola()
    candidates = by_name.get(city_n) or []
    if dept_canonical:
        dept_key = normalize_text(dept_canonical)
        matched = [c for c in candidates if normalize_text(c["department"]) == dept_key]
        if len(matched) == 1:
            hit = matched[0]
            return {
                "municipality": hit["municipality"],
                "department": hit["department"],
                "municipality_code": hit["municipality_code"],
                "department_code": hit["department_code"],
                "population_center": population_center,
                "locality": locality,
                "raw_city": raw_city,
                "raw_department": raw_department,
                "confidence": "high",
                "flags": flags + ["divipola_match"],
            }
        if len(matched) > 1:
            flags.append("ambiguous_divipola_match")
    elif len(candidates) == 1:
        hit = candidates[0]
        return {
            "municipality": hit["municipality"],
            "department": hit["department"],
            "municipality_code": hit["municipality_code"],
            "department_code": hit["department_code"],
            "population_center": population_center,
            "locality": locality,
            "raw_city": raw_city,
            "raw_department": raw_department,
            "confidence": "medium",
            "flags": flags + ["divipola_name_only_match"],
        }
    elif len(candidates) > 1:
        flags.append("ambiguous_municipality_name")

    flags.append("unresolved_municipality_code")
    return {
        "municipality": title_case_es(city_n),
        "department": dept_canonical or title_case_es(raw_department),
        "municipality_code": None,
        "department_code": None,
        "population_center": population_center,
        "locality": locality,
        "raw_city": raw_city,
        "raw_department": raw_department,
        "confidence": "medium" if candidates else "low",
        "flags": flags,
    }
