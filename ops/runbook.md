# Runbook: Inconsistencia en catálogo de referencia y corrupción geográfica en Silver / Gold

> Un runbook es lo que haría cualquier persona del equipo si esto vuelve a
> pasar a las 3 a. m. Escríbanlo para alguien que no estuvo hoy.

## Cómo me doy cuenta

- **Alerta de negocio:** Marketing reporta clientes quejándose por recibir promociones de otro país (ej. clientes de Chile recibiendo promociones exclusivas de Perú), o un dashboard Gold con volúmenes anormalmente inflados o deprimidos por país.
- **Query de diagnóstico inicial en Databricks SQL:**
  ```sql
  -- Si un mismo código de país tiene nombres distintos, el catálogo/cruce falló:
  SELECT country_code, country_name, region, COUNT(*) AS clientes
  FROM gameday.silver_customers_v2
  GROUP BY country_code, country_name, region
  ORDER BY country_code;
  ```
- **Historial y logs:**
  ```sql
  -- Ver qué corridas se ejecutaron recientemente y con qué commit sha:
  SELECT run_id, event_ts, stage, status, details
  FROM gameday.ops_event_log
  ORDER BY event_ts DESC;
  ```

## Contener (que no empeore)

- **Retener lotes entrantes:** NO mover ningún archivo desde `data/incoming/` a `data/source/`. Mantener los archivos en cuarentena hasta solucionar la causa raíz.
- **Congelar despliegues a producción:** No hacer `push` a `main` para evitar que GitHub Actions dispare el pipeline automático con el catálogo corrupto.
- **Avisar de inmediato a Marketing:** Informar al equipo de Marketing que pause de inmediato cualquier campaña basada en `gameday.gold_contactables_por_pais`.

## Recuperar

1. **Código:**
   - Identificar el commit que modificó el catálogo (`git log -p -n 5 data/ref/paises.csv`).
   - Crear una rama de fix: `git checkout -b fix/corrige-catalogo`.
   - Corregir el archivo `data/ref/paises.csv` con los valores válidos (`CL,CHL,Chile,Cono Sur`).
   - Mover el lote retenido (`data/incoming/customers_*.csv`) a `data/source/`.
   - Abrir Pull Request hacia `main`.

2. **Datos:**
   - En Databricks SQL Editor, corregir los datos corruptos in-place (ya que `load_silver.sql` solo inserta filas no existentes y no actualiza automáticamente los registros ya cargados):
     ```sql
     UPDATE gameday.silver_customers_v2
     SET country_name = 'Chile', region = 'Cono Sur'
     WHERE country_code = 'CL';

     UPDATE gameday.ref_paises
     SET country_name = 'Chile', region = 'Cono Sur'
     WHERE country_code = 'CL';
     ```

3. **Reproceso:**
   - Hacer merge del PR hacia `main`. Esto dispara el workflow `DataOps Pipeline`.
   - El pipeline recarga `ref_paises`, procesa los nuevos datos e inserta los clientes pendientes mediante `MERGE` (`WHEN NOT MATCHED THEN INSERT`). Sabemos que no duplica porque hace matching por `customer_id`.
   - El stage `gold` sobrescribe `gold_contactables_por_pais` con los datos consolidados y correctos.

4. **Pendientes:**
   - El lote retenido del lunes se procesa automáticamente al hacer merge del PR.

## Cómo confirmo que volvimos a un estado bueno

- Ejecutar el workflow **Actions → Game day – Verificar**.
- Debe dar **55/55 puntos técnicos** en verde:
  - `ref_paises` con catálogo OK (todos los códigos mapeados correctamente).
  - Clientes con país mal en Silver: `0`.
  - Duplicados en Silver: `0` (`SELECT customer_id, COUNT(*) FROM gameday.silver_customers_v2 GROUP BY customer_id HAVING COUNT(*) > 1` devuelve 0 filas).
  - Gold cuadra exactamente con el conteo de contactables por país.

## A quién aviso

| Momento | A quién | Qué le digo |
| --- | --- | --- |
| Al detectar | Valeria (Marketing) / Stakeholders | *"Detectamos una inconsistencia en el cruce de países que afectó los clientes chilenos cargados recientemente. Por favor, **pausen de inmediato las campañas programadas para hoy** que usen la tabla `gold_contactables_por_pais` mientras solucionamos el problema."* |
| Al recuperar | Valeria (Marketing) / Stakeholders | *"El incidente fue resuelto. Se corrigió el catálogo maestro, se sanearon los clientes afectados en Silver y se recalculó la tabla Gold. Las métricas están 100% verificadas. Ya pueden reanudar el envío de campañas de manera segura."* |
