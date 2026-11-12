import os, math, httpx
from datetime import date, datetime, timedelta, timezone
from .crops_data import CROPS, find_crop, norm_soil, current_seasons, STAGES

UA = {"User-Agent": f"AgricultureThreatFusion/1.0 ({os.getenv('NOMINATIM_EMAIL', 'set-NOMINATIM_EMAIL')})"}
LEVELS = ["Low", "Medium", "High", "Critical"]


class NotConfigured(Exception):
    pass


async def _get(url, params=None, headers=None, timeout=25):
    async with httpx.AsyncClient(timeout=timeout, headers={**UA, **(headers or {})}) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


# ------------------------------------------------------------------ weather
WMO = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Light drizzle",
       53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain", 80: "Rain showers",
       81: "Rain showers", 82: "Violent showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}


async def get_weather(lat, lon):
    j = await _get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "auto", "past_days": 7, "forecast_days": 7,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,cloud_cover,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                 "et0_fao_evapotranspiration,wind_speed_10m_max,relative_humidity_2m_mean"})
    d = j["daily"]
    rows = [{"date": d["time"][i], "tmax": d["temperature_2m_max"][i], "tmin": d["temperature_2m_min"][i],
             "rain": d["precipitation_sum"][i] or 0, "rain_prob": d["precipitation_probability_max"][i],
             "et0": d["et0_fao_evapotranspiration"][i], "wind_max": d["wind_speed_10m_max"][i],
             "rh_mean": d["relative_humidity_2m_mean"][i]} for i in range(len(d["time"]))]
    c = j["current"]
    return {"source": "Open-Meteo", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "current": {"temp": c["temperature_2m"], "humidity": c["relative_humidity_2m"], "rain": c["precipitation"],
                        "wind": c["wind_speed_10m"], "cloud": c["cloud_cover"], "text": WMO.get(c["weather_code"], "—")},
            "history": rows[:7], "forecast": rows[7:]}


def weather_alerts(w):
    fc, hist, out = w["forecast"], w["history"], []
    rain_fc = sum(r["rain"] for r in fc)
    rain_hist = sum(r["rain"] for r in hist)
    if any(r["rain"] >= 115 for r in fc):
        out.append(dict(type="heavy_rain", level="Critical", title="Very heavy rainfall / flooding risk",
                        message="Forecast shows 115 mm or more rain in a day."))
    elif any(r["rain"] >= 64.5 for r in fc):
        out.append(dict(type="heavy_rain", level="High", title="Heavy rainfall expected",
                        message="Forecast shows 64.5 mm or more rain in a day (IMD 'heavy rain' threshold)."))
    if rain_fc < 5 and rain_hist < 5:
        out.append(dict(type="low_rain", level="Medium", title="Low rainfall / possible dry spell",
                        message=f"Only {rain_hist + rain_fc:.1f} mm in the last 7 + next 7 days."))
    if any((r["tmax"] or 0) >= 40 for r in fc):
        out.append(dict(type="heat", level="High", title="Heat stress risk", message="Maximum temperature of 40 °C or more forecast."))
    elif any((r["tmax"] or 0) >= 36 for r in fc):
        out.append(dict(type="heat", level="Medium", title="High temperature", message="Maximum temperature of 36 °C or more forecast."))
    if any((r["wind_max"] or 0) >= 40 for r in fc):
        out.append(dict(type="wind", level="Medium", title="Strong wind", message="Wind of 40 km/h or more forecast - risk of lodging and spray drift."))
    humid = [r for r in fc if (r["rh_mean"] or 0) >= 85 and 15 <= ((r["tmax"] or 0) + (r["tmin"] or 0)) / 2 <= 30 and r["rain"] >= 1]
    if len(humid) >= 3:
        out.append(dict(type="fungal", level="High" if len(humid) >= 5 else "Medium", title="Conditions favourable for fungal disease",
                        message=f"{len(humid)} of the next 7 days are warm, humid and wet (rule-based indicator, not a diagnosis)."))
    return out


# ------------------------------------------------------------------ geocoding
async def reverse_geocode(lat, lon):
    j = await _get("https://nominatim.openstreetmap.org/reverse",
                   {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 14, "addressdetails": 1})
    a = j.get("address", {})
    return {"state": a.get("state"), "district": a.get("state_district") or a.get("county"),
            "taluk": a.get("county") if a.get("state_district") else a.get("suburb"),
            "village": a.get("village") or a.get("hamlet") or a.get("town") or a.get("city") or a.get("suburb"),
            "display": j.get("display_name"), "note": "Auto-detected from OpenStreetMap - please correct if wrong."}


async def search_place(q):
    j = await _get("https://nominatim.openstreetmap.org/search", {"q": q, "format": "jsonv2", "limit": 6, "countrycodes": "in"})
    return [{"name": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in j]


# ------------------------------------------------------------------ water (FAO-56: ETc = ET0 x Kc)
IRR_EFF = {"Drip Irrigation": .9, "Sprinkler Irrigation": .75, "Furrow Irrigation": .6, "Flood Irrigation": .5,
           "Rainfed Farming": 0, "Other": .6}
DEPLETION_MM = {"sandy": 15, "loamy": 20, "red": 20, "laterite": 18, "black": 28, "clay": 30, "alluvial": 24, "silty": 24}


def area_m2(farm):
    a = farm.get("area") or 0
    return a * (4046.86 if (farm.get("unit") or "acres") == "acres" else 10000)


def kc_for(crop, stage):
    k = (crop["kc_ini"], crop["kc_mid"], crop["kc_end"])
    return {"Sowing / Germination": k[0], "Vegetative": (k[0] + k[1]) / 2, "Flowering": k[1],
            "Fruiting / Grain filling": k[1], "Maturity / Harvest": k[2]}.get(stage or "Vegetative", k[1])


def water_requirement(farm, w):
    crop = find_crop(farm.get("crop"))
    if not crop:
        return {"available": False, "reason": "Crop is not in the Kc reference table, so water need cannot be calculated."}
    if not farm.get("area"):
        return {"available": False, "reason": "Enter land area to calculate water volume."}
    kc = kc_for(crop, farm.get("stage"))
    fc = w["forecast"]
    etc = [(r["et0"] or 0) * kc for r in fc]
    eff_rain = [0.8 * r["rain"] for r in fc]           # rough effective-rainfall assumption
    wk_etc, wk_rain = sum(etc), sum(eff_rain)
    net = max(0.0, wk_etc - wk_rain)
    eff = IRR_EFF.get(farm.get("irrigation") or "Other", .6)
    gross = net / eff if eff else 0
    m2 = area_m2(farm)
    thr = DEPLETION_MM.get(norm_soil(farm.get("soil")), 20)
    bal, irr_date = 0.0, None
    for r, e, rn in zip(fc, etc, eff_rain):
        bal = max(0.0, bal + e - rn)
        if bal >= thr:
            irr_date = r["date"]; break
    daily = wk_etc / 7
    ratio = net / wk_etc if wk_etc else 0
    if eff == 0:   # rainfed: nothing can make up a rainfall deficit
        shortage = "High" if ratio > .5 else "Medium" if ratio > .3 else "Low"
    else:          # irrigated: need is met by irrigation, so only flag that irrigation is required
        shortage = "Medium" if ratio > .7 else "Low"
    rain7 = sum(r["rain"] for r in fc)
    excess = "High" if rain7 >= 100 else "Medium" if rain7 >= 50 else "Low"
    return {"available": True, "method": "Calculated estimate: FAO-56 ETc = ET0 x Kc (Open-Meteo ET0). Not a sensor measurement.",
            "kc": round(kc, 2), "etc_mm_day": round(daily, 2), "weekly_etc_mm": round(wk_etc, 1), "weekly_eff_rain_mm": round(wk_rain, 1),
            "weekly_net_irrigation_mm": round(net, 1), "weekly_gross_irrigation_mm": round(gross, 1),
            "daily_litres": round(daily * m2), "weekly_litres": round(wk_etc * m2),
            "weekly_irrigation_litres": round(gross * m2),
            "next_irrigation_date": irr_date if eff else None,
            "irrigation_note": ("Rainfed farm - no irrigation scheduled; monitor rainfall." if not eff else
                                f"Irrigate on {irr_date}." if irr_date else "No irrigation needed within the 7-day forecast window."),
            "frequency_days": max(1, round(thr / daily)) if daily else None,
            "shortage_risk": shortage, "excess_risk": excess,
            "sensor_soil_moisture": farm.get("soil_moisture"), "sensor_note": "Soil moisture shown is the farmer-entered value, if any."}


# ------------------------------------------------------------------ crop recommendation
async def climate_history(lat, lon):
    end = date.today() - timedelta(days=6)
    start = end - timedelta(days=364)
    j = await _get("https://archive-api.open-meteo.com/v1/archive", {
        "latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "temperature_2m_mean,precipitation_sum", "timezone": "auto"}, timeout=40)
    t = [x for x in j["daily"]["temperature_2m_mean"] if x is not None]
    r = [x or 0 for x in j["daily"]["precipitation_sum"]]
    return {"annual_rain_mm": round(sum(r)), "recent_mean_temp_c": round(sum(t[-60:]) / max(1, len(t[-60:])), 1),
            "annual_mean_temp_c": round(sum(t) / max(1, len(t)), 1),
            "source": "Open-Meteo historical (ERA5 reanalysis, modelled - not a rain-gauge record)"}


def _range_score(v, lo_abs, lo_opt, hi_opt, hi_abs):
    if lo_opt <= v <= hi_opt: return 1.0
    if v < lo_abs or v > hi_abs: return 0.0
    return (v - lo_abs) / (lo_opt - lo_abs) if v < lo_opt else (hi_abs - v) / (hi_abs - hi_opt)


def recommend_crops(clim, soil=None, ph=None, month=None):
    month = month or date.today().month
    seasons_now = current_seasons(month)
    res = []
    for c in CROPS:
        f, notes = {}, []
        f["temperature"] = _range_score(clim["recent_mean_temp_c"], c["tabs_lo"], c["topt_lo"], c["topt_hi"], c["tabs_hi"])
        notes.append(f"Recent mean temp {clim['recent_mean_temp_c']} °C vs optimum {c['topt_lo']}-{c['topt_hi']} °C.")
        R = clim["annual_rain_mm"]
        if R >= c["water_lo"]:
            f["water"] = 1.0 if R <= c["water_hi"] * 1.5 else .7
            notes.append(f"Last-12-month rainfall ~{R} mm vs crop need {c['water_lo']}-{c['water_hi']} mm.")
        else:
            f["water"] = max(0.2, R / c["water_lo"])
            notes.append(f"Rainfall ~{R} mm is below the ~{c['water_lo']} mm need - about {c['water_lo'] - R} mm irrigation required.")
        if "Any" in c["seasons"] or seasons_now & set(c["seasons"]):
            f["season"] = 1.0; notes.append("Can be sown in the current season.")
        else:
            f["season"] = .5; notes.append(f"Usual season: {', '.join(c['seasons'])} - not the current one.")
        if soil:
            ok = norm_soil(soil) in c["soils"]
            f["soil"] = 1.0 if ok else .4
            notes.append(f"{soil} is {'suitable' if ok else 'not among the best soils'} for this crop.")
        if ph:
            f["ph"] = _range_score(ph, c["ph_lo"] - 1.5, c["ph_lo"], c["ph_hi"], c["ph_hi"] + 1.5)
            notes.append(f"Soil pH {ph} vs preferred {c['ph_lo']}-{c['ph_hi']}.")
        W = {"temperature": .3, "water": .25, "season": .15, "soil": .2, "ph": .1}
        score = sum(f[k] * W[k] for k in f) / sum(W[k] for k in f)
        irrigation = "Drip or sprinkler" if R < c["water_lo"] else "Rain-fed possible; supplement if dry spells"
        res.append({"crop": c["name"], "score": round(score * 100), "factors": {k: round(v * 100) for k, v in f.items()},
                    "explanation": notes, "seasons": c["seasons"], "water_need_mm": f"{c['water_lo']}-{c['water_hi']}",
                    "duration_days": c["days"], "irrigation": irrigation, "good_soils": c["soils"],
                    "risks": ["Weather-based estimate only; local pests/disease pressure and market access not modelled."]})
    res.sort(key=lambda x: -x["score"])
    return {"results": [r for r in res if r["score"] >= 55],
            "data_used": ["Open-Meteo 12-month climate"] + (["Farmer-entered soil type"] if soil else []) + (["Farmer-entered pH"] if ph else []),
            "data_missing": ([] if soil else ["Soil type (not provided - soil suitability not scored)"]) +
                            ["Satellite NDVI / regional cultivation history are not used in this score"],
            "disclaimer": "Decision-support estimate from generic agronomic ranges. Confirm with your local KVK / agriculture officer."}


# ------------------------------------------------------------------ fertility (qualitative only, no doses)
def soil_fertility(farm):
    out = []
    def rate(v, lo, hi): return "Low" if v < lo else "Medium" if v <= hi else "High"
    if farm.get("soil_n") is not None: out.append(("Nitrogen", rate(farm["soil_n"], 280, 560)))
    if farm.get("soil_p") is not None: out.append(("Phosphorus", rate(farm["soil_p"], 10, 25)))
    if farm.get("soil_k") is not None: out.append(("Potassium", rate(farm["soil_k"], 110, 280)))
    notes = [{"nutrient": n, "rating": r, "advice": (f"{n} is low - plan to correct it; get the dose from your Soil Health Card / KVK."
                                                      if r == "Low" else f"{n} rated {r}.")} for n, r in out]
    if not notes: notes = [{"nutrient": "-", "rating": "Unknown", "advice": "No soil test values entered. A soil test is recommended before fertilising."}]
    return notes


# ------------------------------------------------------------------ markets
def haversine(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


async def nearby_markets(lat, lon, radius_km=50):
    q = f'[out:json][timeout:25];(node["amenity"="marketplace"](around:{radius_km * 1000},{lat},{lon});way["amenity"="marketplace"](around:{radius_km * 1000},{lat},{lon}););out center 30;'
    async with httpx.AsyncClient(timeout=40, headers=UA) as c:
        r = await c.post("https://overpass-api.de/api/interpreter", data={"data": q}); r.raise_for_status(); j = r.json()
    out = []
    for e in j.get("elements", []):
        la, lo = e.get("lat") or e.get("center", {}).get("lat"), e.get("lon") or e.get("center", {}).get("lon")
        if la is None: continue
        t = e.get("tags", {})
        out.append({"name": t.get("name") or "Unnamed marketplace", "lat": la, "lon": lo,
                    "address": ", ".join(x for x in [t.get("addr:street"), t.get("addr:city")] if x) or "—",
                    "distance_km": round(haversine(lat, lon, la, lo), 1)})
    out.sort(key=lambda x: x["distance_km"])
    return {"source": "OpenStreetMap (amenity=marketplace). Not a verified list of regulated mandis; trading information not available.",
            "markets": out}


AGMARK = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
PRICE_ALIAS = {"Soybean": "Soyabean", "Mustard": "Mustard", "Chilli": "Dry Chillies", "Cotton": "Cotton", "Ragi": "Ragi (Finger Millet)",
               "Jowar": "Jowar(Sorghum)", "Bajra": "Bajra(Pearl Millet/Cumbu)", "Rice": "Paddy(Dal)", "Brinjal": "Brinjal"}


async def market_prices(crop, state=None, district=None):
    key = os.getenv("DATA_GOV_API_KEY")
    if not key:
        raise NotConfigured("Market prices need a data.gov.in API key (DATA_GOV_API_KEY).")
    p = {"api-key": key, "format": "json", "limit": 100, "filters[commodity]": PRICE_ALIAS.get(crop, crop)}
    if state: p["filters[state]"] = state
    if district: p["filters[district]"] = district
    j = await _get(AGMARK, p)
    rows = [{"market": r.get("market"), "district": r.get("district"), "state": r.get("state"), "commodity": r.get("commodity"),
             "min": r.get("min_price"), "max": r.get("max_price"), "modal": r.get("modal_price"), "date": r.get("arrival_date")}
            for r in j.get("records", [])]
    return {"source": "Agmarknet via data.gov.in", "unit": "Rs per quintal", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "note": "Prices are the latest published by Agmarknet (usually previous trading day), not tick-by-tick live prices.",
            "rows": rows}


# ------------------------------------------------------------------ satellite NDVI (Sentinel Hub Statistical API)
EVAL = """//VERSION=3
function setup(){return{input:[{bands:["B04","B08","SCL","dataMask"]}],output:[{id:"ndvi",bands:1},{id:"dataMask",bands:1}]}}
function evaluatePixel(s){var ok=s.dataMask==1&&[4,5,6].indexOf(s.SCL)>=0;return{ndvi:[(s.B08-s.B04)/(s.B08+s.B04)],dataMask:[ok?1:0]}}"""


def ndvi_class(v):
    return "Healthy" if v >= .6 else "Moderate" if v >= .4 else "Stressed" if v >= .2 else "Poor"


async def ndvi_series(lat, lon, days=120):
    cid, sec = os.getenv("SENTINELHUB_CLIENT_ID"), os.getenv("SENTINELHUB_CLIENT_SECRET")
    if not (cid and sec):
        raise NotConfigured("Satellite monitoring needs Sentinel Hub credentials (SENTINELHUB_CLIENT_ID / SECRET).")
    async with httpx.AsyncClient(timeout=60) as c:
        t = await c.post("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
                         data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec})
        t.raise_for_status()
        d = 0.0035
        body = {"input": {"bounds": {"bbox": [lon - d, lat - d, lon + d, lat + d], "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                          "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 50}}]},
                "aggregation": {"timeRange": {"from": (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z"),
                                              "to": datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")},
                                "aggregationInterval": {"of": "P10D"}, "evalscript": EVAL, "resx": 0.0001, "resy": 0.0001},
                "calculations": {"default": {}}}
        r = await c.post("https://services.sentinel-hub.com/api/v1/statistics", json=body,
                         headers={"Authorization": "Bearer " + t.json()["access_token"]})
        r.raise_for_status()
    pts = []
    for x in r.json().get("data", []):
        st = x["outputs"]["ndvi"]["bands"]["B0"]["stats"]
        if st.get("sampleCount", 0) and st["sampleCount"] - st.get("noDataCount", 0) > 0 and st.get("mean") is not None:
            pts.append({"from": x["interval"]["from"][:10], "to": x["interval"]["to"][:10], "ndvi": round(st["mean"], 3),
                        "class": ndvi_class(st["mean"])})
    if not pts:
        return {"source": "Sentinel-2 L2A via Sentinel Hub", "series": [], "latest": None,
                "limitation": "No cloud-free Sentinel-2 observations in this period over the farm. Try again later."}
    return {"source": "Sentinel-2 L2A via Sentinel Hub (10-day mean NDVI of cloud-free pixels in ~700 m box)", "series": pts, "latest": pts[-1],
            "note": "NDVI thresholds are general; healthy values differ by crop and growth stage. Imagery preview is not included."}


# ------------------------------------------------------------------ threat fusion
THREAT_INFO = {
    "heavy_rain": ("Waterlogging, lodging, nutrient leaching, disease spread", "Open drainage channels; avoid fertiliser/spray before rain", "Clear field drains and delay irrigation/fertiliser application."),
    "low_rain": ("Moisture stress and yield loss", "Mulching, timely irrigation, drought-tolerant practices", "Plan irrigation using the water-requirement estimate."),
    "heat": ("Flower/fruit drop, wilting, reduced yield", "Mulch, irrigate in the evening, avoid transplanting in peak heat", "Irrigate lightly in cool hours; avoid stress operations."),
    "wind": ("Lodging, mechanical damage, spray drift", "Staking/windbreaks", "Postpone spraying; support tall crops."),
    "fungal": ("Blight, mildew, leaf-spot outbreaks", "Good spacing/airflow, avoid overhead irrigation, scout fields", "Scout fields daily; upload suspicious leaves in Disease Detection; consult KVK before spraying."),
}


def build_threats(farm, w=None, water=None, sat=None, last_disease=None):
    T = []
    def add(name, level, source, evidence, impact, prevent, action):
        T.append(dict(threat=name, level=level, crop=farm.get("crop"), stage=farm.get("stage"), source=source,
                      evidence=evidence, impact=impact, prevention=prevent, action=action))
    if w:
        for a in weather_alerts(w):
            i = THREAT_INFO[a["type"]]
            add(a["title"], a["level"], "Weather forecast (Open-Meteo)", a["message"], *i)
    if water and water.get("available"):
        if water["shortage_risk"] in ("Medium", "High"):
            add("Water shortage", water["shortage_risk"], "Water-requirement calculation (FAO-56)",
                f"Net weekly irrigation need ~{water['weekly_net_irrigation_mm']} mm after forecast rain.",
                "Moisture stress, lower yield", "Schedule irrigation to the estimate", water["irrigation_note"])
        if water["excess_risk"] in ("Medium", "High"):
            add("Excess rainfall", water["excess_risk"], "Weather forecast", f"Forecast rain this week: {water['weekly_eff_rain_mm']} mm effective.",
                *THREAT_INFO["heavy_rain"])
    if sat and sat.get("latest") and sat["latest"]["class"] in ("Stressed", "Poor"):
        add("Poor vegetation", "High" if sat["latest"]["class"] == "Poor" else "Medium", "Sentinel-2 NDVI",
            f"NDVI {sat['latest']['ndvi']} ({sat['latest']['class']}) for {sat['latest']['from']}-{sat['latest']['to']}.",
            "Reduced growth and yield", "Check irrigation, nutrition, pests", "Walk the field to find the cause of low vegetation.")
    if sat and len(sat.get("series", [])) >= 2:
        a, b = sat["series"][-2]["ndvi"], sat["series"][-1]["ndvi"]
        if a - b >= .1:
            add("Vegetation decline", "Medium", "Sentinel-2 NDVI", f"NDVI fell from {a} to {b} between consecutive periods.",
                "Possible stress, harvest or disease", "Scout field", "Compare with growth stage; inspect for stress.")
    if last_disease and last_disease.get("confident") and not last_disease.get("healthy"):
        add("Crop disease: " + last_disease["disease"], "High" if last_disease["confidence"] >= .9 else "Medium", "AI disease detection (image)",
            f"Model confidence {round(last_disease['confidence'] * 100)}% on {last_disease.get('date', '')}. AI result, not a confirmed diagnosis.",
            "Yield and quality loss", "Sanitation, resistant varieties, rotation", "Confirm with an agriculture expert before treatment.")
    for n in soil_fertility(farm):
        if n["rating"] == "Low":
            add("Nutrient deficiency risk: " + n["nutrient"], "Medium", "Farmer-entered soil test", n["advice"],
                "Poor growth and yield", "Balanced fertilisation based on soil test", "Get dose from Soil Health Card / KVK.")
    if any(t["level"] in ("High", "Critical") for t in T):
        add("Reduced crop yield", "Medium", "Combined analysis", "One or more High/Critical threats are active.",
            "Lower yield / quality", "Address the high-level threats first", "Act on threats listed above.")
    T.sort(key=lambda t: -LEVELS.index(t["level"]))
    return T
