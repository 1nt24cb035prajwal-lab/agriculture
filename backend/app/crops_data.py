"""Approximate agronomic reference table (FAO-56 Kc values and EcoCrop/ICAR-style climate ranges).
These are generic reference ranges, NOT local recommendations - verify with your local KVK / agri officer.
Admins can edit this file to refine or add crops."""
KEYS = ["name", "kc_ini", "kc_mid", "kc_end", "topt_lo", "topt_hi", "tabs_lo", "tabs_hi", "water_lo", "water_hi",
        "seasons", "soils", "days", "ph_lo", "ph_hi"]
_RAW = [
    ("Rice", 1.05, 1.2, 0.9, 22, 32, 15, 38, 900, 2000, ["Kharif"], ["alluvial", "clay", "loamy", "silty"], 120, 5.5, 7.0),
    ("Wheat", 0.3, 1.15, 0.4, 15, 24, 5, 32, 450, 650, ["Rabi"], ["loamy", "alluvial", "clay", "black"], 130, 6.0, 7.5),
    ("Maize", 0.3, 1.2, 0.6, 20, 30, 10, 35, 500, 800, ["Kharif", "Rabi", "Zaid"], ["loamy", "red", "alluvial", "sandy"], 100, 5.8, 7.5),
    ("Ragi", 0.3, 1.0, 0.3, 20, 30, 12, 35, 300, 500, ["Kharif", "Summer"], ["red", "loamy", "sandy", "laterite"], 110, 5.0, 7.5),
    ("Jowar", 0.3, 1.0, 0.55, 25, 32, 15, 40, 350, 600, ["Kharif", "Rabi"], ["black", "red", "loamy"], 110, 6.0, 8.0),
    ("Bajra", 0.3, 1.0, 0.3, 25, 35, 15, 42, 250, 500, ["Kharif", "Summer"], ["sandy", "loamy", "red"], 85, 6.0, 8.0),
    ("Sugarcane", 0.4, 1.25, 0.75, 24, 32, 15, 38, 1500, 2500, ["Any"], ["loamy", "black", "alluvial", "clay"], 330, 6.0, 8.0),
    ("Cotton", 0.35, 1.15, 0.7, 22, 32, 15, 40, 700, 1300, ["Kharif"], ["black", "loamy", "alluvial"], 170, 6.0, 8.0),
    ("Groundnut", 0.4, 1.15, 0.6, 22, 30, 15, 35, 500, 700, ["Kharif", "Rabi", "Summer"], ["sandy", "red", "loamy"], 110, 6.0, 7.0),
    ("Soybean", 0.4, 1.15, 0.5, 20, 30, 10, 35, 450, 700, ["Kharif"], ["black", "loamy", "red"], 100, 6.0, 7.5),
    ("Sunflower", 0.35, 1.0, 0.35, 20, 28, 10, 35, 350, 600, ["Kharif", "Rabi", "Summer"], ["loamy", "black", "red"], 95, 6.0, 7.5),
    ("Mustard", 0.35, 1.15, 0.35, 15, 25, 8, 32, 250, 400, ["Rabi"], ["loamy", "alluvial", "sandy"], 120, 6.0, 7.5),
    ("Tomato", 0.6, 1.15, 0.8, 20, 27, 10, 35, 400, 800, ["Kharif", "Rabi", "Summer"], ["loamy", "red", "sandy"], 120, 6.0, 7.0),
    ("Potato", 0.5, 1.15, 0.75, 15, 22, 7, 30, 500, 700, ["Rabi"], ["loamy", "sandy", "alluvial"], 100, 5.0, 6.5),
    ("Onion", 0.7, 1.05, 0.75, 15, 25, 8, 32, 350, 550, ["Rabi", "Kharif"], ["loamy", "red", "black"], 130, 6.0, 7.5),
    ("Chilli", 0.6, 1.05, 0.9, 20, 30, 12, 35, 600, 1250, ["Kharif", "Rabi"], ["loamy", "red", "black"], 150, 6.0, 7.0),
    ("Brinjal", 0.6, 1.05, 0.9, 22, 30, 12, 35, 600, 800, ["Kharif", "Rabi", "Summer"], ["loamy", "red", "sandy"], 140, 5.5, 6.8),
    ("Cabbage", 0.7, 1.05, 0.95, 15, 22, 5, 30, 380, 500, ["Rabi"], ["loamy", "alluvial", "clay"], 90, 6.0, 7.0),
    ("Cauliflower", 0.7, 1.05, 0.95, 15, 22, 5, 30, 380, 500, ["Rabi"], ["loamy", "alluvial", "clay"], 100, 6.0, 7.0),
    ("Banana", 0.5, 1.1, 1.0, 24, 32, 15, 38, 1200, 2200, ["Any"], ["loamy", "alluvial", "black"], 330, 6.0, 7.5),
    ("Coconut", 0.95, 1.0, 1.0, 24, 32, 18, 38, 1200, 2500, ["Any"], ["laterite", "sandy", "loamy", "red", "alluvial"], 365, 5.2, 8.0),
    ("Arecanut", 0.9, 1.0, 1.0, 24, 30, 14, 36, 1750, 3000, ["Any"], ["laterite", "red", "loamy"], 365, 5.0, 6.5),
    ("Mango", 0.55, 1.0, 0.8, 24, 32, 15, 42, 750, 2500, ["Any"], ["loamy", "laterite", "red", "alluvial"], 365, 5.5, 7.5),
    ("Grapes", 0.3, 0.85, 0.45, 20, 30, 10, 40, 500, 900, ["Any"], ["loamy", "red", "sandy", "black"], 365, 5.5, 7.0),
]
CROPS = [dict(zip(KEYS, r)) for r in _RAW]
CROP_BY_NAME = {c["name"].lower(): c for c in CROPS}
ALIASES = {"soyabean": "soybean", "paddy": "rice", "finger millet": "ragi", "sorghum": "jowar", "pearl millet": "bajra",
           "peanut": "groundnut", "chili": "chilli", "eggplant": "brinjal", "corn": "maize", "areca nut": "arecanut"}
STAGES = ["Sowing / Germination", "Vegetative", "Flowering", "Fruiting / Grain filling", "Maturity / Harvest"]


def find_crop(name):
    n = (name or "").strip().lower()
    return CROP_BY_NAME.get(ALIASES.get(n, n))


def norm_soil(s):
    return (s or "").lower().replace("soil", "").strip()


def current_seasons(month: int):
    s = set()
    if 6 <= month <= 10: s.add("Kharif")
    if month >= 11 or month <= 3: s.add("Rabi")
    if 3 <= month <= 6: s |= {"Summer", "Zaid"}
    return s


def suggest_seasons(crop_name):
    c = find_crop(crop_name)
    return c["seasons"] if c else []
