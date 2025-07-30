"""
Nettoyage  frequente de la base de données sqlite

"""

import sqlite3
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DB_PATH = "history.db"
def clean_old_entries(db_path: str, days: int = 30):
    """
    Supprime les entrées plus anciennes que le nombre de jours spécifié.
    
    Args:
        db_path (str): Chemin vers la base de données SQLite.
        days (int): Nombre de jours au-delà duquel les entrées seront supprimées.
    """
    if not os.path.exists(db_path):
        logger.warning(f"Base de données {db_path} non trouvée.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Calculer la date limite
    limit_date = datetime.now() - timedelta(days=days)
    
    # Supprimer les entrées plus anciennes que la date limite
    logger.info(f"Nettoyage des entrées plus anciennes que {days} jours...")
    cursor.execute("DELETE FROM history WHERE timestamp < ?", (limit_date,))
    cursor.execute("DELETE FROM checks WHERE timestamp < ?", (limit_date,))
    logger.info(f"Suppression des entrées plus anciennes que {days} jours.")
    
    conn.commit()
    conn.close()
    logger.info(f"Nettoyage terminé. Entrées plus anciennes que {days} jours supprimées.")