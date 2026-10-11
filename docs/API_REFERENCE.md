# GridMind API v2 Reference Guide

Complete reference specification for GridMind's versioned HTTP API (`/v2`), deployed via Amazon API Gateway HTTP API v2.

---

## 1. Global Conventions & Standards

- **Base URL**:
  - **Live Deployed Endpoint**: `https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com`
  - **Local Development Proxy**: `http://localhost:5173/api`
- **Headers**:
  - `Content-Type: application/json`
  - `Cache-Control: no-store`
- **Body Size Limit**: Maximum 2,048 decoded UTF-8 bytes.
- **Time Representation**: Exactly 96 intervals of 15 minutes (`"00:00"` through `"23:45"`).
- **Physical Units**:
  - Voltage: per-unit (`p.u.`)
  - Temperature: degrees Celsius (`°C`)
  - Active Power: kilowatts (`kW`)
  - Loading: percentage of rated current (`%`)
  - Money: Indian Rupees (`INR`), integer amounts

---

## 2. API Endpoints

### 2.1 `GET /v2/health`
Verifies backend runtime health, memory caching, and engine module availability.

```bash
curl https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/health
```

**Response (HTTP 200)**:
```json
{
  "status": "healthy",
  "engine_version": "0.1.0",
  "supported_v2_operations": [
    "health",
    "scenarios",
    "network",
    "simulate",
    "assess",
    "impact",
    "hosting",
    "plan"
  ]
}
```

---

### 2.2 `GET /v2/scenarios`
Returns the enumerated input dimensions, defaults, and configuration parameter citations.

```bash
curl https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/scenarios
```

**Response (HTTP 200)**:
```json
{
  "engine_version": "0.1.0",
  "enums": {
    "ev_kw": [10, 30, 50, 100],
    "pv_kwp": [0, 10, 20, 30],
    "day_type": ["summer_weekday", "winter_weekday", "weekend"],
    "load_level": ["moderate", "heavy", "critical"],
    "bess": ["off", "auto"]
  },
  "defaults": {
    "ev_kw": 50,
    "pv_kwp": 30,
    "day_type": "summer_weekday",
    "load_level": "heavy",
    "bess": "off"
  }
}
```

---

### 2.3 `GET /v2/network`
Retrieves the 6-transformer neighbourhood topology (Model Colony, Sector 14) and candidate charging sites.

```bash
curl https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/network
```

---

### 2.4 `POST /v2/simulate`
Executes a 24-hour, 96-step coupled AC power flow and IEEE C57.91 thermal simulation for one transformer.

```bash
curl -X POST https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "ev_kw": 50,
    "pv_kwp": 30,
    "day_type": "summer_weekday",
    "load_level": "heavy"
  }'
```

**Response Highlights (HTTP 200)**:
```json
{
  "engine_version": "0.1.0",
  "verdict": "violations_found",
  "summary": {
    "min_voltage_pu": 0.9318,
    "min_voltage_time": "19:45",
    "max_hotspot_c": 134.2,
    "max_hotspot_time": "20:15",
    "max_loading_pct": 128.4,
    "daily_equivalent_aging_hours": 116.5,
    "estimated_insulation_life_years": 4.2
  },
  "alerts": [
    {
      "type": "low_voltage",
      "severity": "warning",
      "start_time": "18:30",
      "end_time": "21:15",
      "peak_value": 0.9318,
      "message": "Voltage below statutory limit 0.95 p.u."
    }
  ],
  "series": {
    "timestamps": ["00:00", "00:15", "..."],
    "voltage_pu": [0.9982, 0.9985, "..."],
    "loading_pct": [42.1, 41.8, "..."],
    "hotspot_temp_c": [72.4, 71.8, "..."],
    "top_oil_temp_c": [54.2, 53.8, "..."],
    "aging_factor": [0.08, 0.07, "..."]
  }
}
```

---

### 2.5 `POST /v2/assess`
Evaluates multi-transformer network loading and thermal states under a proposed site allocation.

```bash
curl -X POST https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/assess \
  -H "Content-Type: application/json" \
  -d '{"allocation": [{"site_id": "S1", "allocated_kw": 50}]}'
```

---

### 2.6 `POST /v2/impact`
Computes comparative reference-equivalent life consumption, rupee asset depreciation, and household voltage exposure hours.

```bash
curl -X POST https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/impact \
  -H "Content-Type: application/json" \
  -d '{"allocation": [{"site_id": "S1", "allocated_kw": 50}]}'
```

---

### 2.7 `POST /v2/hosting`
Calculates discrete EV hosting capacity headroom (uncontrolled and managed) across all 6 transformers.

```bash
curl -X POST https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/hosting \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### 2.8 `POST /v2/plan`
Determines optimal greedy footfall placement and remedy selection for a specified neighbourhood target charging capacity.

```bash
curl -X POST https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/plan \
  -H "Content-Type: application/json" \
  -d '{"target_kw": 300}'
```
