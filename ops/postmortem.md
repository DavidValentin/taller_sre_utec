# Postmortem: Campaña de Perú enviada erróneamente a clientes de Chile

> Sin culpables: buscamos qué falló en el proceso, no quién se equivocó.

**Equipo y roles:** Comandante: [ Juancarlos ] · Operador: [ David - Edgar ] · Comunicador: [ Leila - Fiorela ]

## Resumen

El viernes por la tarde se introdujo un error en el catálogo de países (`data/ref/paises.csv`) asignando el país "Perú" y región "Andina" al código "CL" (Chile). Al cargarse el lote de clientes del viernes, los nuevos clientes de Chile quedaron registrados como de Perú en la tabla Silver v2 y agregados a Perú en la tabla Gold, provocando que en la mañana del lunes Marketing enviara la campaña de Perú a clientes chilenos y que la campaña de Chile saliera incompleta.

## Impacto

- **Tablas afectadas:** 
  - `gameday.ref_paises` (desde corrida del viernes con commit `9ad2866`): catálogo sobrescrito con `CL -> Perú, Andina`.
  - `gameday.silver_customers_v2` (desde corrida del viernes `sha=9ad2866`): 4 clientes con `country_code = 'CL'` registrados erróneamente con `country_name = 'Perú'` y `region = 'Andina'`.
  - `gameday.gold_contactables_por_pais` (desde **versión 2**, 2026-11-02 01:30:39 UTC / 20:30:39 -05:00): el conteo de Perú se infló a 10 clientes (deberían ser 6), mientras que el de Chile bajó a 4 (deberían ser 8).
- **Clientes afectados:**
  - 4 clientes de Chile del lote del viernes (`customers_viernes.csv`):
    - ID 13: Tomás (`tomas@example.com`, edad 45, PASS)
    - ID 14: Isabel (`isabel@example.com`, edad 31, PASS)
    - ID 16: Fernanda (`fernanda@example.com`, edad 39, PASS)
    - ID 19: Gabriel (edad 36, email null, PASS)
  - 3 de ellos (Tomás, Isabel y Fernanda) son contactables y recibieron emails promocionales exclusivos de Perú en lugar de Chile.

## Línea de tiempo

| Hora (UTC) | Hora (-05:00) | Qué pasó |
| --- | --- | --- |
| 2026-10-23 22:48 UTC | 2026-10-23 17:48 (-05:00) | Se comitea `3915bc8` ("chore(ref): normaliza catálogo de países a ISO 3166") por Martín Soto con error en `CL -> Perú`. |
| 2026-10-23 23:05 UTC | 2026-10-23 18:05 (-05:00) | Se mergea a main en commit `9ad2866` ("Merge branch 'chore/normaliza-paises'"). |
| 2026-11-02 01:28:20 UTC | 2026-11-01 20:28:20 (-05:00) | Corrida del jueves: Gold v1 correcto (`sha=98dd769`). |
| 2026-11-02 01:30:40 UTC | 2026-11-01 20:30:40 (-05:00) | Corrida del viernes: Gold v2 corrupto con `sha=9ad2866`. |
| 2026-11-02 01:30:59 UTC | 2026-11-01 20:30:59 (-05:00) | **Inicio del incidente** registrado en `ops_event_log` (`run_id: 41372389743`, stage: `incidente_inicio`). |
| 2026-11-02 01:34:00 UTC | 2026-11-01 20:34:00 (-05:00) | **Detectamos la causa raíz y el cambio culpable** (commit `3915bc8` / merge `9ad2866`). |
| 2026-11-02 01:45:00 UTC | 2026-11-01 20:45:00 (-05:00) | **Contención**: Se decide retener el lote del lunes en `data/incoming/` y NO cargarlo aún para evitar corromper a 3 nuevos clientes de Chile (`CL`). Se avisa a Marketing para pausar la campaña de la tarde. |
| [ ... ] | [ ... ] | [ primer verificar en verde ] |

**MTTR:** [ minutos desde el inicio del incidente hasta el primer verificar en verde ]

## Causa raíz

- **¿Qué cambio lo causó?**
  El commit `3915bc8` (autor: Martín Soto, fecha: viernes 23 de octubre de 2026 17:48 -0500, merge `9ad2866` a las 18:05 -0500) que buscaba normalizar el catálogo de países a ISO 3166 modificó `data/ref/paises.csv`. Por error humano/copia, asignó `CL,CHL,Perú,Andina` en vez de `CL,CHL,Chile,Cono Sur`. Al procesar el lote del viernes con `load_silver.sql` (que une `bronze` con `ref_paises`), los 4 nuevos clientes de Chile se guardaron con país Perú en `silver_customers_v2`.
- **¿Por qué los checks no lo frenaron?**
  - `framework/validation/validate_silver.py` solo valida volumen total (`total_rows`), nombres nulos (`name_null_count`) y menores de edad (`underage_count`).
  - No existía ningún check de integridad referencial, ni validación de duplicados o consistencia código-país en `ref_paises` ni en `silver_customers_v2`.
  - El script `validate_silver.py` solo guardaba métricas en `ops_dq_results` pero no detenía el pipeline (no arrojaba error ni hacía fallar el job en caso de anomalías).
  - El test unitario `framework/tests/test_dataset.py` solo chequeaba el encabezado del archivo inicial `customers.csv`, no el catálogo de países ni las tablas transformadas en Databricks.

## Qué funcionó y qué no

- [ ... ]

## Acción preventiva

- Check nuevo en `framework/validation/validate_silver.py`: [ ¿qué valida? ]
- ¿Lo probaron? ¿Falla si vuelven a aplicar el cambio del viernes? [ sí / no ]
- Otras acciones (con dueño y fecha): [ ... ]
