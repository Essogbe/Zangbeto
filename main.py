#!/usr/bin/env python3
import os
import time
import argparse
import schedule
import subprocess
import threading
from datetime import datetime
from crawler import (
    load_sites, explore_site, init_db, save_results, get_latest_check, 
    generate_html_report, check_internet_connectivity, wait_for_connectivity,
    save_connectivity_log
)
from notify import NotificationManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_FREQ_MIN = 30
DEFAULT_REPORT_HOURS = 12
DEFAULT_OUTPUT = "rapport.html"

def open_file_in_browser(file_path):
    """Opens the file in the default browser"""
    try:
        logger.debug(f"Opening file in browser: {file_path}")
        subprocess.run(['xdg-open', file_path])
    except FileNotFoundError:
        # Fallback for systems without xdg-open
        logger.warning("xdg-open not found, trying firefox as fallback")
        try:
            subprocess.run(['firefox', file_path])
        except FileNotFoundError:
            logger.error("No suitable browser opener found (xdg-open or firefox)")

def send_report_notification(title, output_path):
    """Sends a notification with action to open the report"""
    def notification_thread():
        logger.info(f"Sending notification for report: {output_path}")
        abs_path = os.path.abspath(output_path)
        file_url = f"file://{abs_path}"
        body = "Click to open the report in your browser"
        
        try:
            result = subprocess.run([
                'notify-send', 
                title, 
                body,
                "--icon=Zangbeto.jpg",
                "--app-name=Zangbeto Site Monitor",
                '--action=open=Open Report',
                '--urgency=normal',
                '--expire-time=30000',  # 30 seconds
                '--wait'
            ], capture_output=True, text=True, timeout=60)
            
            # If user clicks "Open Report"
            if result.returncode == 0 and 'open' in result.stdout:
                logger.info("User clicked on notification, opening report")
                open_file_in_browser(file_url)
            else:
                logger.debug("Notification expired or dismissed without action")
                
        except subprocess.TimeoutExpired:
            # Notification expired without action
            logger.debug("Notification timeout expired")
        except FileNotFoundError:
            # Fallback: simple notification if notify-send is not available
            logger.warning(f"notify-send not available. Report generated: {abs_path}")

    # Launch in separate thread to avoid blocking
    thread = threading.Thread(target=notification_thread, daemon=True)
    thread.start()

def send_connectivity_notification(notifier, connectivity_restored=False):
    """Send connectivity-related notifications"""
    if connectivity_restored:
        title = "Internet Connectivity Restored"
        message = "Website monitoring will resume with next check cycle"
        icon = "dialog-information"
        logger.info("Sending connectivity restoration notification")
    else:
        title = "Internet Connectivity Issue"
        message = "No internet connection detected. Website monitoring paused until connectivity is restored."
        icon = "dialog-warning"
        logger.warning("Sending connectivity issue notification")
    
    try:
        notifier.system_notify(title, message, icon=icon)
    except Exception as e:
        logger.error(f"Failed to send connectivity notification: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Website monitoring tool with HTML reports and notifications"
    )
    parser.add_argument(
        "-f", "--frequency", type=int, default=DEFAULT_FREQ_MIN,
        help=f"Monitoring frequency in minutes (default: {DEFAULT_FREQ_MIN} min)"
    )
    parser.add_argument(
        "-o", "--output", type=str, default=DEFAULT_OUTPUT,
        help=f"HTML report file path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "-i", "--interval", type=int, default=DEFAULT_REPORT_HOURS,
        help=f"Interval in hours for complete report sending (default: {DEFAULT_REPORT_HOURS} h)"
    )
    parser.add_argument(
        "-c", "--count", type=int, default=None,
        help="Number of check cycles to run (default: infinite for continuous monitoring)"
    )
    parser.add_argument(
        "--one-shot", action="store_true",
        help="Run a single check, generate report, send notification and exit (equivalent to --count 1)"
    )
    parser.add_argument(
        "--skip-connectivity", action="store_true",
        help="Skip internet connectivity checks (use with caution - may cause false alerts)"
    )
    parser.add_argument(
        "--connectivity-wait", type=int, default=2,
        help="Minutes to wait for connectivity restoration (default: 2 min)"
    )
    
    args = parser.parse_args()
    
    # Handle one-shot mode
    if args.one_shot:
        args.count = 1
        logger.info("One-shot mode enabled - will run a single check and exit")
    
    logger.info("Starting monitoring script")
    
    # Initialization
    logger.info("Initializing database and sites configuration")
    init_db()
    logger.info("Loading sites to monitor")
    notifier = NotificationManager()
    
    freq = args.frequency
    report_interval = args.interval
    output_path = args.output
    max_checks = args.count
    skip_connectivity_check = args.skip_connectivity
    connectivity_wait_min = args.connectivity_wait
    
    # Log configuration
    connectivity_mode = "disabled" if skip_connectivity_check else f"enabled (wait: {connectivity_wait_min}min)"
    if max_checks:
        logger.info(f"Configuration loaded - Frequency: {freq} min, Report interval: {report_interval} h, "
                   f"Output: {output_path}, Max checks: {max_checks}, Connectivity check: {connectivity_mode}")
    else:
        logger.info(f"Configuration loaded - Frequency: {freq} min, Report interval: {report_interval} h, "
                   f"Output: {output_path}, Mode: continuous, Connectivity check: {connectivity_mode}")
    
    # Check counter for limited runs
    check_counter = 0
    last_connectivity_status = True  # Track connectivity changes for notifications
    
    def check_job():
        """Periodic check job - monitors all sites and sends alerts if needed"""
        nonlocal check_counter, last_connectivity_status
        check_counter += 1
        
        logger.info(f"Starting check job #{check_counter}" + 
                   (f" of {max_checks}" if max_checks else " (continuous mode)"))
        
        connectivity_ok = True
        
        try:
            # Check internet connectivity first (unless disabled)
            if not skip_connectivity_check:
                logger.debug("Checking internet connectivity...")
                connectivity_ok = check_internet_connectivity()
                
                if not connectivity_ok:
                    logger.warning("No internet connectivity detected")
                    
                    # Send notification if connectivity just failed
                    if last_connectivity_status:
                        send_connectivity_notification(notifier, connectivity_restored=False)
                    
                    # Log connectivity issue and try to wait for restoration
                    save_connectivity_log(connectivity_ok)
                    
                    logger.info(f"Attempting to wait for connectivity restoration ({connectivity_wait_min} minutes)...")
                    if wait_for_connectivity(max_wait_minutes=connectivity_wait_min):
                        logger.info("Connectivity restored during wait period")
                        connectivity_ok = True
                        
                        # Send restoration notification if connectivity was previously down
                        if not last_connectivity_status:
                            send_connectivity_notification(notifier, connectivity_restored=True)
                    else:
                        logger.warning(f"Connectivity not restored within {connectivity_wait_min} minutes, skipping site checks")
                        last_connectivity_status = connectivity_ok
                        return  # Skip this check cycle
                elif not last_connectivity_status:
                    # Connectivity was restored between checks
                    logger.info("Internet connectivity confirmed (was previously down)")
                    send_connectivity_notification(notifier, connectivity_restored=True)
                
                # Update connectivity status tracking
                last_connectivity_status = connectivity_ok
            
            # Proceed with site monitoring if connectivity is OK
            sites = load_sites()
            logger.debug(f"Loaded {len(sites)} sites to monitor")
            all_pages = []
            
            for site in sites:
                logger.debug(f"Exploring site: {site}")
                try:
                    site_results = explore_site(site)
                    all_pages.extend(site_results)
                    logger.debug(f"Site {site} exploration completed: {len(site_results)} pages")
                except Exception as e:
                    logger.error(f"Failed to explore site {site}: {e}")
                    continue
            
            if not all_pages:
                logger.warning("No pages were successfully checked")
                return
            
            # Save results with connectivity status
            ts = save_results(all_pages, connectivity_ok)
            ts, latest = get_latest_check()  
            logger.info(f"Results saved for timestamp: {ts}")
            
            # Generate HTML report with connectivity status
            generate_html_report(ts, latest, connectivity_ok, output_path)
            logger.debug(f"HTML report generated: {output_path}")
            
            # Send notification if there are failures
            fails = [p for p in latest if not p['ok']]
            if fails:
                logger.warning(f"Found {len(fails)} failed checks")
                
                # Create detailed failure message
                failure_details = []
                for p in fails[:10]:  # Limit to first 10 failures
                    status = p.get('status_code', '?')
                    if p.get('error'):
                        status = f"Error: {p['error'][:30]}"
                    failure_details.append(f"• {p['url']} → {status}")
                
                msg = "Sites DOWN:\n" + "\n".join(failure_details)
                if len(fails) > 10:
                    msg += f"\n... and {len(fails) - 10} more"
                
                # Add connectivity info if relevant
                if not connectivity_ok:
                    msg = "⚠️ Connectivity issues detected!\n\n" + msg
                
                notifier.system_notify("Monitoring Alert", msg, icon="dialog-warning")
            else:
                logger.info("All sites are healthy")

            # Log summary
            total_checked = len(all_pages)
            failed_count = len(fails)
            connectivity_icon = "✓" if connectivity_ok else "✗"
            
            logger.info(f"Check job #{check_counter} completed: {total_checked} pages checked, "
                       f"{failed_count} failures, connectivity: {connectivity_icon}")
            
        except Exception as e:
            logger.error(f"Error during check job #{check_counter}: {e}", exc_info=True)

    def report_job():
        """Report job - generates complete report and sends notification with action"""
        logger.info("Starting report job")
        try:
            # Get latest check data
            ts, pages = get_latest_check()
            if not pages:
                logger.warning("No check data available for report generation")
                return
            
            # Determine connectivity status from latest check
            # (This is a simplified approach - in practice you might want to query the DB)
            connectivity_ok = last_connectivity_status
            
            # Generate complete report and notify with action
            generate_html_report(ts, pages, connectivity_ok, output_path)
            logger.info(f"Complete report generated for {len(pages)} pages")
            
            # Calculate summary for notification
            failed_count = sum(1 for p in pages if not p['ok'])
            connectivity_status = "✓" if connectivity_ok else "✗"
            
            title = f"Monitoring Report - {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Send notification with action to open report
            send_report_notification(title, output_path)

            logger.info(f"Report notification sent: {len(pages)} pages, {failed_count} failures, "
                       f"connectivity: {connectivity_status}")
            
        except Exception as e:
            logger.error(f"Error during report job: {e}", exc_info=True)

    def run_limited_checks():
        """Run a limited number of checks and exit"""
        logger.info(f"Starting limited monitoring - will run {max_checks} check(s)")
        
        for i in range(max_checks):
            if i > 0:  # Don't wait before the first check
                logger.info(f"Waiting {freq} minutes before next check...")
                time.sleep(freq * 60)  # Convert minutes to seconds
            
            check_job()
        
        # Generate final report and notification
        logger.info("All checks completed, generating final report...")
        report_job()
        
        logger.info(f"Limited monitoring completed - {max_checks} check(s) finished")
        print(f"\nMonitoring completed: {max_checks} check(s) finished.")
        
        # Wait a bit for notification thread to complete
        time.sleep(2)

    def run_continuous_monitoring():
        """Run continuous monitoring with scheduling"""
        logger.info("Starting continuous monitoring daemon")
        
        # Run initial check immediately
        check_job()
        
        # Schedule periodic jobs
        schedule.every(freq).minutes.do(check_job)
        schedule.every(report_interval).hours.do(report_job)
        
        logger.info("Monitoring daemon started successfully")
        logger.info("Press Ctrl+C to stop monitoring")
        
        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping monitoring...")
            print("\nContinuous monitoring stopped.")

    # Choose execution mode based on arguments
    if max_checks:
        # Limited number of checks
        run_limited_checks()
    else:
        # Continuous monitoring
        run_continuous_monitoring()

if __name__ == "__main__":
    main()