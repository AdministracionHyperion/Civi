# Inventario Manizales — refresh offline del CSV canónico

Modo offline: sincroniza los 12 IDs de auditoría originales con el CSV actual (44 filas).
No consulta el Geoportal. No borra evidencia geoportal previa si ya existía.

Servicio de referencia: `https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10`
Consulta/local: `2026-07-10T20:53:49Z`

## Conteos CSV actuales

```json
{
  "total": 44,
  "by_kind": {
    "CDA": 14,
    "CEA": 15,
    "CIA": 8,
    "CRC": 7
  },
  "by_validation_status": {
    "confirmed_address": 18,
    "confirmed_business": 19,
    "approximate_not_confirmed": 7
  }
}
```

## Filas de auditoría (12 IDs originales)

| ID | CSV status | precision | lat,lng |
|---|---|---|---|
| `cda-manizales-cda-caldas-el-bosque-a730920403` | `confirmed_address` | `building` | 5.0619543,-75.5239713 |
| `cda-manizales-cda-socicar-7acac31f0f` | `approximate_not_confirmed` | `street_intersection` | 5.0694483,-75.5235525 |
| `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c` | `confirmed_address` | `building` | 5.0668747,-75.5108309 |
| `cea-manizales-academia-automovilistica-caldas-sas-12d613c393` | `confirmed_address` | `building` | 5.0627089,-75.4949577 |
| `cea-manizales-academia-automovilistica-piloto-177f760536` | `approximate_not_confirmed` | `address_interpolation` | 5.0680434,-75.5217931 |
| `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0` | `approximate_not_confirmed` | `address_interpolation` | 5.0518489,-75.4840936 |
| `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930` | `confirmed_address` | `building` | 5.0627826,-75.4962432 |
| `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e` | `confirmed_address` | `building` | 5.0694094,-75.5181173 |
| `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047` | `approximate_not_confirmed` | `address_interpolation` | 5.0692235,-75.5179797 |
| `cia-manizales-cimyc-manizales-s-a-s-498175000a` | `approximate_not_confirmed` | `street_intersection` | 5.05813485,-75.48422695 |
| `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d` | `approximate_not_confirmed` | `street_intersection` | 5.0702978,-75.5177831 |
| `crc-manizales-certificamos-agustinos-98839ab670` | `approximate_not_confirmed` | `street_intersection` | 5.069385,-75.5203143 |
