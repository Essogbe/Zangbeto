#!/usr/bin/env python3
import os
import time
import argparse
import schedule
import subprocess
import threading
from datetime import datetime
from crawler import load_sites, explore_site, init_db, save_results, get_latest_check, generate_html_report
from notify import NotificationManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Defaults
DEFAULT_FREQ_MIN = 30
DEFAULT_REPORT_HOURS = 12
DEFAULT_OUTPUT = "rapport.html"

def open_file_in_browser(file_path):
    """Ouvre le fichier dans le navigateur par défaut"""
    try:
        subprocess.run(['xdg-open', file_path])
    except FileNotFoundError:
        # Fallback pour systèmes sans xdg-open
        subprocess.run(['firefox', file_path])

def send_report_notification(title, output_path):
    """Envoie une notification avec action pour ouvrir le rapport"""
    def notification_thread():
        logger.info(f"Envoi de la notification pour le rapport : {output_path}")
        abs_path = os.path.abspath(output_path)
        file_url = f"file://{abs_path}"
        body = "Cliquez pour ouvrir le rapport dans votre navigateur"
        
        try:
            result = subprocess.run([
                'notify-send', 
                title, 
                body,
                '--action=open=Ouvrir le rapport',
                '--urgency=normal',
                '--expire-time=30000',  # 30 secondes
                '--wait'
            ], capture_output=True, text=True, timeout=60)
            
            # Si l'utilisateur clique sur "Ouvrir le rapport"
            if result.returncode == 0 and 'open' in result.stdout:
                open_file_in_browser(file_url)
                
        except subprocess.TimeoutExpired:
            # La notification a expiré sans action
            pass
        except FileNotFoundError:
            # Fallback: notification simple si notify-send n'est pas disponible
            print(f"notify-send non disponible. Rapport généré: {abs_path}")
    
    # Lance dans un thread séparé pour ne pas bloquer
    thread = threading.Thread(target=notification_thread, daemon=True)
    thread.start()

def main():
    parser = argparse.ArgumentParser(
        description="Monitor de sites avec rapports HTML et notifications"
    )
    parser.add_argument(
        "-f", "--frequency", type=int, default=DEFAULT_FREQ_MIN,
        help=f"Fréquence de surveillance en minutes (défaut: {DEFAULT_FREQ_MIN} min)"
    )
    parser.add_argument(
        "-o", "--output", type=str, default=DEFAULT_OUTPUT,
        help=f"Chemin du fichier rapport HTML (défaut: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "-i", "--interval", type=int, default=DEFAULT_REPORT_HOURS,
        help=f"Intervalle en heures pour envoi du rapport complet (défaut: {DEFAULT_REPORT_HOURS} h)"
    )
    
    args = parser.parse_args()
    logger.info("Démarrage du script de monitoring")
    # Initialisation
    logger.info("Initialisation de la base de données et des sites")
    init_db()
    logger.info("Chargement des sites à surveiller")
    notifier = NotificationManager()
    
    freq = args.frequency
    report_interval = args.interval
    output_path = args.output
    
    def check_job():
        logger.info(f"Lancement du job de vérification toutes les {freq} minutes")
        sites = load_sites()
        all_pages = []
        
        for site in sites:
            all_pages.extend(explore_site(site))
        
        ts = save_results(all_pages)
        ts, latest = get_latest_check()  
        logger.info(f"Résultats sauvegardés pour le timestamp: {ts}")
        generate_html_report(ts, latest, output_path)
        
        # Notification si erreur
        fails = [p for p in latest if not p['ok']]
        if fails:
            msg = "\n".join(f"{p['url']} → {p.get('status_code','?')}" for p in fails)
            notifier.system_notify("Alerte monitoring", msg,icon="dialog-warning")
        
        print(f"[{datetime.utcnow().isoformat()}] Check executed.")
    
    def report_job():
        # Générer le rapport complet et notifier avec action
        ts, pages = get_latest_check()
        generate_html_report(ts, pages, output_path)
        
        title = f"Rapport de monitoring - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Notification avec action pour ouvrir le rapport
        logger
        send_report_notification(title, output_path)
        
        print(f"[{datetime.utcnow().isoformat()}] Report notification sent.")
    
    # Schedule jobs
    logger.info(f"Démarrage du monitoring - Fréquence: {freq} min, Rapports: {report_interval} h")
    check_job()  # run once immediately
    
    schedule.every(freq).minutes.do(check_job)
    schedule.every(report_interval).hours.do(report_job)
    
    # Boucle principale
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt du monitoring...")

if __name__ == "__main__":
    
    
    
    main()