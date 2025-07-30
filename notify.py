"""
Multi-channel Notification Manager for Zangbéto Website Monitor

This module provides asynchronous notification capabilities across multiple channels:
- System notifications (notify-send)
- Email notifications (SMTP)
- Slack notifications (webhook)
- Telegram notifications (Bot API)

All notification methods are non-blocking and use asyncio for concurrent execution.

Environment Variables:
    SMTP_HOST: SMTP server hostname
    SMTP_PORT: SMTP server port (default: 587)
    SMTP_USER: SMTP username
    SMTP_PASSWORD: SMTP password
    SLACK_WEBHOOK_URL: Slack webhook URL for notifications
    TELEGRAM_BOT_TOKEN: Telegram bot token
    TELEGRAM_CHAT_ID: Telegram chat ID for notifications

Example:
    # Create notification manager
    nm = NotificationManager()
    
    # Send system notification
    await nm.system_notify("Alert", "Website down!")
    
    # Send email notification
    await nm.email_notify("Alert", "Website down!", ["admin@example.com"])
"""

import os
import subprocess
import asyncio
import smtplib
from email.mime.text import MIMEText
from typing import List, Optional
import aiohttp
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment configuration
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = os.getenv('SMTP_PORT', 587)
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


class NotificationManager:
    """
    Asynchronous multi-channel notification manager.
    
    Manages notifications across multiple channels including system notifications,
    email, Slack, and Telegram. All methods are asynchronous and non-blocking.
    
    Configuration is done via environment variables for security.
    
    Attributes:
        email_host (str): SMTP server hostname
        email_port (int): SMTP server port
        email_user (str): SMTP username
        email_password (str): SMTP password
        slack_webhook (str): Slack webhook URL
        telegram_token (str): Telegram bot token
        telegram_chat_id (str): Telegram chat ID
    
    Example:
        >>> nm = NotificationManager()
        >>> await nm.system_notify("Test", "Hello World!")
    """
    
    def __init__(self):
        """
        Initialize the NotificationManager with environment configuration.
        
        Loads all configuration from environment variables and logs
        which notification channels are available.
        """
        # Email configuration
        self.email_host = SMTP_HOST
        self.email_port = int(SMTP_PORT) if SMTP_PORT else 587
        self.email_user = SMTP_USER
        self.email_password = SMTP_PASSWORD
        
        # Slack webhook URL
        self.slack_webhook = SLACK_WEBHOOK_URL
        
        # Telegram bot configuration
        self.telegram_token = TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = TELEGRAM_CHAT_ID
        
        # Log available notification channels
        self._log_available_channels()
    
    def _log_available_channels(self) -> None:
        """
        Log which notification channels are properly configured.
        
        This helps with debugging configuration issues during startup.
        """
        channels = []
        
        if all([self.email_host, self.email_user, self.email_password]):
            channels.append("Email")
        
        if self.slack_webhook:
            channels.append("Slack")
        
        if all([self.telegram_token, self.telegram_chat_id]):
            channels.append("Telegram")
        
        # System notifications are always available on Linux
        channels.append("System")
        
        logger.info(f"Available notification channels: {', '.join(channels)}")
        
        if len(channels) == 1:  # Only system notifications
            logger.warning("Only system notifications configured. Consider setting up additional channels.")

    async def system_notify(self, title: str, message: str, 
                          app_name: str = "Zangbéto Site Monitor", 
                          icon: str = "dialog-information") -> bool:
        """
        Send a non-blocking system notification using notify-send.
        
        Args:
            title (str): Notification title
            message (str): Notification message body
            app_name (str, optional): Application name shown in notification. 
                                    Defaults to "Zangbéto Site Monitor".
            icon (str, optional): Icon name for the notification. 
                                Defaults to "dialog-information".
        
        Returns:
            bool: True if notification was sent successfully, False otherwise.
        
        Example:
            >>> await nm.system_notify("Alert", "Website is down!", icon="dialog-warning")
        
        Note:
            This method requires notify-send to be installed on the system.
            On most Linux distributions, this is provided by libnotify-bin package.
        """
        try:
            logger.debug(f"Sending system notification: {title}")
            await asyncio.to_thread(
                subprocess.run,
                ['notify-send', title, message, f"--icon={icon}", f"--app-name={app_name}"],
                check=True
            )
            logger.info(f"System notification sent: {title}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"System notification failed: {e}")
            return False
        except FileNotFoundError:
            logger.error("notify-send not found. Install libnotify-bin package.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in system notification: {e}")
            return False

    async def email_notify(self, subject: str, body: str, to_addrs: List[str]) -> bool:
        """
        Send an email notification via SMTP asynchronously.
        
        Args:
            subject (str): Email subject line
            body (str): Email message body (plain text)
            to_addrs (List[str]): List of recipient email addresses
        
        Returns:
            bool: True if email was sent successfully, False otherwise.
        
        Raises:
            ValueError: If to_addrs is empty or contains invalid emails
        
        Example:
            >>> await nm.email_notify(
            ...     "Website Alert", 
            ...     "example.com is down", 
            ...     ["admin@company.com", "ops@company.com"]
            ... )
        
        Note:
            Requires SMTP_HOST, SMTP_USER, and SMTP_PASSWORD environment variables.
            Uses STARTTLS for secure connection.
        """
        if not to_addrs:
            raise ValueError("to_addrs cannot be empty")
        
        if not all([self.email_host, self.email_user, self.email_password]):
            logger.warning("SMTP not configured, email notification skipped")
            return False
        
        def send_email():
            """Inner function to send email synchronously."""
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = self.email_user
            msg['To'] = ', '.join(to_addrs)
            
            with smtplib.SMTP(self.email_host, self.email_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.sendmail(self.email_user, to_addrs, msg.as_string())
        
        try:
            logger.debug(f"Sending email to {len(to_addrs)} recipients: {subject}")
            await asyncio.to_thread(send_email)
            logger.info(f"Email sent successfully to {', '.join(to_addrs)}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed. Check credentials.")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    async def slack_notify(self, message: str, channel: Optional[str] = None) -> bool:
        """
        Send a message to Slack via webhook asynchronously.
        
        Args:
            message (str): Message text to send
            channel (str, optional): Slack channel to send to. 
                                   If None, uses webhook default channel.
        
        Returns:
            bool: True if message was sent successfully, False otherwise.
        
        Example:
            >>> await nm.slack_notify("🚨 Website example.com is down!")
            >>> await nm.slack_notify("✅ All systems operational", "#monitoring")
        
        Note:
            Requires SLACK_WEBHOOK_URL environment variable.
            Supports Slack markdown formatting in messages.
        """
        if not self.slack_webhook:
            logger.warning("Slack webhook not configured, notification skipped")
            return False
        
        payload = {"text": message}
        if channel:
            payload["channel"] = channel
        
        try:
            logger.debug(f"Sending Slack notification: {message[:50]}...")
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook, json=payload) as response:
                    response.raise_for_status()
                    logger.info("Slack notification sent successfully")
                    return True
        except aiohttp.ClientError as e:
            logger.error(f"Slack notification failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Slack notification: {e}")
            return False

    async def telegram_notify(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message via Telegram Bot API asynchronously.
        
        Args:
            message (str): Message text to send
            parse_mode (str, optional): Message formatting mode. 
                                      Can be "Markdown", "HTML", or None. 
                                      Defaults to "Markdown".
        
        Returns:
            bool: True if message was sent successfully, False otherwise.
        
        Example:
            >>> await nm.telegram_notify("🚨 *Alert*: Website is down!")
            >>> await nm.telegram_notify("<b>Alert</b>: Website is down!", "HTML")
        
        Note:
            Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
            Supports Telegram Bot API formatting (Markdown/HTML).
        """
        if not all([self.telegram_token, self.telegram_chat_id]):
            logger.warning("Telegram bot not configured, notification skipped")
            return False
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        try:
            logger.debug(f"Sending Telegram notification: {message[:50]}...")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    response.raise_for_status()
                    logger.info("Telegram notification sent successfully")
                    return True
        except aiohttp.ClientError as e:
            logger.error(f"Telegram notification failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Telegram notification: {e}")
            return False

    async def notify_all(self, title: str, message: str, 
                        email_recipients: Optional[List[str]] = None) -> dict:
        """
        Send notifications across all configured channels simultaneously.
        
        Args:
            title (str): Notification title (used for system and email subject)
            message (str): Notification message body
            email_recipients (List[str], optional): Email recipients. 
                                                  If None, email is skipped.
        
        Returns:
            dict: Dictionary with channel names as keys and success status as values.
                 Example: {"system": True, "email": False, "slack": True, "telegram": True}
        
        Example:
            >>> results = await nm.notify_all(
            ...     "Critical Alert", 
            ...     "Database connection failed",
            ...     ["admin@company.com"]
            ... )
            >>> print(f"Notifications sent: {sum(results.values())}/{len(results)}")
        
        Note:
            This method sends notifications concurrently for better performance.
            Failed channels don't affect others - each is independent.
        """
        logger.info(f"Sending notifications to all channels: {title}")
        
        # Prepare tasks for concurrent execution
        tasks = []
        channel_names = []
        
        # System notification
        tasks.append(self.system_notify(title, message))
        channel_names.append("system")
        
        # Email notification
        if email_recipients:
            tasks.append(self.email_notify(title, message, email_recipients))
            channel_names.append("email")
        
        # Slack notification
        if self.slack_webhook:
            slack_message = f"*{title}*\n{message}"
            tasks.append(self.slack_notify(slack_message))
            channel_names.append("slack")
        
        # Telegram notification
        if all([self.telegram_token, self.telegram_chat_id]):
            telegram_message = f"*{title}*\n{message}"
            tasks.append(self.telegram_notify(telegram_message))
            channel_names.append("telegram")
        
        # Execute all notifications concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            status_dict = {}
            successful = 0
            
            for name, result in zip(channel_names, results):
                if isinstance(result, Exception):
                    logger.error(f"Exception in {name} notification: {result}")
                    status_dict[name] = False
                else:
                    status_dict[name] = result
                    if result:
                        successful += 1
            
            logger.info(f"Notifications completed: {successful}/{len(channel_names)} successful")
            return status_dict
            
        except Exception as e:
            logger.error(f"Unexpected error in notify_all: {e}")
            return {name: False for name in channel_names}


# Example usage and testing
async def main():
    """
    Example usage of the NotificationManager.
    
    This function demonstrates how to use various notification methods
    and is useful for testing configuration.
    """
    logger.info("Testing NotificationManager...")
    
    nm = NotificationManager()
    
    # Test system notification
    await nm.system_notify("Test System", "Asynchronous system notification test")
    
    # Test email notification (uncomment and configure SMTP)
    # await nm.email_notify("Test Email", "This is a test email.", ["recipient@example.com"])
    
    # Test Slack notification (uncomment and configure webhook)
    # await nm.slack_notify("🧪 Test Slack notification")
    
    # Test Telegram notification (uncomment and configure bot)
    # await nm.telegram_notify("🧪 Test Telegram notification")
    
    # Test all notifications at once
    # results = await nm.notify_all(
    #     "Test All Channels",
    #     "Testing all notification channels simultaneously",
    #     ["admin@example.com"]
    # )
    # logger.info(f"All notifications result: {results}")
    
    logger.info("NotificationManager testing completed")


if __name__ == "__main__":
    asyncio.run(main())