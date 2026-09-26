# battery_simulation.py
# Moteur de simulation physique de la batterie — Itération temporelle pas-à-pas
# Simule les cycles de charge/décharge et calcule les flux d'énergie avec et sans batterie.

import pandas as pd
import numpy as np


def is_off_peak(hour: float, hc_start_1: float, hc_end_1: float,
                hc_start_2: float, hc_end_2: float) -> bool:
    """
    Détermine si une heure donnée est en heures creuses (HC).
    Gère les plages horaires qui traversent minuit (ex: 22h - 6h).
    """
    def in_range(h, start, end):
        if start is None or end is None:
            return False
        if start < end:
            return start <= h < end
        else:  # traverse minuit
            return h >= start or h < end

    return in_range(hour, hc_start_1, hc_end_1) or in_range(hour, hc_start_2, hc_end_2)


def _vectorized_off_peak(hours: np.ndarray, hc_s1, hc_e1, hc_s2, hc_e2) -> np.ndarray:
    """Version vectorisée de is_off_peak pour toutes les heures d'un coup."""
    def in_range_vec(h, start, end):
        if start is None or end is None:
            return np.zeros(len(h), dtype=bool)
        if start < end:
            return (h >= start) & (h < end)
        else:
            return (h >= start) | (h < end)

    return in_range_vec(hours, hc_s1, hc_e1) | in_range_vec(hours, hc_s2, hc_e2)


def simulate_battery(df: pd.DataFrame, battery_params: dict, tariff_params: dict) -> pd.DataFrame:
    """
    Moteur de simulation physique de la batterie pas-à-pas.
    
    Paramètres:
    -----------
    df : DataFrame avec colonnes 'timestamp' et 'Consommation nette de puissance actuelle' (kW)
         Valeurs négatives = surplus solaire, positives = consommation réseau
    battery_params : dict avec capacity_kwh, dod_percent, max_charge_kw, max_discharge_kw,
                     round_trip_efficiency (0-1), inverter_efficiency (0-1)
    tariff_params : dict avec hc_start_1, hc_end_1, hc_start_2, hc_end_2
    
    Retourne:
    ---------
    DataFrame enrichi avec colonnes: soc, grid_buy_with_batt, grid_sell_with_batt,
    grid_buy_no_batt, grid_sell_no_batt, tariff_type
    """
    res_df = df.copy()
    n = len(res_df)

    # Détection du pas de temps
    timestamps = pd.to_datetime(res_df['timestamp'])
    diffs = timestamps.diff().dt.total_seconds().dropna()
    timestep_hours = diffs.median() / 3600.0 if not diffs.empty else 1.0

    # Paramètres batterie
    capacity_kwh = battery_params.get('capacity_kwh', 10.0)
    dod_percent = battery_params.get('dod_percent', 100.0)
    max_charge_kw = battery_params.get('max_charge_kw', 5.0)
    max_discharge_kw = battery_params.get('max_discharge_kw', 5.0)
    round_trip_efficiency = battery_params.get('round_trip_efficiency', 0.95)
    inverter_efficiency = battery_params.get('inverter_efficiency', 0.97)

    usable_capacity = capacity_kwh * (dod_percent / 100.0)

    # Répartition symétrique des pertes round-trip entre charge et décharge
    charge_eff = np.sqrt(round_trip_efficiency)
    discharge_eff = np.sqrt(round_trip_efficiency)

    # Rendement total de la chaîne
    eff_charge_total = inverter_efficiency * charge_eff    # AC → DC (entrée batterie)
    eff_discharge_total = inverter_efficiency * discharge_eff  # DC → AC (sortie batterie)

    # Pré-calcul vectoriel des heures et tarifs
    hours = (timestamps.dt.hour + timestamps.dt.minute / 60.0).values.astype(float)
    hc_s1 = tariff_params.get('hc_start_1')
    hc_e1 = tariff_params.get('hc_end_1')
    hc_s2 = tariff_params.get('hc_start_2')
    hc_e2 = tariff_params.get('hc_end_2')
    is_hc_arr = _vectorized_off_peak(hours, hc_s1, hc_e1, hc_s2, hc_e2)

    # Données de puissance nette (kW)
    net_power = res_df['Consommation nette de puissance actuelle'].values.astype(float)

    # Pré-allocation des tableaux de résultats
    soc_arr = np.zeros(n)
    buy_batt = np.zeros(n)
    sell_batt = np.zeros(n)
    buy_nobatt = np.zeros(n)
    sell_nobatt = np.zeros(n)

    # ─── Scénario SANS BATTERIE (entièrement vectoriel) ───
    net_energy = net_power * timestep_hours  # kWh par pas de temps
    surplus_mask = net_power < 0
    deficit_mask = net_power > 0
    buy_nobatt[deficit_mask] = net_energy[deficit_mask]
    sell_nobatt[surplus_mask] = np.abs(net_energy[surplus_mask])

    # ─── Scénario AVEC BATTERIE (itération séquentielle sur le SoC) ───
    soc = usable_capacity * 0.5  # Démarrer à 50% de charge

    for i in range(n):
        p = net_power[i]
        e = p * timestep_hours

        if p < 0:
            # ── SURPLUS → CHARGE de la batterie ──
            available_surplus_kw = abs(p)
            charge_power = min(available_surplus_kw, max_charge_kw)
            charge_energy_ac = charge_power * timestep_hours

            # Énergie effectivement stockée (après pertes onduleur + charge)
            charge_stored = charge_energy_ac * eff_charge_total
            # Limiter par la capacité restante
            actual_stored = min(charge_stored, usable_capacity - soc)

            # Énergie AC réellement consommée pour cette charge
            actual_ac_used = actual_stored / eff_charge_total if eff_charge_total > 0 else 0.0

            # Surplus restant injecté sur le réseau
            remaining_surplus = abs(e) - actual_ac_used
            sell_batt[i] = max(0.0, remaining_surplus)
            soc += actual_stored

        elif p > 0:
            # ── DÉFICIT → DÉCHARGE de la batterie ──
            needed_kw = p
            discharge_power = min(needed_kw, max_discharge_kw)
            discharge_ac_needed = discharge_power * timestep_hours

            # Énergie à prélever de la batterie pour fournir cette puissance AC
            discharge_from_batt = discharge_ac_needed / eff_discharge_total if eff_discharge_total > 0 else 0.0
            # Limiter par le SoC disponible
            actual_from_batt = min(discharge_from_batt, soc)

            # Énergie AC effectivement délivrée au foyer
            actual_ac_delivered = actual_from_batt * eff_discharge_total

            # Déficit restant acheté au réseau
            remaining_deficit = e - actual_ac_delivered
            buy_batt[i] = max(0.0, remaining_deficit)
            soc -= actual_from_batt

        soc_arr[i] = soc

    # Ajout des résultats au DataFrame
    res_df['soc'] = soc_arr
    res_df['grid_buy_with_batt'] = buy_batt
    res_df['grid_sell_with_batt'] = sell_batt
    res_df['grid_buy_no_batt'] = buy_nobatt
    res_df['grid_sell_no_batt'] = sell_nobatt
    res_df['tariff_type'] = np.where(is_hc_arr, 'HC', 'HP')

    return res_df


def compute_annual_summary(sim_df: pd.DataFrame, tariff_params: dict) -> dict:
    """
    Calcule le résumé annuel à partir des données simulées.
    Retourne un dictionnaire avec les totaux d'énergie, coûts, revenus et économies.
    """
    hp_price = tariff_params.get('hp_price', 0.25)
    hc_price = tariff_params.get('hc_price', 0.20)
    sell_price = tariff_params.get('sell_price', 0.10)

    # Masques HP/HC
    hp_mask = sim_df['tariff_type'] == 'HP'
    hc_mask = sim_df['tariff_type'] == 'HC'

    # Totaux sans batterie
    tot_buy_no_batt = sim_df['grid_buy_no_batt'].sum()
    tot_sell_no_batt = sim_df['grid_sell_no_batt'].sum()

    cost_no_batt_hp = sim_df.loc[hp_mask, 'grid_buy_no_batt'].sum() * hp_price
    cost_no_batt_hc = sim_df.loc[hc_mask, 'grid_buy_no_batt'].sum() * hc_price
    cost_no_batt = cost_no_batt_hp + cost_no_batt_hc
    rev_sell_no_batt = tot_sell_no_batt * sell_price

    # Totaux avec batterie
    tot_buy_batt = sim_df['grid_buy_with_batt'].sum()
    tot_sell_batt = sim_df['grid_sell_with_batt'].sum()

    cost_batt_hp = sim_df.loc[hp_mask, 'grid_buy_with_batt'].sum() * hp_price
    cost_batt_hc = sim_df.loc[hc_mask, 'grid_buy_with_batt'].sum() * hc_price
    cost_with_batt = cost_batt_hp + cost_batt_hc
    rev_sell_with_batt = tot_sell_batt * sell_price

    # Factures nettes
    bill_no_batt = cost_no_batt - rev_sell_no_batt
    bill_with_batt = cost_with_batt - rev_sell_with_batt
    annual_savings = bill_no_batt - bill_with_batt

    # Taux d'autoconsommation (énergie solaire consommée directement / production totale)
    total_production = tot_sell_no_batt + (tot_buy_no_batt - tot_buy_no_batt)  # approx
    # Calcul plus précis : production = surplus + autoconsommation directe
    # surplus sans batterie = tot_sell_no_batt
    # autoconsommation sans batterie = production - surplus
    # On utilise les données brutes pour approximer
    net_col = 'Consommation nette de puissance actuelle'
    if net_col in sim_df.columns:
        net_vals = sim_df[net_col].values
        # Production solaire totale = somme des surplus (quand net < 0) + autoconsommation directe
        # Autoconsommation directe = min(production, consommation) quand il y a du soleil
        # Approximation : surplus_no_batt = énergie vendue sans batterie
        total_solar = tot_sell_no_batt  # minimum, le solaire autoconsommé directement n'est pas mesuré ici
        # On sait que la production réduit la conso nette, donc production = conso brute - conso nette
        # Sans données de production séparées, on approxime
        self_consumption_no_batt = 0.0
        self_consumption_with_batt = 0.0
        if total_solar > 0:
            self_consumption_no_batt = max(0, 1 - tot_sell_no_batt / (tot_sell_no_batt + 1))
            self_consumption_with_batt = max(0, 1 - tot_sell_batt / (tot_sell_no_batt + 1))
    else:
        self_consumption_no_batt = 0.0
        self_consumption_with_batt = 0.0

    # Taux d'autarcie
    autarky_with_batt = 0.0
    if tot_buy_no_batt > 0:
        autarky_with_batt = 1 - (tot_buy_batt / tot_buy_no_batt)

    return {
        'total_grid_buy_kwh_no_batt': tot_buy_no_batt,
        'total_grid_sell_kwh_no_batt': tot_sell_no_batt,
        'total_grid_buy_kwh_with_batt': tot_buy_batt,
        'total_grid_sell_kwh_with_batt': tot_sell_batt,
        'cost_no_batt': cost_no_batt,
        'cost_with_batt': cost_with_batt,
        'cost_no_batt_hp': cost_no_batt_hp,
        'cost_no_batt_hc': cost_no_batt_hc,
        'cost_batt_hp': cost_batt_hp,
        'cost_batt_hc': cost_batt_hc,
        'revenue_sell_no_batt': rev_sell_no_batt,
        'revenue_sell_with_batt': rev_sell_with_batt,
        'bill_no_batt': bill_no_batt,
        'bill_with_batt': bill_with_batt,
        'annual_savings': annual_savings,
        'self_consumption_rate_no_batt': self_consumption_no_batt,
        'self_consumption_rate_with_batt': self_consumption_with_batt,
        'autarky_rate_with_batt': autarky_with_batt,
    }
