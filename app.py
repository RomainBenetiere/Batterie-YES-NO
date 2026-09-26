# app.py
# Application Streamlit principale — Simulateur de Rentabilité Batterie Solaire
# Point d'entrée : streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from battery_models import BATTERY_MODELS, get_model_names, get_default_params, DEFAULT_TARIFF_PARAMS
from data_handler import load_and_clean_csv, detect_timestep, validate_data
from battery_simulation import simulate_battery, compute_annual_summary
from financial_engine import project_cashflows, compute_npv, compute_irr, compute_discounted_payback
from visualization import (
    plot_cashflow_cumulative, plot_typical_week,
    plot_monthly_comparison, COLORS
)
from mock_data import generate_mock_data, generate_mock_data_description

# ─────────────────────────── Configuration de la page ───────────────────────────
st.set_page_config(
    page_title='Simulateur Batterie Solaire',
    page_icon='🔋',
    layout='wide',
    initial_sidebar_state='expanded'
)

# ─────────────────────────── CSS Premium ───────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Application globale */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* En-tête principal avec dégradé */
    .main-header {
        background: linear-gradient(135deg, #00D4AA 0%, #448AFF 50%, #7C4DFF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.6em;
        font-weight: 700;
        margin-bottom: 0;
        padding-top: 10px;
        line-height: 1.2;
    }
    .sub-header {
        color: #78909C;
        font-size: 1.15em;
        margin-bottom: 25px;
        font-weight: 300;
    }
    
    /* Cartes métriques améliorées */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #16213e 0%, #1a1a3e 100%);
        padding: 18px 22px;
        border-radius: 14px;
        border-left: 4px solid #00D4AA;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.85em !important;
        color: #90A4AE !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 500;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.8em !important;
        font-weight: 700;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stSlider label {
        font-size: 0.85em;
        font-weight: 500;
    }
    
    /* Bouton primaire */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%);
        border: none;
        font-weight: 600;
        font-size: 1.05em;
        letter-spacing: 0.5px;
        padding: 12px 24px;
        border-radius: 10px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 212, 170, 0.3);
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 212, 170, 0.5);
    }
    
    /* Tableaux */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
        font-weight: 500;
    }
    
    /* Divider subtil */
    .section-divider {
        border-top: 1px solid rgba(255,255,255,0.06);
        margin: 30px 0;
    }
    
    /* Info cards */
    .info-card {
        background: linear-gradient(135deg, #16213e, #1a1a3e);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.05);
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════ SIDEBAR ═══════════════════════════

st.sidebar.markdown("### ⚡ Paramètres de Simulation")
st.sidebar.markdown("---")

# ──── Section 1 : Modèle de Batterie ────
with st.sidebar.expander("🔋 Modèle de Batterie", expanded=True):
    model_names = get_model_names()
    selected_model = st.selectbox("Modèle", model_names, index=0)

    # Charger les paramètres du modèle sélectionné
    if selected_model == "Personnalisée":
        defaults = get_default_params()
    else:
        defaults = BATTERY_MODELS[selected_model]

    cap_kwh = st.number_input("Capacité totale (kWh)", value=float(defaults['capacity_kwh']),
                               min_value=0.5, max_value=100.0, step=0.5, format="%.1f")
    dod = st.number_input("Profondeur de décharge DoD (%)", value=float(defaults['dod_percent']),
                           min_value=50.0, max_value=100.0, step=1.0, format="%.0f")

    col_c, col_d = st.columns(2)
    with col_c:
        p_charge = st.number_input("Charge max (kW)", value=float(defaults['max_charge_kw']),
                                    min_value=0.5, max_value=25.0, step=0.25, format="%.2f")
    with col_d:
        p_discharge = st.number_input("Décharge max (kW)", value=float(defaults['max_discharge_kw']),
                                       min_value=0.5, max_value=25.0, step=0.25, format="%.2f")

    rend_batt = st.number_input("Rendement batterie (%)", value=float(defaults['round_trip_efficiency']),
                                 min_value=70.0, max_value=100.0, step=0.5, format="%.1f")
    rend_ond = st.number_input("Rendement onduleur (%)", value=float(defaults['inverter_efficiency']),
                                min_value=85.0, max_value=100.0, step=0.5, format="%.1f")
    deg_annuelle = st.number_input("Dégradation annuelle (%)", value=float(defaults['annual_degradation_percent']),
                                    min_value=0.0, max_value=10.0, step=0.1, format="%.1f")
    cout_install = st.number_input("Coût d'installation total (€)", value=float(defaults['install_cost_eur']),
                                    min_value=0.0, max_value=100000.0, step=100.0, format="%.0f")

# ──── Section 2 : Tarification ────
with st.sidebar.expander("💰 Tarification Électrique", expanded=False):
    prix_hp = st.number_input("Prix HP (€/kWh)", value=DEFAULT_TARIFF_PARAMS['hp_price'],
                               min_value=0.01, max_value=1.0, step=0.0001, format="%.4f")
    prix_hc = st.number_input("Prix HC (€/kWh)", value=DEFAULT_TARIFF_PARAMS['hc_price'],
                               min_value=0.01, max_value=1.0, step=0.0001, format="%.4f")

    st.markdown("**Plage Heures Creuses 1**")
    col1, col2 = st.columns(2)
    with col1:
        hc1_start = st.number_input("Début (h)", value=DEFAULT_TARIFF_PARAMS['hc_start_1'],
                                     min_value=0, max_value=23, step=1, key='hc1s')
    with col2:
        hc1_end = st.number_input("Fin (h)", value=DEFAULT_TARIFF_PARAMS['hc_end_1'],
                                   min_value=0, max_value=23, step=1, key='hc1e')

    st.markdown("**Plage Heures Creuses 2**")
    col3, col4 = st.columns(2)
    with col3:
        hc2_start = st.number_input("Début (h)", value=DEFAULT_TARIFF_PARAMS['hc_start_2'],
                                     min_value=0, max_value=23, step=1, key='hc2s')
    with col4:
        hc2_end = st.number_input("Fin (h)", value=DEFAULT_TARIFF_PARAMS['hc_end_2'],
                                   min_value=0, max_value=23, step=1, key='hc2e')

    prix_revente = st.number_input("Prix revente surplus (€/kWh)", value=DEFAULT_TARIFF_PARAMS['sell_price'],
                                    min_value=0.0, max_value=0.5, step=0.001, format="%.4f")

# ──── Section 3 : Hypothèses de projection ────
with st.sidebar.expander("📈 Hypothèses de Projection", expanded=False):
    aug_elec = st.slider("Augmentation annuelle prix élec (%)", 0.0, 10.0,
                          DEFAULT_TARIFF_PARAMS['annual_elec_increase'] * 100, step=0.5) / 100.0
    duree_contrat = st.number_input("Durée contrat revente (années)",
                                     value=DEFAULT_TARIFF_PARAMS['contract_duration'],
                                     min_value=0, max_value=30, step=1)
    tarif_post = st.number_input("Tarif revente post-contrat (€/kWh)",
                                  value=DEFAULT_TARIFF_PARAMS['post_contract_sell_price'],
                                  min_value=0.0, max_value=0.3, step=0.005, format="%.3f")
    taux_actu = st.slider("Taux d'actualisation (%)", 0.0, 10.0,
                           DEFAULT_TARIFF_PARAMS['discount_rate'] * 100, step=0.5) / 100.0
    duree_proj = st.slider("Durée de projection (années)", 10, 30, DEFAULT_TARIFF_PARAMS['projection_years'])


# ═══════════════════════════ ZONE PRINCIPALE ═══════════════════════════

# En-tête
st.markdown('<div class="main-header">🔋 Simulateur de Rentabilité — Batterie Solaire</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Analysez la rentabilité de votre investissement en stockage d\'énergie</div>', unsafe_allow_html=True)

# ──── Chargement des données ────
uploaded_file = st.file_uploader(
    "📂 Chargez vos données de consommation (CSV)",
    type=['csv'],
    help="Fichier CSV avec colonnes 'timestamp' et 'Consommation nette de puissance actuelle' (kW)"
)

with st.expander("📋 Format de fichier CSV attendu", expanded=False):
    st.markdown("""
**Spécifications du fichier :**
| Paramètre | Valeur attendue |
|---|---|
| **Séparateur de colonnes** | Point-virgule `;` |
| **Séparateur décimal** | Virgule `,` |
| **Format de date** | `mm/dd/yyyy hh:mm` |
| **Encodage** | UTF-8 |

**Colonnes requises :**
- `timestamp` — Horodatage de chaque mesure
- `Consommation nette de puissance actuelle` — Puissance en **kW**
  - **Valeurs positives** → consommation depuis le réseau (déficit solaire)
  - **Valeurs négatives** → injection sur le réseau (surproduction solaire)

**Exemple :**
```
timestamp;Consommation nette de puissance actuelle
01/15/2025 08:00;1,523
01/15/2025 08:15;-2,312
01/15/2025 08:30;0,789
```

> Le pas de temps (5 min à 1h) est détecté automatiquement à partir des timestamps.
""")

# Préparer les données
data_warnings = []
use_mock = False

if uploaded_file is not None:
    df, data_warnings = load_and_clean_csv(uploaded_file)
    is_valid, errors = validate_data(df)
    if not is_valid:
        for err in errors:
            st.error(f"❌ {err}")
        st.stop()
else:
    use_mock = True
    df = generate_mock_data()
    st.info(f"📊 **Données de démonstration chargées** — {generate_mock_data_description()}")

# Afficher les avertissements du nettoyage
for w in data_warnings:
    st.warning(f"⚠️ {w}")

# Résumé des données
timestep_h = detect_timestep(df)
net_col = 'Consommation nette de puissance actuelle'
total_consumption = df.loc[df[net_col] > 0, net_col].sum() * timestep_h
total_production = abs(df.loc[df[net_col] < 0, net_col].sum()) * timestep_h

col_info = st.columns(4)
with col_info[0]:
    st.metric("📅 Période couverte",
              f"{pd.to_datetime(df['timestamp'].iloc[0]).strftime('%d/%m/%Y')} → "
              f"{pd.to_datetime(df['timestamp'].iloc[-1]).strftime('%d/%m/%Y')}")
with col_info[1]:
    st.metric("📊 Points de mesure", f"{len(df):,}")
with col_info[2]:
    st.metric("⏱ Pas de temps", f"{int(timestep_h * 60)} min")
with col_info[3]:
    st.metric("☀️ Production solaire estimée", f"{total_production:,.0f} kWh")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ──── Lancement de la simulation ────
run_button = st.button('🚀 Lancer la Simulation', type='primary', use_container_width=True)

if run_button:
    st.session_state['run_sim'] = True

if st.session_state.get('run_sim', False):
    try:
        # Construction des paramètres
        battery_params = {
            'capacity_kwh': cap_kwh,
            'dod_percent': dod,
            'max_charge_kw': p_charge,
            'max_discharge_kw': p_discharge,
            'round_trip_efficiency': rend_batt / 100.0,
            'inverter_efficiency': rend_ond / 100.0,
            'annual_degradation_percent': deg_annuelle,
            'install_cost_eur': cout_install,
        }

        tariff_params = {
            'hp_price': prix_hp,
            'hc_price': prix_hc,
            'hc_start_1': hc1_start,
            'hc_end_1': hc1_end,
            'hc_start_2': hc2_start,
            'hc_end_2': hc2_end,
            'sell_price': prix_revente,
            'annual_elec_increase': aug_elec,
            'contract_duration': duree_contrat,
            'post_contract_sell_price': tarif_post,
            'discount_rate': taux_actu,
            'projection_years': duree_proj,
        }

        # ═══ Simulation physique ═══
        with st.spinner('⚙️ Simulation physique en cours...'):
            sim_df = simulate_battery(df.copy(), battery_params, tariff_params)
            summary = compute_annual_summary(sim_df, tariff_params)

        # ═══ Calculs financiers ═══
        with st.spinner('💰 Projections financières en cours...'):
            fin = project_cashflows(summary, battery_params, tariff_params)
            cashflows = fin['cashflows']
            cumul = fin['cumulative_cashflows']
            yearly = fin['yearly_details']

            van = compute_npv(cashflows, taux_actu)
            tri = compute_irr(cashflows)
            roi = compute_discounted_payback(cashflows, taux_actu)

        # ═══════════════════ RÉSULTATS ═══════════════════

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("## 📊 Résultats de l'Analyse")

        # ──── KPI Financiers ────
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            van_delta = "Investissement rentable" if van and van > 0 else "Investissement non rentable"
            st.metric("💎 Valeur Actuelle Nette (VAN)",
                      f"{van:+,.0f} €" if van else "N/A",
                      delta=van_delta)
        with kpi2:
            tri_str = f"{tri * 100:.1f} %" if tri is not None else "N/A"
            st.metric("📈 Taux de Rentabilité Interne (TRI)", tri_str)
        with kpi3:
            roi_str = f"{roi:.1f} ans" if roi is not None else "> {duree_proj} ans"
            st.metric("⏱ Retour sur Investissement", roi_str)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # ──── Bilan Année 1 ────
        st.markdown("### 📋 Bilan Annuel — Année 1")

        summary_table = pd.DataFrame({
            'Configuration': ['☀️ Sans batterie', '🔋 Avec batterie', '✅ Économie'],
            'Achat réseau (kWh)': [
                f"{summary['total_grid_buy_kwh_no_batt']:,.0f}",
                f"{summary['total_grid_buy_kwh_with_batt']:,.0f}",
                f"{summary['total_grid_buy_kwh_no_batt'] - summary['total_grid_buy_kwh_with_batt']:,.0f}",
            ],
            'Coût achat (€)': [
                f"{summary['cost_no_batt']:,.2f}",
                f"{summary['cost_with_batt']:,.2f}",
                f"{summary['cost_no_batt'] - summary['cost_with_batt']:,.2f}",
            ],
            'Revente (kWh)': [
                f"{summary['total_grid_sell_kwh_no_batt']:,.0f}",
                f"{summary['total_grid_sell_kwh_with_batt']:,.0f}",
                f"{summary['total_grid_sell_kwh_with_batt'] - summary['total_grid_sell_kwh_no_batt']:,.0f}",
            ],
            'Revenu revente (€)': [
                f"{summary['revenue_sell_no_batt']:,.2f}",
                f"{summary['revenue_sell_with_batt']:,.2f}",
                f"{summary['revenue_sell_with_batt'] - summary['revenue_sell_no_batt']:,.2f}",
            ],
            'Facture nette (€)': [
                f"{summary['bill_no_batt']:,.2f}",
                f"{summary['bill_with_batt']:,.2f}",
                f"💰 {summary['annual_savings']:,.2f}",
            ],
        })
        summary_table = summary_table.set_index('Configuration')
        st.dataframe(summary_table, use_container_width=True)

        # ──── Indicateurs complémentaires ────
        extra1, extra2, extra3 = st.columns(3)
        with extra1:
            st.metric("🔌 Soutirage réseau évité",
                      f"{summary['total_grid_buy_kwh_no_batt'] - summary['total_grid_buy_kwh_with_batt']:,.0f} kWh")
        with extra2:
            autarky = 0
            total_need = summary['total_grid_buy_kwh_no_batt'] + summary['total_grid_sell_kwh_no_batt']
            if total_need > 0:
                autarky = (1 - summary['total_grid_buy_kwh_with_batt'] / (
                    summary['total_grid_buy_kwh_no_batt'])) * 100 if summary['total_grid_buy_kwh_no_batt'] > 0 else 0
            st.metric("🏠 Gain d'autonomie", f"+{autarky:.1f} %")
        with extra3:
            st.metric("💰 Économie année 1", f"{summary['annual_savings']:,.2f} €")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # ──── Graphiques ────
        tab1, tab2, tab3 = st.tabs([
            '📈 Projection Financière',
            '🔄 Semaine Type',
            '📊 Comparaison Mensuelle'
        ])

        with tab1:
            fig_cf = plot_cashflow_cumulative(yearly, roi, duree_proj)
            st.plotly_chart(fig_cf, use_container_width=True, key='cashflow_chart')

            # Tableau détaillé des flux
            with st.expander("📄 Détail des flux annuels"):
                flow_df = pd.DataFrame(yearly)
                flow_df.columns = ['Année', 'Facteur dégradation', 'Facteur prix élec.',
                                   'Économies achat (€)', 'Revenu vente (€)',
                                   'Diff. revente (€)', 'Flux net (€)', 'Cumul (€)']
                st.dataframe(flow_df.style.format({
                    'Facteur dégradation': '{:.2%}',
                    'Facteur prix élec.': '{:.2%}',
                    'Économies achat (€)': '{:,.2f}',
                    'Revenu vente (€)': '{:,.2f}',
                    'Diff. revente (€)': '{:,.2f}',
                    'Flux net (€)': '{:,.2f}',
                    'Cumul (€)': '{:,.2f}',
                }), use_container_width=True)

        with tab2:
            # Sélecteur de semaine
            min_date = pd.to_datetime(sim_df['timestamp'].iloc[0]).date()
            max_date = pd.to_datetime(sim_df['timestamp'].iloc[-1]).date() - timedelta(days=7)

            # Par défaut : dernière semaine de juin (semaine solaire intéressante)
            default_week = datetime(min_date.year, 6, 23).date()
            if default_week < min_date:
                default_week = min_date
            if default_week > max_date:
                default_week = max_date

            # Initialiser la session_state si nécessaire
            if 'week_date' not in st.session_state:
                st.session_state['week_date'] = default_week

            # Boutons raccourcis saisons — modifient la session_state AVANT le date_input
            col_week1, col_week2, col_week3 = st.columns([3, 1, 1])
            with col_week2:
                if st.button("☀️ Été", use_container_width=True):
                    summer_date = datetime(min_date.year, 7, 7).date()
                    if summer_date < min_date:
                        summer_date = min_date
                    if summer_date > max_date:
                        summer_date = max_date
                    st.session_state['week_date'] = summer_date
            with col_week3:
                if st.button("❄️ Hiver", use_container_width=True):
                    winter_date = datetime(min_date.year, 1, 13).date()
                    if winter_date < min_date:
                        winter_date = min_date
                    if winter_date > max_date:
                        winter_date = max_date
                    st.session_state['week_date'] = winter_date

            with col_week1:
                week_date = st.date_input("📅 Début de la semaine à afficher",
                                          value=st.session_state['week_date'],
                                          min_value=min_date, max_value=max_date,
                                          key='week_date')

            fig_week = plot_typical_week(sim_df, week_date, timestep_h, cap_kwh)
            st.plotly_chart(fig_week, use_container_width=True, key='week_chart')

        with tab3:
            fig_month = plot_monthly_comparison(sim_df, tariff_params)
            st.plotly_chart(fig_month, use_container_width=True, key='monthly_chart')

        # ──── Pied de page ────
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align: center; color: #546E7A; font-size: 0.85em; padding: 20px 0;">'
            '🔋 Simulateur Batterie Solaire — '
            f'Modèle: <strong>{selected_model}</strong> | '
            f'Capacité: <strong>{cap_kwh} kWh</strong> | '
            f'Coût: <strong>{cout_install:,.0f} €</strong>'
            '</div>',
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.error(f"❌ Une erreur est survenue lors de la simulation : {str(e)}")
        with st.expander("Détails de l'erreur"):
            import traceback
            st.code(traceback.format_exc())
