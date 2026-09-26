import pandas as pd
import numpy as np

def load_and_clean_csv(uploaded_file) -> tuple[pd.DataFrame, list[str]]:
    """
    Charge un fichier CSV, nettoie les données et retourne un tuple (DataFrame_nettoyé, liste_avertissements).
    
    Format attendu :
      - Séparateur de colonnes : point-virgule (;)
      - Séparateur décimal : virgule (,)
      - Format de date : mm/dd/yyyy hh:mm
    
    Le script tente d'abord ce format prioritaire, puis bascule en détection automatique
    si ça échoue, pour rester compatible avec d'autres sources de données.
    """
    warnings = []

    # ─── 1. Lecture du fichier CSV ───
    df = None
    try:
        # Tentative prioritaire : séparateur ; et décimale ,
        df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding='utf-8')
        # Vérifier qu'on a obtenu au moins 2 colonnes (sinon le séparateur est probablement faux)
        if df.shape[1] < 2:
            df = None
    except Exception:
        df = None

    if df is None:
        try:
            # Rembobiner le flux si c'est un UploadedFile Streamlit
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
            # Tentative avec détection automatique du séparateur
            df = pd.read_csv(uploaded_file, sep=None, engine='python', decimal=',')
        except Exception:
            pass

    if df is None:
        try:
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
            # Dernière tentative : virgule comme séparateur, point comme décimale
            df = pd.read_csv(uploaded_file, sep=',', decimal='.')
        except Exception as e:
            warnings.append(f"Erreur lors de la lecture du fichier : {str(e)}")
            return pd.DataFrame(), warnings

    if df.empty:
        warnings.append("Le fichier CSV est vide.")
        return df, warnings

    # ─── 2. Recherche de la colonne timestamp ───
    ts_col = None
    # Recherche par nom exact ou partiel (insensible à la casse)
    candidates_ts = ['timestamp', 'date', 'datetime', 'time', 'heure', 'horodatage', 'date/time']
    for c in df.columns:
        if str(c).strip().lower() in candidates_ts:
            ts_col = c
            break
    # Si pas trouvé par nom exact, chercher par contenu partiel
    if ts_col is None:
        for c in df.columns:
            col_lower = str(c).strip().lower()
            if any(k in col_lower for k in ['date', 'time', 'heure', 'horodatage']):
                ts_col = c
                break
    # En dernier recours, prendre la première colonne
    if ts_col is None:
        ts_col = df.columns[0]
        warnings.append(f"Colonne de temps non identifiée, utilisation de la première colonne : '{ts_col}'.")

    # ─── 3. Recherche de la colonne de consommation nette ───
    val_col = None
    # Recherche par mots-clés dans le nom de colonne
    keywords_cons = ['consommation nette', 'net power', 'puissance nette', 'puissance actuelle', 'active power']
    for c in df.columns:
        col_lower = str(c).strip().lower()
        if any(k in col_lower for k in keywords_cons):
            val_col = c
            break
    # Si pas trouvé, chercher 'consommation' ou 'power' ou 'puissance'
    if val_col is None:
        for c in df.columns:
            col_lower = str(c).strip().lower()
            if c != ts_col and any(k in col_lower for k in ['consommation', 'power', 'puissance', 'kw']):
                val_col = c
                break
    # En dernier recours, prendre la première colonne numérique qui n'est pas le timestamp
    if val_col is None:
        for c in df.columns:
            if c != ts_col:
                # Tenter une conversion numérique pour vérifier
                try:
                    test_vals = df[c].astype(str).str.replace(',', '.', regex=False)
                    pd.to_numeric(test_vals, errors='raise')
                    val_col = c
                    warnings.append(f"Colonne de consommation non identifiée formellement, utilisation de : '{val_col}'.")
                    break
                except (ValueError, TypeError):
                    continue
    if val_col is None:
        warnings.append("Aucune colonne numérique trouvée pour la consommation.")
        return pd.DataFrame(), warnings

    # ─── 4. Extraction et renommage des colonnes ───
    df = df[[ts_col, val_col]].copy()
    df.columns = ['timestamp', 'Consommation nette de puissance actuelle']

    # ─── 5. Conversion de la colonne de consommation en numérique ───
    # Gestion du séparateur décimal virgule : remplacer la virgule par un point
    cons_col = 'Consommation nette de puissance actuelle'
    df[cons_col] = (
        df[cons_col]
        .astype(str)
        .str.strip()
        .str.replace('\xa0', '', regex=False)   # espaces insécables
        .str.replace(' ', '', regex=False)       # espaces normaux
        .str.replace(',', '.', regex=False)      # virgule décimale → point
    )
    df[cons_col] = pd.to_numeric(df[cons_col], errors='coerce')

    # ─── 6. Conversion du timestamp en datetime ───
    # Priorité au format mm/dd/yyyy hh:mm
    ts_raw = df['timestamp'].astype(str).str.strip()
    parsed = pd.NaT

    # Tentative 1 : format exact mm/dd/yyyy HH:MM
    try:
        parsed = pd.to_datetime(ts_raw, format='%m/%d/%Y %H:%M', errors='coerce')
    except Exception:
        pass

    # Si trop de NaT, essayer d'autres formats
    if parsed is not pd.NaT and isinstance(parsed, pd.Series):
        nat_ratio = parsed.isna().sum() / len(parsed)
    else:
        nat_ratio = 1.0

    if nat_ratio > 0.5:
        # Tentative 2 : format dd/mm/yyyy HH:MM
        try:
            parsed = pd.to_datetime(ts_raw, format='%d/%m/%Y %H:%M', errors='coerce')
            nat_ratio = parsed.isna().sum() / len(parsed)
        except Exception:
            pass

    if nat_ratio > 0.5:
        # Tentative 3 : format ISO et autres via inférence pandas
        try:
            parsed = pd.to_datetime(ts_raw, format='mixed', dayfirst=False, errors='coerce')
            nat_ratio = parsed.isna().sum() / len(parsed)
        except Exception:
            pass

    if nat_ratio > 0.5:
        # Tentative 4 : dayfirst=True
        try:
            parsed = pd.to_datetime(ts_raw, format='mixed', dayfirst=True, errors='coerce')
        except Exception as e:
            warnings.append(f"Problème lors de la conversion des dates : {str(e)}")

    df['timestamp'] = parsed

    if df['timestamp'].isna().any():
        nb_na_dates = df['timestamp'].isna().sum()
        if nb_na_dates == len(df):
            warnings.append("Aucune date n'a pu être interprétée. Vérifiez le format (attendu : mm/dd/yyyy hh:mm).")
            return pd.DataFrame(), warnings
        warnings.append(f"{nb_na_dates} dates n'ont pas pu être interprétées et ont été ignorées.")
        df = df.dropna(subset=['timestamp'])

    # ─── 7. Tri chronologique et suppression des doublons ───
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    initial_len = len(df)
    df = df.drop_duplicates(subset=['timestamp'])
    if len(df) < initial_len:
        warnings.append(f"{initial_len - len(df)} lignes dupliquées ont été supprimées.")

    # ─── 8. Traitement des valeurs manquantes ───
    if df[cons_col].isna().any():
        nb_na_vals = df[cons_col].isna().sum()
        warnings.append(f"{nb_na_vals} valeurs manquantes détectées et interpolées linéairement.")
        df[cons_col] = df[cons_col].interpolate(method='linear')
        df[cons_col] = df[cons_col].ffill().bfill()

    # ─── 9. Détection des anomalies ───
    # Trous temporels > 2 heures
    time_diffs = df['timestamp'].diff()
    large_gaps = time_diffs > pd.Timedelta(hours=2)
    if large_gaps.any():
        warnings.append(f"{large_gaps.sum()} écarts de plus de 2 heures détectés dans les données.")

    # Valeurs aberrantes (> 50 kW en valeur absolue)
    outliers = df[df[cons_col].abs() > 50]
    if not outliers.empty:
        warnings.append(f"{len(outliers)} valeurs extrêmement élevées (> 50 kW) ont été détectées.")

    return df, warnings

def detect_timestep(df: pd.DataFrame) -> float:
    """
    Détecte le pas de temps en heures à partir de la différence médiane entre les timestamps.
    Retourne un float (ex: 0.25 pour 15 min, 1.0 pour 1 heure).
    """
    if len(df) < 2 or 'timestamp' not in df.columns:
        return 1.0  # Par défaut 1h si impossible de calculer

    time_diffs = df['timestamp'].diff().dropna()
    median_diff = time_diffs.median()

    # Conversion en heures
    return median_diff.total_seconds() / 3600.0

def validate_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Valide que le DataFrame contient les colonnes nécessaires et des données exploitables.
    Retourne (is_valid, liste_erreurs).
    """
    errors = []

    if df.empty:
        errors.append("Les données sont vides.")
        return False, errors

    required_cols = ['timestamp', 'Consommation nette de puissance actuelle']
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"La colonne requise '{col}' est manquante.")

    if len(df) < 100:
        errors.append("Il n'y a pas assez de données pour une simulation fiable (minimum 100 points recommandés).")

    if not errors and df['timestamp'].isna().all():
        errors.append("Toutes les dates sont invalides.")

    return len(errors) == 0, errors
