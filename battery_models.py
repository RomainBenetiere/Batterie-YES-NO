# battery_models.py
# Ce module contient les spécifications des modèles de batteries et les paramètres tarifaires par défaut.

BATTERY_MODELS = {
    "Tesla Powerwall 2": {
        "name": "Tesla Powerwall 2",
        "capacity_kwh": 13.5,
        "dod_percent": 100.0,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "round_trip_efficiency": 90.0,
        "inverter_efficiency": 97.5,
        "annual_degradation_percent": 2.0,
        "install_cost_eur": 9500.0,
        "warranty_years": 10
    },
    "Enphase IQ Battery 5P": {
        "name": "Enphase IQ Battery 5P",
        "capacity_kwh": 5.0,
        "dod_percent": 100.0,
        "max_charge_kw": 3.84,
        "max_discharge_kw": 3.84,
        "round_trip_efficiency": 96.0,
        "inverter_efficiency": 97.0,
        "annual_degradation_percent": 2.0,
        "install_cost_eur": 6500.0,
        "warranty_years": 15
    },
    "LG Chem RESU 10H": {
        "name": "LG Chem RESU 10H",
        "capacity_kwh": 9.8,
        "dod_percent": 95.0,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "round_trip_efficiency": 95.0,
        "inverter_efficiency": 97.0,
        "annual_degradation_percent": 2.0,
        "install_cost_eur": 7500.0,
        "warranty_years": 10
    },
    "BYD Battery-Box HVM 11.0": {
        "name": "BYD Battery-Box HVM 11.0",
        "capacity_kwh": 11.04,
        "dod_percent": 96.0,
        "max_charge_kw": 5.12,
        "max_discharge_kw": 5.12,
        "round_trip_efficiency": 95.5,
        "inverter_efficiency": 97.5,
        "annual_degradation_percent": 1.8,
        "install_cost_eur": 8000.0,
        "warranty_years": 10
    },
    "Huawei LUNA2000-10": {
        "name": "Huawei LUNA2000-10",
        "capacity_kwh": 10.0,
        "dod_percent": 100.0,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "round_trip_efficiency": 97.0,
        "inverter_efficiency": 98.0,
        "annual_degradation_percent": 1.5,
        "install_cost_eur": 7000.0,
        "warranty_years": 10
    }
}

DEFAULT_TARIFF_PARAMS = {
    "hp_price": 0.2516,
    "hc_price": 0.2068,
    "hc_start_1": 22,
    "hc_end_1": 6,
    "hc_start_2": 12,
    "hc_end_2": 14,
    "sell_price": 0.1300,
    "annual_elec_increase": 0.04,
    "contract_duration": 20,
    "post_contract_sell_price": 0.04,
    "discount_rate": 0.03,
    "projection_years": 20
}

def get_model_names() -> list[str]:
    """
    Retourne la liste des noms des modèles de batterie disponibles, 
    avec l'option 'Personnalisée' à la fin.
    """
    return list(BATTERY_MODELS.keys()) + ["Personnalisée"]

def get_default_params() -> dict:
    """
    Retourne les paramètres par défaut pour une batterie personnalisée.
    Basés sur une moyenne représentative.
    """
    return {
        "name": "Personnalisée",
        "capacity_kwh": 10.0,
        "dod_percent": 95.0,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "round_trip_efficiency": 95.0,
        "inverter_efficiency": 97.0,
        "annual_degradation_percent": 2.0,
        "install_cost_eur": 8000.0,
        "warranty_years": 10
    }
