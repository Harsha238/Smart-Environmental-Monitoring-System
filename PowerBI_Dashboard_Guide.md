# Power BI Dashboard Setup Guide
### Smart Environmental Monitoring & Analysis System

This guide walks through building a 3-page Power BI dashboard on top of the
project's MySQL database (or the REST API / sample_data.csv as alternatives).

---

## 1. Connect Power BI to your data source

You have **three options** -- pick whichever is easiest for your environment.

### Option A: Connect directly to MySQL (recommended)
1. Install the **MySQL Connector/NET** (required by Power BI to talk to MySQL):
   https://dev.mysql.com/downloads/connector/net/
2. Open **Power BI Desktop** → `Home` → `Get Data` → `More...`
3. Search for **MySQL database** → `Connect`
4. Server: `localhost:3306` (or your DB host) | Database: `smart_env_monitoring`
5. Choose **DirectQuery** (live, always up to date) or **Import** (faster, snapshot)
6. Enter your MySQL username/password → `Connect`
7. In the Navigator, select the tables: `sensor_readings`, `alerts`, `daily_analytics`
8. Click **Transform Data** to open Power Query if you need to rename/clean
   columns, otherwise click **Load**.

### Option B: Connect via the Flask REST API (Web connector)
1. `Get Data` → `Web`
2. URL: `http://localhost:5000/api/readings/history?limit=10000`
3. Power BI receives JSON → click **Into Table** → expand the `data` column
   → expand all sub-columns (temperature, humidity, aqi, recorded_at)
4. Repeat for `http://localhost:5000/api/analytics/anomalies?limit=200` to
   pull the alerts table.

### Option C: Import sample_data.csv directly (offline/demo mode)
1. `Get Data` → `Text/CSV` → select `sample_data.csv` → `Load`
2. Use Power Query (`Transform Data`) to set `timestamp` to Date/Time type.

> For this guide, the imported table is referred to as **sensor_readings**
> with columns: `device_id, temperature, humidity, aqi, recorded_at` (or
> `timestamp` if using the CSV).

---

## 2. Create a Date table and relationships

1. `Modeling` tab → `New Table` → paste:
   ```
   DateTable = CALENDAR(MIN(sensor_readings[recorded_at]), MAX(sensor_readings[recorded_at]))
   ```
2. On `DateTable`, add calculated columns:
   ```
   Day = FORMAT(DateTable[Date], "YYYY-MM-DD")
   Hour = HOUR(DateTable[Date])
   DayOfWeek = FORMAT(DateTable[Date], "ddd")
   ```
3. `Model` view → drag `DateTable[Date]` onto `sensor_readings[recorded_at]`
   to create a relationship (1-to-many).

---

## 3. Create the core DAX measures

Go to `Modeling` → `New Measure` and add each of these (also saved in
`powerbi/dax_measures.txt`):

```DAX
Avg Temperature   = ROUND(AVERAGE(sensor_readings[temperature]), 1)
Avg Humidity      = ROUND(AVERAGE(sensor_readings[humidity]), 1)
Avg AQI           = ROUND(AVERAGE(sensor_readings[aqi]), 1)
Max Temperature   = MAX(sensor_readings[temperature])
Min Temperature   = MIN(sensor_readings[temperature])
Total Readings    = COUNTROWS(sensor_readings)
Poor AQI Count    = CALCULATE(COUNTROWS(sensor_readings), sensor_readings[aqi] >= 150)
High Temp Count   = CALCULATE(COUNTROWS(sensor_readings), sensor_readings[temperature] >= 38)

Environmental Health Score =
VAR AqiScore = MAX(0, 100 - (AVERAGE(sensor_readings[aqi]) / 5))
VAR TempScore =
    IF(AVERAGE(sensor_readings[temperature]) >= 20 && AVERAGE(sensor_readings[temperature]) <= 26,
       100,
       MAX(0, 100 - (ABS(AVERAGE(sensor_readings[temperature]) - 23) * 6.67)))
VAR HumidityScore =
    IF(AVERAGE(sensor_readings[humidity]) >= 40 && AVERAGE(sensor_readings[humidity]) <= 60,
       100,
       MAX(0, 100 - (ABS(AVERAGE(sensor_readings[humidity]) - 50) * 2.5)))
RETURN ROUND(0.5 * AqiScore + 0.3 * TempScore + 0.2 * HumidityScore, 1)

AQI Trend (7-day slope) =
VAR Recent = AVERAGEX(FILTER(sensor_readings, sensor_readings[recorded_at] >= TODAY()-7), sensor_readings[aqi])
VAR Previous = AVERAGEX(FILTER(sensor_readings, sensor_readings[recorded_at] < TODAY()-7 && sensor_readings[recorded_at] >= TODAY()-14), sensor_readings[aqi])
RETURN Recent - Previous
```

---

## 4. PAGE 1 -- Executive Overview (KPI Cards)

1. Add a new page, rename it **"Overview"**.
2. Insert a **Card** visual (`Insert` → `Visual` → `Card`) for each KPI:
   - Card 1 → Field: `Avg Temperature` measure → format suffix `"°C"`
   - Card 2 → Field: `Avg Humidity` measure → format suffix `"%"`
   - Card 3 → Field: `Avg AQI` measure
   - Card 4 (optional 4th KPI) → Field: `Environmental Health Score`
3. Arrange the 3-4 cards in a horizontal row at the top of the page.
4. Add a **Slicer** visual bound to `DateTable[Date]` so users can filter
   the whole page by date range.
5. Style: `Format` pane → set a consistent accent color (e.g. teal #2E86AB
   for good readings, red #E63946 reserved for alert-related visuals later).
6. Add a **Multi-row card** below showing `Max Temperature`, `Min Temperature`,
   `Total Readings`, and `Poor AQI Count` for quick context.

---

## 5. PAGE 2 -- Trend Analysis (Line Charts)

1. Add a new page, rename it **"Trends"**.
2. **AQI Trend Line Chart**
   - Visual: `Line chart`
   - X-axis: `DateTable[Date]` (or `recorded_at` at Hour granularity)
   - Y-axis: `Avg AQI`
   - Add a reference line at y=150 (Format → Y-axis → Add a constant line,
     label "Unhealthy threshold", color red) to visually flag pollution events.
3. **Temperature Trend Chart**
   - Visual: `Line chart`, X-axis: `Date`, Y-axis: `Avg Temperature`
   - Add constant line at y=38 labeled "High temp alert".
4. **Humidity Trend Chart**
   - Visual: `Line chart`, X-axis: `Date`, Y-axis: `Avg Humidity`
5. Arrange the three charts stacked vertically or in a 2x2 grid (leave one
   cell for a small KPI card recap).
6. Add a **Slicer** for `device_id` if you have multiple ESP32 nodes.

---

## 6. PAGE 3 -- Environmental Health & Alerts

1. Add a new page, rename it **"Health & Alerts"**.
2. **Heatmap (Hour × Day AQI matrix)**
   - Visual: `Matrix` (or install the **"Calendar Heatmap"** / **"HeatMap"**
     custom visual from AppSource for a true color-graded grid)
   - Rows: `DateTable[Day]` | Columns: `Hour` (0-23) | Values: `Avg AQI`
   - `Format` → `Conditional formatting` → `Background color` on the Values
     field → color scale: green (low AQI) → yellow → red (high AQI)
3. **Environmental Score Gauge**
   - Visual: `Gauge`
   - Value: `Environmental Health Score`
   - Min: 0, Max: 100, Target: 80
   - Color bands (Format → Color rules): 0-39 red, 40-59 orange,
     60-79 yellow, 80-100 green
4. **Alert Table**
   - Visual: `Table`
   - Fields: `alerts[created_at]`, `alerts[alert_type]`, `alerts[severity]`,
     `alerts[message]`, joined reading's `temperature`/`humidity`/`aqi`
   - Sort descending by `created_at`
   - Conditional formatting on `severity`: CRITICAL=red, HIGH=orange,
     MODERATE=yellow, LOW=gray (Format → Conditional formatting → Background
     color → Rules)
5. Add a **Card** showing `High Temp Count` and `Poor AQI Count` next to the gauge.

---

## 7. Final touches

- `View` → `Themes` → apply a custom theme (or import `powerbi/theme.json`
  if you create one) for consistent branding across all 3 pages.
- `File` → `Options and settings` → `Data source settings` → set up a
  **Scheduled Refresh** (if publishing to the Power BI Service) so the
  dashboard automatically reflects new ESP32 readings, e.g. every 15 minutes.
- Add page navigation buttons (`Insert` → `Buttons` → `Back`/`Page navigation`)
  for a polished click-through experience between Overview → Trends → Health & Alerts.
- Publish: `Home` → `Publish` → select your workspace.

---

## Expected Visual Result (description, since live screenshots require Power BI Desktop)

- **Page 1**: A clean top strip of 3-4 large KPI cards (Avg Temp, Avg Humidity,
  Avg AQI, Health Score) in teal/blue tones, with a date slicer top-right.
- **Page 2**: Three stacked line charts showing AQI/Temperature/Humidity over
  the 14-day sample period, with visible spikes around the simulated heatwave
  and pollution events, each with a red threshold reference line.
- **Page 3**: A green-to-red gradient heatmap grid (days × hours) showing when
  pollution peaks occur, a circular gauge needle pointing to the current health
  score, and a color-coded alert table listing every HIGH_TEMPERATURE /
  POOR_AIR_QUALITY event raised by `analytics.py`.
