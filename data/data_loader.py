# database/data_loader.py

import sqlite3
import pandas as pd

def load_data_from_sqlite(db_path: str, table_name: str) -> pd.DataFrame:
    """
    Charge les données depuis une base SQLite et retourne un DataFrame.

    Args:
        db_path (str): Chemin vers le fichier .sqlite
        table_name (str): Nom de la table à lire

    Returns:
        pd.DataFrame: Données chargées
    """
    try:
        conn = sqlite3.connect(db_path)
        query = f"SELECT * FROM {table_name};"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"[ERREUR] Impossible de charger les données : {e}")
        return pd.DataFrame()
