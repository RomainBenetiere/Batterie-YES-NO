import pandas as pd
import numpy as np

def generate_mock_data() -> pd.DataFrame:
    """
    Génère 1 an de données fictives réalistes par intervalles de 15 min (35 040 points).
    Le profil correspond à un foyer français consommant environ 8000 kWh/an
    et une installation solaire de 6 kWc produisant environ 7500 kWh/an.
    Retourne un DataFrame avec 'timestamp' et 'Consommation nette de puissance actuelle'.
    """
    np.random.seed(42)
    
    # Création de l'index temporel (1 an, toutes les 15 minutes)
    timestamps = pd.date_range(start='2025-01-01', end='2025-12-31 23:45:00', freq='15min')
    n_points = len(timestamps)
    
    # Extraction des caractéristiques temporelles (conversion en arrays numpy)
    hour = (timestamps.hour + timestamps.minute / 60.0).values.astype(float)
    day_of_week = timestamps.dayofweek.values
    day_of_year = timestamps.dayofyear.values.astype(float)
    
    # --- Profil de consommation ---
    # Base: 0.3 kW
    consumption = np.full(n_points, 0.3)
    
    # Matin (6h-9h): pic de 1.5 à 2.5 kW
    morning_mask = (hour >= 6) & (hour < 9)
    consumption[morning_mask] += np.random.uniform(1.2, 2.2, morning_mask.sum())
    
    # Journée (9h-17h): 0.5 à 1.0 kW
    day_mask = (hour >= 9) & (hour < 17)
    consumption[day_mask] += np.random.uniform(0.2, 0.7, day_mask.sum())
    
    # Soir (17h-22h): pic de 2.0 à 3.5 kW
    evening_mask = (hour >= 17) & (hour < 22)
    consumption[evening_mask] += np.random.uniform(1.7, 3.2, evening_mask.sum())
    
    # Variation week-end
    weekend_mask = day_of_week >= 5
    consumption[weekend_mask & morning_mask] -= 0.5 # Matins plus calmes
    consumption[weekend_mask & day_mask] += 0.5     # Journées plus actives
    
    # Variation saisonnière (cosinus centré sur le début d'année)
    # +20% en hiver, -10% en été
    seasonal_factor = 1.05 + 0.15 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    consumption *= seasonal_factor
    
    # Bruit aléatoire (±20%)
    noise_factor = np.random.uniform(0.8, 1.2, n_points)
    consumption *= noise_factor
    
    # --- Profil de production solaire ---
    # Facteur saisonnier pour le soleil (max en été, min en hiver)
    # E.g., max ~5.5 kW fin juin, max ~1.5 kW fin décembre
    solar_seasonal_peak = 3.5 - 2.0 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
    
    # Centre de la production (13h l'été, 12h30 l'hiver)
    solar_noon = 12.75 - 0.25 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
    
    # Largeur de la fenêtre de production (plus large l'été)
    solar_width = 3.0 + 1.0 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
    
    # Courbe gaussienne de production
    solar_production = solar_seasonal_peak * np.exp(-0.5 * ((hour - solar_noon) / solar_width)**2)
    
    # Annulation la nuit (très faible production ignorée)
    solar_production = np.where(solar_production < 0.1, 0.0, solar_production)
    
    # Couverture nuageuse (baisse aléatoire de production)
    clouds = np.random.uniform(0, 1, n_points)
    cloud_drops = np.where(clouds > 0.7, np.random.uniform(0.2, 0.8, n_points), 1.0)
    solar_production *= cloud_drops
    
    # --- Consommation nette ---
    net_consumption = consumption - solar_production
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'Consommation nette de puissance actuelle': net_consumption
    })
    
    return df

def generate_mock_data_description() -> str:
    """
    Retourne une description textuelle des données fictives générées.
    """
    return (
        "Ces données fictives représentent 1 année de relevés au pas de 15 minutes (35 040 points). "
        "Elles simulent un foyer français moyen avec une consommation annuelle d'environ 8000 kWh, "
        "équipé d'une installation solaire de 6 kWc produisant environ 7500 kWh/an.\n\n"
        "- La **consommation** intègre des pics matinaux et en soirée, une variation week-end et "
        "une saisonnalité (chauffage en hiver).\n"
        "- La **production solaire** suit une courbe en cloche centrée sur midi solaire, plus large "
        "et haute en été, avec des passages nuageux aléatoires.\n\n"
        "La colonne *'Consommation nette'* indique l'énergie tirée du réseau (valeurs positives) "
        "ou injectée/disponible (valeurs négatives)."
    )
