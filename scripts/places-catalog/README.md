# Places catalog (RUNT) — Fase 1

Pipeline offline para armar el catálogo nacional de CDA / CEA / CRC / CIA **sin geocoding** (costo Google = $0).

## Scripts

```powershell
# 1) Scrape RUNT (reanudable; shards en data/places/raw/)
python scripts/places-catalog/scrape_runt.py --delay 0.6

# Opcional: un departamento
python scripts/places-catalog/scrape_runt.py --department Santander --kinds CDA,CIA

# 2) Normalizar a JSON sin coordenadas
python scripts/places-catalog/normalize_runt.py
```

Salidas:

- `data/places/raw/*.json` — shards crudos por tipo/depto/municipio
- `data/places/places_colombia_sin_coords.json` — catálogo normalizado
- `data/places/places_colombia_summary.json` — conteos

## Fase 2 (no ejecutar aún)

Geocoding híbrido (Google ≤ 8k/mes + Nominatim) queda pendiente de aprobación explícita para no consumir cuota.
