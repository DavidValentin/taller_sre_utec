# Playbook FinOps: pipeline de contactables por país

> No buscamos la cifra exacta: buscamos que sepan de dónde sale el costo,
> quién es el dueño y qué decisión tomarían.

## 0. Supuestos de tarifa (iguales para todos)

Precios de lista públicos, revisados en octubre de 2026. Úsenlos tal cual para
que todos los equipos lleguen a números comparables.

| Recurso | Tarifa supuesta | De dónde sale |
| --- | --- | --- |
| GitHub Actions, runner Linux 2-core | USD 0.006 por minuto | Precio de lista de GitHub. **Cada job se redondea al minuto entero.** |
| Databricks SQL Warehouse serverless, 2X-Small | 4 DBU/hora × USD 0.70/DBU = **USD 2.80 por hora** | Tabla de DBU por tamaño de Databricks y tarifa Premium en AWS US East (USD 0.0467/min) |
| Auto-stop del warehouse | 10 minutos encendido sin uso después de la última query | Valor por defecto; revisen el de su warehouse |
| Hora-persona | USD 25 por hora | Supuesto del taller |

> Ojo: en un repo **público** los minutos de Actions no se cobran, y en
> Databricks Free Edition tampoco pagan el warehouse. Calculamos con precio de
> lista porque en una empresa sí se paga.

### Midan, no supongan: lo que registra Databricks

Mediciones reales obtenidas en Databricks (consultas a `system.billing.usage` y `system.query.history`):
- **Consumo por producto:** SQL Warehouse Serverless generó **3.05 DBU**, Interactive **0.88 DBU**, Storage **0.27 DBU**, y `PREDICTIVE_OPTIMIZATION` **0.25 DBU**.
- **Minutos de query vs facturación:** Databricks SQL Connector (GitHub Actions) ejecutó 227 sentencias acumulando **4.5 minutos de query útil**, mientras que SQL Editor y Notebooks sumaron **2.5 minutos**. 
- **Tiempo inactivo vs trabajo útil:** Con 4.5 min de query útil (~0.075 h) el cómputo puro costaría solo ~0.30 DBU. La diferencia hasta los 3.05 DBU cobrados es el **tiempo de auto-stop** (10 minutos encendido esperando después de cada corrida).
- **Costo oculto detectado:** `PREDICTIVE_OPTIMIZATION` cobró 0.25 DBU por optimizar tablas de solo 26 registros.
- **Atribución de usuario:** Todas las queries aparecen con `executed_by = 'dfvaler@gmail.com'`, lo que impide separar a nivel de factura el costo de CI/CD del trabajo manual interactivo.

---

## 1. ¿Cuánto cuesta una corrida?

Mediciones extraídas de `gameday.ops_event_log` y GitHub Actions:

| Stage | Minutos (Actions) | Minutos de warehouse (`ops_event_log`) | Costo estimado |
| --- | --- | --- | --- |
| deploy | 1 min | 0.5 min (~26-30s) | USD 0.006 (Actions) + USD 0.023 (DBX) = USD 0.029 |
| ref | 1 min | 0.5 min (~25-37s) | USD 0.006 (Actions) + USD 0.023 (DBX) = USD 0.029 |
| bronze | 1 min | 0.5 min (~29-30s) | USD 0.006 (Actions) + USD 0.023 (DBX) = USD 0.029 |
| silver | 1 min | 0.5 min (~24-29s) | USD 0.006 (Actions) + USD 0.023 (DBX) = USD 0.029 |
| validation | 1 min | 0.5 min (~30s) | USD 0.006 (Actions) + USD 0.023 (DBX) = USD 0.029 |
| gold | 1 min | 0.4 min (~24-25s) | USD 0.006 (Actions) + USD 0.019 (DBX) = USD 0.025 |
| tests | 1 min | — (local en runner) | USD 0.006 (Actions) |
| **Subtotal trabajo activo** | **7 min (Actions)** | **2.4 min (ejecución)** | **USD 0.176** |
| Auto-stop del warehouse | — | 10.0 min inactivo | 10 min × USD 0.0467 = **USD 0.467** |
| **Total por corrida** | | **12.4 min totales de warehouse** | **USD 0.643 por corrida** |

- **¿Cuántas veces corre al mes? ¿Por qué se dispara?**
  Se dispara por cada `push` a la rama `main` que modifique rutas bajo `data/**`, `framework/**` o el propio workflow. En un esquema de producción estándar con 3 ingestas semanales (12 al mes) más ~4 despliegues/mantenimientos, corre aproximadamente **16 a 20 veces al mes**.
- **Costo mensual estimado:**
  20 corridas × USD 0.643 = **USD 12.86 al mes**.
  *(Si corriera a diario con 30 corridas: 30 × USD 0.643 = USD 19.29 al mes).*

---

## 2. ¿Cuánto costó el incidente?

- **Corridas extra de infraestructura:**
  - 1 corrida de `preparar-produccion` (4.7 min warehouse + auto-stop = 14.7 min): USD 0.69
  - 2 corridas de pipeline (PR fix + deploy preventivo = ~25 min warehouse con auto-stops): USD 1.28
  - 1 corrida de `verificar`: USD 0.15
  - Total cómputo extra: **USD 2.12**.
- **Horas-persona:**
  - 5 personas (Comandante, 2 Operadores, 2 Comunicadores) × 56.1 minutos de MTTR (0.935 horas) × USD 25/hora = **USD 116.88**.
- **Costo total del incidente:**
  USD 2.12 (Infraestructura) + USD 116.88 (Horas-persona) = **USD 119.00**.
  *(El 98.2% del costo del incidente correspondió al tiempo del equipo, lo que demuestra que reducir el MTTR es la palanca FinOps más potente).*
- **¿Cuánto habría costado recargar todo en vez de lo que hicieron?**
  Hacer un *full reload* destructivo habría requerido borrar tablas, reprocesar todos los CSVs desde cero, validar y depurar duplicados. Habría tomado al menos 2 horas adicionales de equipo (2h × 5 personas × $25 = $250 extra) más múltiples ciclos de warehouse. Al corregir in-place con `UPDATE` las 4 filas de Chile, el equipo ahorró más de USD 250 y eliminó el riesgo de duplicación.

---

## 3. ¿Quién es el dueño?

El dueño no se escribe en un Excel: se deja **en el recurso**, con tags, igual
que en Azure o AWS. Así un reporte de costos lo puede leer solo.

- **¿Quién usa `gold_contactables_por_pais`? ¿Quién debería responder por su costo?**
  El usuario final es el equipo de **Marketing** (Valeria), quienes consumen los datos para segmentar sus campañas. Por tanto, Marketing es la unidad de negocio que extrae valor y debe ser dueña de la tabla Gold (`owner = 'marketing'`, `cost_center = 'CC-1020'`).
- **Tagueo desde código en `framework/deployment/deploy_silver_v2.sql`:**
  ```sql
  ALTER TABLE gameday.gold_contactables_por_pais
    SET TAGS ('owner' = 'marketing', 'cost_center' = 'CC-1020', 'consumer' = 'marketing');
  ```
- **Comprobación en `information_schema.table_tags`:**
  Verificado con éxito en Databricks:
  - `gold_contactables_por_pais` | `owner` | `marketing`
  - `gold_contactables_por_pais` | `cost_center` | `CC-1020`
  - `gold_contactables_por_pais` | `consumer` | `marketing`
- **Política como código:**
  El workflow `FinOps – Política de tags` corre `framework/tests/test_owner_tags.py` y valida que ninguna tabla Gold carezca del tag `owner`. Con este cambio, queda en verde.
- **Tags en el Warehouse:**
  Los tags de tabla son de gobernanza; el costo de cómputo lo factura el SQL Warehouse. Para atribuirlo en `system.billing.usage.custom_tags`, el warehouse debe configurarse con:
  `{'environment': 'production', 'team': 'dataops', 'primary_consumer': 'marketing'}`.
  *¿Qué pasa si dos equipos comparten el mismo warehouse?*
  Los costos de DBU se consolidan en una sola factura indiferenciada. Para prorratear el costo real por equipo, se debe cruzar `system.billing.usage` con `system.query.history` agrupando el consumo por `executed_by` o `client_application`, o bien crear warehouses dedicados si el volumen lo amerita.

---

## 4. ¿Qué deciden?

| Costo oculto que encontramos | Decisión (apagar / ajustar / priorizar) | Dueño | Fecha |
| --- | --- | --- | --- |
| **Auto-stop del Warehouse excesivo (10 min):** En cada corrida las queries tardan 2.4 min, pero el warehouse paga 10 min de ocio (80% del costo). | **Ajustar:** Reducir el auto-stop del SQL Warehouse de 10 minutos a **5 minutos** (o 2 minutos en Serverless). Ahorra ~50% del gasto en DBU inactivo. | David (Operador) | 2026-11-04 |
| **`PREDICTIVE_OPTIMIZATION` en tablas diminutas:** Facturó 0.25 DBU en tareas de compactación automáticas innecesarias para un dataset de 26 filas. | **Apagar:** Deshabilitar Predictive Optimization en el schema `gameday`: `ALTER SCHEMA gameday DISABLE PREDICTIVE OPTIMIZATION`. | Juancarlos (Comandante) | 2026-11-05 |
| **Ejecución con cuenta personal (`dfvaler@gmail.com`):** Imposibilita auditar y separar en facturación el costo de Actions del trabajo interactivo. | **Priorizar:** Crear un Service Principal exclusivo para GitHub Actions y asignarle token propio en los secrets. | Edgar (Operador) | 2026-11-07 |

---

### Bonus implementado:
En [`framework/deployment/deploy_silver_v2.sql`](file:///c:/Users/dvalentin/Downloads/Data%20Architecture/taller_sre_utec/framework/deployment/deploy_silver_v2.sql) se integró la sentencia `ALTER TABLE ... SET TAGS` para que en cada despliegue las tablas Gold nazcan tagueadas automáticamente, garantizando que el workflow de política de tags nunca falle.
