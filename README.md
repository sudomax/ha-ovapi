# 🇳🇱 Dutch Public Transport (OVapi) for Home Assistant

Real-time departures for buses, trams, metros, ferries, and regional trains across the Netherlands using [OVapi](http://v0.ovapi.nl) open data, built to be set up in seconds with zero maintenance.

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue.svg)
![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)

---

## ✨ What You Get

- **1-Step Setup**: Enter your stop's Haltenummer (TPC) and optionally filter by line number(s). Done.
- **3 Live Departure Sensors**: Automatically creates `Next Departure`, `Departure 2`, and `Departure 3` using Home Assistant's native `TIMESTAMP` device class (*"in 4 minutes"*), rounded to the minute to avoid GPS database spam.
- **1-Click Dashboard Summary**: Each sensor includes a ready-to-display `summary` attribute (e.g. `26 → IJburg` or `26 → IJburg (+3 min)`) alongside `line_number`, `destination`, `delay_minutes`, `platform`, and `status`.
- **Boardable Trips Only**: Automatically filters out passed vehicles and terminating/drop-off-only arrivals.
- **Built-In Smart Polling & Resilience**: Polls every 30s when a departure is within 30 minutes, slows down to 5 minutes when far away and 15 minutes overnight, and tolerates transient OVapi hiccups without dashboard flickering.

---

## 🔍 How to Find Your Stop Code (TPC)

Every Dutch transit stop pole has its **Haltenummer** (Timing Point Code — a 7 or 8-digit number, e.g. `30005029` for *Amsterdam, Centraal Station*):

1. **On the Physical Stop Sign**: Printed directly on the yellow/blue stop sign or shelter timetable next to the stop name. Notice each side of the street has its own code for its direction.
2. **Operator Timetables**: Listed on stop pages and PDF timetables from GVB, RET, HTM, Qbuzz, Connexxion, Arriva, and EBS.

---

## 🚀 Installation

### Option 1: Via HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots (top right) → **Custom repositories**.
3. Add `https://github.com/sudomax/ha-ovapi` with category **Integration**.
4. Download **Dutch Public Transport (OVapi)** and restart Home Assistant.

### Option 2: Manual Installation
1. Copy the `custom_components/ovapi` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

---

## ⚙️ Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Dutch Public Transport (OVapi)**.
3. Fill in the single setup screen:
   - **Timing Point Code (TPC)**: e.g. `30005029`
   - **Line number(s)** *(optional)*: Leave empty to track **all lines** at that stop, or enter one or more lines separated by commas (e.g. `26` or `7, 39`).
4. Click **Submit**.

---

## 📊 Dashboard & Automation Examples

### 1. Clean Tile Card (Visual Editor — No YAML Needed)
1. Add a **Tile** card to your dashboard and select `sensor.<your_stop>_next_departure`.
2. Under **State content**, select **State** and **Summary**.
3. Your card immediately displays: **`in 4 minutes · 26 → IJburg (+2 min)`**.

Equivalent YAML for all 3 upcoming departures:
```yaml
type: vertical-stack
cards:
  - type: tile
    entity: sensor.centraal_station_next_departure
    name: Next Departure
    state_content:
      - state
      - summary
  - type: tile
    entity: sensor.centraal_station_departure_2
    name: Departure 2
    state_content:
      - state
      - summary
  - type: tile
    entity: sensor.centraal_station_departure_3
    name: Departure 3
    state_content:
      - state
      - summary
```

### 2. "Time to Leave" Notification Automation
Use Home Assistant's built-in `offset` on `Next Departure` to get alerted when it's time to walk to the stop (e.g. 8 minutes before departure):

```yaml
alias: "Time to leave"
triggers:
  - trigger: time
    at: sensor.centraal_station_next_departure
    offset: "-00:08:00"
actions:
  - action: notify.notify
    data:
      title: "Time to leave!"
      message: >
        Leave now for {{ state_attr('sensor.centraal_station_next_departure', 'summary') }}.
```

---

## 🧪 Development

```bash
.venv/bin/pytest tests/ -v
.venv/bin/ruff check .
```
