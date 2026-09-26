# visualization.py
# Module de visualisation Plotly pour le simulateur de batterie solaire.
# Toutes les visualisations utilisent un thème sombre professionnel.

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# --- Palette de couleurs professionnelle ---
COLORS = {
    'primary': '#00D4AA',       # Teal/cyan
    'secondary': '#FF6B6B',     # Coral red
    'accent': '#FFD93D',        # Doré
    'positive': '#00C853',      # Vert
    'negative': '#FF5252',      # Rouge
    'neutral': '#78909C',       # Gris bleu
    'battery': '#448AFF',       # Bleu
    'solar': '#FFB300',         # Jaune solaire
    'background': '#0e1117',    # Fond sombre Streamlit
    'card': '#16213e',          # Fond carte
    'text': '#e0e0e0',          # Texte clair
    'grid': 'rgba(255,255,255,0.08)',
}

PLOTLY_TEMPLATE = 'plotly_dark'

FRENCH_MONTHS = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
]


def _base_layout(**kwargs):
    """Retourne un dictionnaire de layout de base pour tous les graphiques."""
    layout = dict(
        template=PLOTLY_TEMPLATE,
        plot_bgcolor=COLORS['background'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text'], family='Inter, sans-serif'),
        margin=dict(l=50, r=30, t=70, b=50),
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            bgcolor='rgba(0,0,0,0)',
        ),
    )
    layout.update(kwargs)
    return layout


def plot_cashflow_cumulative(yearly_details: list, payback_year, projection_years: int = 20) -> go.Figure:
    """
    Graphique en barres des flux de trésorerie cumulés sur N ans.
    yearly_details: liste de dicts avec clés 'year', 'cumulative', 'net_cashflow'
    payback_year: float ou None
    """
    # Année 0 = investissement initial
    years = [0] + [d['year'] for d in yearly_details]
    cumulative = [yearly_details[0]['cumulative'] - yearly_details[0]['net_cashflow']] if yearly_details else [0]
    # Remplir : pour l'année 0, on recalcule
    # En fait on a besoin du cumul à chaque année
    cumulative_values = []
    # Récupérer le cashflow cumulé. L'année 0 est -install_cost (= cumul[0] - savings[0])
    if yearly_details:
        install_cost = yearly_details[0]['cumulative'] - yearly_details[0]['net_cashflow']
        cumulative_values = [install_cost] + [d['cumulative'] for d in yearly_details]
    else:
        cumulative_values = [0]

    colors = [COLORS['negative'] if v < 0 else COLORS['positive'] for v in cumulative_values]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=years,
        y=cumulative_values,
        marker_color=colors,
        marker_line_width=0,
        name='Flux cumulé (€)',
        hovertemplate='Année %{x}<br>Cumul: %{y:,.0f} €<extra></extra>',
    ))

    # Ligne de flux annuels
    annual_cfs = [cumulative_values[0]] + [d['net_cashflow'] for d in yearly_details]
    fig.add_trace(go.Scatter(
        x=years,
        y=annual_cfs,
        mode='lines+markers',
        name='Flux annuel (€)',
        line=dict(color=COLORS['accent'], width=2, dash='dot'),
        marker=dict(size=5),
        hovertemplate='Année %{x}<br>Flux: %{y:,.0f} €<extra></extra>',
    ))

    fig.add_hline(y=0, line_width=2, line_color=COLORS['text'], opacity=0.4)

    if payback_year is not None:
        try:
            pb = float(payback_year)
            if not np.isnan(pb) and 0 < pb <= projection_years:
                fig.add_vline(x=pb, line_dash='dash', line_color=COLORS['accent'], line_width=2)
                fig.add_annotation(
                    x=pb, y=max(cumulative_values) * 0.6 if max(cumulative_values) > 0 else 0,
                    text=f'⏱ Retour: {pb:.1f} ans',
                    showarrow=True, arrowhead=2, ax=50, ay=-40,
                    font=dict(color=COLORS['accent'], size=14, family='Inter, sans-serif'),
                    bgcolor='rgba(0,0,0,0.6)', bordercolor=COLORS['accent'], borderwidth=1,
                    borderpad=6,
                )
        except (TypeError, ValueError):
            pass

    fig.update_layout(**_base_layout(
        title=dict(text=f'Flux de Trésorerie Cumulés sur {projection_years} Ans', font_size=18),
        xaxis_title='Année',
        yaxis_title='Montant (€)',
        yaxis=dict(gridcolor=COLORS['grid']),
        xaxis=dict(gridcolor=COLORS['grid'], dtick=1 if projection_years <= 25 else 2),
        bargap=0.2,
    ))

    return fig


def plot_typical_week(sim_df: pd.DataFrame, week_start_date, timestep_hours: float, capacity_kwh: float = 10.0) -> go.Figure:
    """
    Visualise le comportement du système sur une semaine type.
    Montre la consommation nette, le soutirage réseau, l'injection, et le SoC batterie.
    
    sim_df doit contenir les colonnes:
      timestamp, Consommation nette de puissance actuelle, soc,
      grid_buy_with_batt, grid_sell_with_batt
    """
    end_date = pd.to_datetime(week_start_date) + pd.Timedelta(days=7)
    mask = (sim_df['timestamp'] >= pd.to_datetime(week_start_date)) & (sim_df['timestamp'] < end_date)
    week_df = sim_df.loc[mask].copy()

    if week_df.empty:
        fig = go.Figure()
        fig.add_annotation(text='Aucune donnée pour cette semaine', xref='paper', yref='paper',
                           x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=COLORS['text']))
        fig.update_layout(**_base_layout(title='Aucune donnée disponible'))
        return fig

    # Convertir les énergies (kWh par pas) en puissance (kW) pour l'affichage
    inv_ts = timestep_hours if timestep_hours > 0 else 0.25
    buy_kw = week_df['grid_buy_with_batt'] / inv_ts
    sell_kw = week_df['grid_sell_with_batt'] / inv_ts

    fig = make_subplots(specs=[[{'secondary_y': True}]])

    # Consommation nette sans batterie (référence)
    fig.add_trace(
        go.Scatter(
            x=week_df['timestamp'], y=week_df['Consommation nette de puissance actuelle'],
            name='Conso nette (sans batt.)',
            mode='lines',
            line=dict(color=COLORS['neutral'], width=1.5, dash='dot'),
            opacity=0.7,
        ),
        secondary_y=False,
    )

    # Soutirage réseau avec batterie
    fig.add_trace(
        go.Scatter(
            x=week_df['timestamp'], y=buy_kw,
            name='Soutirage réseau (avec batt.)',
            mode='lines', fill='tozeroy',
            line=dict(color=COLORS['secondary'], width=1.5),
            fillcolor='rgba(255, 107, 107, 0.2)',
        ),
        secondary_y=False,
    )

    # Injection réseau avec batterie (négatif pour distinguer visuellement)
    fig.add_trace(
        go.Scatter(
            x=week_df['timestamp'], y=-sell_kw,
            name='Injection réseau (avec batt.)',
            mode='lines', fill='tozeroy',
            line=dict(color=COLORS['positive'], width=1.5),
            fillcolor='rgba(0, 200, 83, 0.2)',
        ),
        secondary_y=False,
    )

    # SoC batterie (axe secondaire)
    soc_pct = (week_df['soc'] / capacity_kwh * 100) if capacity_kwh > 0 else week_df['soc']
    fig.add_trace(
        go.Scatter(
            x=week_df['timestamp'], y=soc_pct,
            name='Charge batterie (%)',
            mode='lines', fill='tozeroy',
            line=dict(color=COLORS['battery'], width=2.5),
            fillcolor='rgba(68, 138, 255, 0.12)',
        ),
        secondary_y=True,
    )

    date_str = pd.to_datetime(week_start_date).strftime('%d/%m/%Y')
    fig.update_layout(**_base_layout(
        title=dict(text=f'Comportement du Système — Semaine du {date_str}', font_size=18),
    ))
    fig.update_xaxes(title_text='', tickformat='%a %d/%m', gridcolor=COLORS['grid'])
    fig.update_yaxes(title_text='Puissance (kW)', secondary_y=False, gridcolor=COLORS['grid'])
    fig.update_yaxes(title_text='Charge Batterie (%)', secondary_y=True,
                     range=[0, 105], gridcolor=COLORS['grid'])

    return fig


def plot_monthly_comparison(sim_df: pd.DataFrame, tariff_params: dict) -> go.Figure:
    """
    Graphique en barres groupées comparant les coûts mensuels avec et sans batterie.
    sim_df doit contenir les colonnes: timestamp, grid_buy_with_batt, grid_buy_no_batt,
      grid_sell_with_batt, grid_sell_no_batt, tariff_type
    """
    df = sim_df.copy()
    df['month'] = pd.to_datetime(df['timestamp']).dt.month

    hp_price = tariff_params.get('hp_price', 0.25)
    hc_price = tariff_params.get('hc_price', 0.20)
    sell_price = tariff_params.get('sell_price', 0.13)

    monthly_data = []
    for m in range(1, 13):
        mdf = df[df['month'] == m]
        if mdf.empty:
            monthly_data.append({'month_name': FRENCH_MONTHS[m - 1], 'cost_no_batt': 0, 'cost_with_batt': 0})
            continue

        # Sans batterie
        cost_nb_hp = mdf.loc[mdf['tariff_type'] == 'HP', 'grid_buy_no_batt'].sum() * hp_price
        cost_nb_hc = mdf.loc[mdf['tariff_type'] == 'HC', 'grid_buy_no_batt'].sum() * hc_price
        rev_nb = mdf['grid_sell_no_batt'].sum() * sell_price
        bill_nb = cost_nb_hp + cost_nb_hc - rev_nb

        # Avec batterie
        cost_wb_hp = mdf.loc[mdf['tariff_type'] == 'HP', 'grid_buy_with_batt'].sum() * hp_price
        cost_wb_hc = mdf.loc[mdf['tariff_type'] == 'HC', 'grid_buy_with_batt'].sum() * hc_price
        rev_wb = mdf['grid_sell_with_batt'].sum() * sell_price
        bill_wb = cost_wb_hp + cost_wb_hc - rev_wb

        monthly_data.append({
            'month_name': FRENCH_MONTHS[m - 1],
            'cost_no_batt': round(bill_nb, 2),
            'cost_with_batt': round(bill_wb, 2),
        })

    mdf_plot = pd.DataFrame(monthly_data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=mdf_plot['month_name'], y=mdf_plot['cost_no_batt'],
        name='Sans batterie', marker_color=COLORS['secondary'],
        hovertemplate='%{x}<br>%{y:.0f} €<extra>Sans batterie</extra>',
    ))
    fig.add_trace(go.Bar(
        x=mdf_plot['month_name'], y=mdf_plot['cost_with_batt'],
        name='Avec batterie', marker_color=COLORS['primary'],
        hovertemplate='%{x}<br>%{y:.0f} €<extra>Avec batterie</extra>',
    ))

    # Annotations économies mensuelles
    savings = mdf_plot['cost_no_batt'] - mdf_plot['cost_with_batt']
    for i, s in enumerate(savings):
        if s > 0.5:
            fig.add_annotation(
                x=mdf_plot['month_name'].iloc[i],
                y=max(mdf_plot['cost_no_batt'].iloc[i], mdf_plot['cost_with_batt'].iloc[i]) + 3,
                text=f'-{s:.0f}€', showarrow=False,
                font=dict(color=COLORS['positive'], size=11, family='Inter, sans-serif'),
            )

    fig.update_layout(**_base_layout(
        title=dict(text="Comparaison des Coûts Mensuels d'Électricité", font_size=18),
        xaxis_title='', yaxis_title='Facture nette mensuelle (€)',
        barmode='group', bargap=0.15, bargroupgap=0.05,
        yaxis=dict(gridcolor=COLORS['grid']),
    ))

    return fig


def plot_soc_heatmap(sim_df: pd.DataFrame, capacity_kwh: float = 10.0) -> go.Figure:
    """
    Heatmap du SoC batterie par heure et par jour de l'année.
    Utile pour comprendre les patterns saisonniers.
    """
    df = sim_df.copy()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    soc_pct = (df.groupby(['date', 'hour'])['soc'].mean() / capacity_kwh * 100).unstack(fill_value=0)

    fig = go.Figure(data=go.Heatmap(
        z=soc_pct.values,
        x=[f'{h}h' for h in range(24)],
        y=pd.to_datetime(soc_pct.index).strftime('%d/%m'),
        colorscale=[[0, COLORS['negative']], [0.5, COLORS['accent']], [1, COLORS['positive']]],
        colorbar=dict(title='SoC (%)'),
        hovertemplate='Jour: %{y}<br>Heure: %{x}<br>SoC: %{z:.0f}%<extra></extra>',
    ))

    fig.update_layout(**_base_layout(
        title=dict(text='Carte Thermique du Niveau de Charge', font_size=18),
        xaxis_title='Heure', yaxis_title='',
        yaxis=dict(autorange='reversed'),
    ))

    return fig
