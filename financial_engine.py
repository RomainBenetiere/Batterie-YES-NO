import numpy as np
import numpy_financial as npf

def project_cashflows(summary_year1: dict, battery_params: dict, tariff_params: dict) -> dict:
    """
    Moteur de projection financière sur N années (ex: 20 ans).
    """
    install_cost_eur = battery_params.get('install_cost_eur', 0.0)
    annual_degradation_percent = battery_params.get('annual_degradation_percent', 0.0)
    
    annual_elec_increase = tariff_params.get('annual_elec_increase', 0.0)
    contract_duration = tariff_params.get('contract_duration', 20)
    sell_price = tariff_params.get('sell_price', 0.0)
    post_contract_sell_price = tariff_params.get('post_contract_sell_price', 0.0)
    projection_years = tariff_params.get('projection_years', 20)
    
    # Economies d'achat générées par la batterie en Année 1
    purchase_savings_y1 = summary_year1['cost_no_batt'] - summary_year1['cost_with_batt']
    
    # Quantité d'énergie vendue en Année 1
    sell_kwh_batt_y1 = summary_year1['total_grid_sell_kwh_with_batt']
    sell_kwh_nobatt_y1 = summary_year1['total_grid_sell_kwh_no_batt']
    
    cashflows = [-install_cost_eur]
    cumulative = [-install_cost_eur]
    yearly_details = []
    
    for y in range(1, projection_years + 1):
        # Facteurs d'évolution
        degradation_factor = (1 - annual_degradation_percent / 100.0) ** (y - 1)
        elec_factor = (1 + annual_elec_increase) ** (y - 1)
        
        # Economies d'achat (évoluent avec prix élec et dégradation batterie)
        current_purchase_savings = purchase_savings_y1 * degradation_factor * elec_factor
        
        # Prix de revente
        current_sell_price = sell_price if y <= contract_duration else post_contract_sell_price
        
        # Revenus de vente (avec et sans batterie)
        current_rev_sell_batt = sell_kwh_batt_y1 * degradation_factor * current_sell_price
        current_rev_sell_nobatt = sell_kwh_nobatt_y1 * degradation_factor * current_sell_price
        
        # Différentiel de revenus de vente
        sell_revenue_diff = current_rev_sell_batt - current_rev_sell_nobatt
        
        # Flux de trésorerie net annuel lié à la batterie
        net_cashflow = current_purchase_savings + sell_revenue_diff
        
        cashflows.append(net_cashflow)
        cumulative.append(cumulative[-1] + net_cashflow)
        
        yearly_details.append({
            'year': y,
            'degradation_factor': degradation_factor,
            'elec_factor': elec_factor,
            'savings': current_purchase_savings,
            'sell_revenue': current_rev_sell_batt, # revenu avec batterie pour détail
            'sell_revenue_diff': sell_revenue_diff,
            'net_cashflow': net_cashflow,
            'cumulative': cumulative[-1]
        })
        
    return {
        'cashflows': cashflows,
        'cumulative_cashflows': cumulative,
        'yearly_details': yearly_details
    }

def compute_npv(cashflows: list, discount_rate: float) -> float:
    """
    Calcule la Valeur Actuelle Nette (VAN).
    """
    return npf.npv(discount_rate, cashflows)

def compute_irr(cashflows: list) -> float:
    """
    Calcule le Taux de Rentabilité Interne (TRI).
    """
    irr_val = npf.irr(cashflows)
    if np.isnan(irr_val) or np.isinf(irr_val):
        return None
    return float(irr_val)

def compute_payback_period(cumulative_cashflows: list) -> float:
    """
    Calcule le temps de retour sur investissement (Payback Period).
    Interpolation linéaire pour les années partielles.
    """
    for i in range(1, len(cumulative_cashflows)):
        if cumulative_cashflows[i] >= 0 and cumulative_cashflows[i-1] < 0:
            fraction = abs(cumulative_cashflows[i-1]) / (cumulative_cashflows[i] - cumulative_cashflows[i-1])
            return float(i - 1 + fraction)
    return None

def compute_discounted_payback(cashflows: list, discount_rate: float) -> float:
    """
    Calcule le temps de retour sur investissement actualisé.
    """
    discounted_cf = [cf / ((1 + discount_rate) ** i) for i, cf in enumerate(cashflows)]
    cum_discounted = []
    tot = 0
    for cf in discounted_cf:
        tot += cf
        cum_discounted.append(tot)
        
    return compute_payback_period(cum_discounted)
