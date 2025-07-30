import os
import subprocess
import asyncio
import smtplib
from email.mime.text import MIMEText
import aiohttp
import logging
from dotenv import load_dotenv
load_dotenv()  # Charge les variables d'environnement depuis .env

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = os.getenv('SMTP_PORT', 587)
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


class NotificationManager:
    """
    Gestionnaire de notifications multi-canaux asynchrone :
    système, email, Slack, Telegram.
    Configurez les credentials via variables d'environnement.
    """
    def __init__(self):
        # Configuration email
        self.email_host = SMTP_HOST
        self.email_port = int(SMTP_PORT)
        self.email_user = SMTP_USER
        self.email_password = SMTP_PASSWORD
        # Slack webhook URL
        self.slack_webhook = SLACK_WEBHOOK_URL
        # Telegram bot
        self.telegram_token = TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = TELEGRAM_CHAT_ID

    async def system_notify(self, title: str, message: str, app_name: str = "Simple Site Monitor", icon: str = "dialog-information"):
        """
        Notification système (notify-send) non-bloquante.
        """
        try:
            await asyncio.to_thread(subprocess.run,
                                  ['notify-send', title, message, f"--icon={icon}", f"--app-name={app_name}"],)
        except Exception as e:
            print(f"Erreur notification système: {e}")

    async def email_notify(self, subject: str, body: str, to_addrs: list):
        """
        Envoie un email via SMTP de façon asynchrone.
        """
        if not all([self.email_host, self.email_user, self.email_password]):
            print("SMTP non configuré, email non envoyé.")
            return
        def send_email():
            msg = MIMEText(body, 'plain')
            msg['Subject'] = subject
            msg['From'] = self.email_user
            msg['To'] = ', '.join(to_addrs)
            with smtplib.SMTP(self.email_host, self.email_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.sendmail(self.email_user, to_addrs, msg.as_string())
        try:
            await asyncio.to_thread(send_email)
        except Exception as e:
            print(f"Erreur envoi email: {e}")

    async def slack_notify(self, message: str):
        """
        Envoie un message sur Slack via webhook de façon asynchrone.
        """
        if not self.slack_webhook:
            print("Webhook Slack non configuré, notification non envoyée.")
            return
        async with aiohttp.ClientSession() as session:
            payload = {"text": message}
            try:
                async with session.post(self.slack_webhook, json=payload) as resp:
                    resp.raise_for_status()
            except Exception as e:
                print(f"Erreur notification Slack: {e}")

    async def telegram_notify(self, message: str):
        """
        Envoie un message via Telegram Bot API de façon asynchrone.
        """
        if not all([self.telegram_token, self.telegram_chat_id]):
            print("Telegram non configuré, notification non envoyée.")
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {"chat_id": self.telegram_chat_id, "text": message}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, data=data) as resp:
                    resp.raise_for_status()
            except Exception as e:
                print(f"Erreur notification Telegram: {e}")

# Exemple d'utilisation asynchrone
async def main():
    nm = NotificationManager()
    await nm.system_notify("Test System", "Notification système asynchrone.")
    #await nm.email_notify("Test Email", "Ceci est un test.", ["destinataire@example.com"])
    #await nm.slack_notify("Test Slack asynchrone.")
    #await nm.telegram_notify("Test Telegram asynchrone.")

if __name__ == "__main__":
    asyncio.run(main())
