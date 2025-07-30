#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zangbéto Website Crawler and Monitoring Module

This module provides comprehensive website monitoring capabilities including:
- Recursive website crawling with configurable depth
- HTTP health checks and response time measurement
- SQLite database storage for historical data
- HTML report generation with interactive charts
- Status code analysis and failure detection

The crawler explores websites by following internal links up to a specified depth,
measures response times, and tracks status codes for detailed monitoring reports.

Dependencies:
    - requests: HTTP client for web requests
    - beautifulsoup4: HTML parsing for link extraction
    - sqlite3: Database storage (built-in)
    - jinja2: Template rendering for reports
    - plotly: Interactive chart generation

Example:
    # Basic usage
    init_db()
    sites = load_sites("sites.txt")
    for site in sites:
        results = explore_site(site)
        timestamp = save_results(results)
    
    # Generate report
    ts, pages = get_latest_check()
    generate_html_report(ts, pages)
"""

import os
import time
import json
import sqlite3
import requests
import schedule
import plotly.graph_objs as go
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import Counter
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Tuple, Optional, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
DB_PATH = "history.db"
TEMPLATE_PATH = "templates"
TEMPLATE_NAME = "report_template.html"
OUTPUT_HTML = "rapport.html"
SITES_FILE = "sites.txt"
DEPTH = 2  # Website exploration depth
NOTIF_TITLE = "Zangbéto Monitor"
DEFAULT_TIMEOUT = 10  # Default HTTP timeout in seconds


def load_sites(file_path: str = SITES_FILE) -> List[str]:
    """
    Load website URLs from a text file.
    
    Reads URLs from a text file, one URL per line. Empty lines and
    whitespace are automatically handled.
    
    Args:
        file_path (str): Path to the file containing URLs. 
                        Defaults to SITES_FILE constant.
    
    Returns:
        List[str]: List of website URLs to monitor.
    
    Raises:
        FileNotFoundError: If the sites file doesn't exist.
        IOError: If the file cannot be read.
    
    Example:
        >>> sites = load_sites("my_sites.txt")
        >>> print(f"Loaded {len(sites)} sites to monitor")
    
    Note:
        The sites file should contain one URL per line:
        https://example.com
        https://mysite.org
        https://another-site.net
    """
    try:
        logger.debug(f"Loading sites from: {file_path}")
        with open(file_path, "r", encoding='utf-8') as f:
            sites = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(sites)} sites from {file_path}")
        return sites
    except FileNotFoundError:
        logger.error(f"Sites file not found: {file_path}")
        raise
    except IOError as e:
        logger.error(f"Error reading sites file {file_path}: {e}")
        raise


def extract_internal_links(base_url: str, html: str) -> Set[str]:
    """
    Extract internal links from HTML content.
    
    Parses HTML and extracts all internal links (same domain) for
    recursive crawling. Only returns links that belong to the same
    domain as the base URL.
    
    Args:
        base_url (str): The base URL of the page being parsed.
        html (str): HTML content to parse for links.
    
    Returns:
        Set[str]: Set of internal URLs found in the HTML.
    
    Example:
        >>> links = extract_internal_links("https://example.com", html_content)
        >>> print(f"Found {len(links)} internal links")
    
    Note:
        - Only extracts links with the same domain as base_url
        - Converts relative URLs to absolute URLs
        - Returns a set to avoid duplicates
        - Handles malformed URLs gracefully
    """
    try:
        logger.debug(f"Extracting internal links from: {base_url}")
        soup = BeautifulSoup(html, "html.parser")
        links = set()
        base_domain = urlparse(base_url).netloc
        
        for a_tag in soup.find_all("a", href=True):
            try:
                # Convert relative URLs to absolute
                full_url = urljoin(base_url, a_tag["href"])
                parsed_url = urlparse(full_url)
                
                # Only include internal links (same domain)
                if parsed_url.netloc == base_domain:
                    # Remove fragments and query parameters for cleaner URLs
                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    links.add(clean_url)
            except Exception as e:
                logger.debug(f"Skipping malformed link: {a_tag.get('href', '')}")
                continue
        
        logger.debug(f"Found {len(links)} internal links")
        return links
    except Exception as e:
        logger.error(f"Error extracting links from {base_url}: {e}")
        return set()


def check_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> Dict:
    """
    Perform HTTP health check on a single URL.
    
    Makes an HTTP GET request and measures response time, status code,
    and success status. Also extracts internal links if the response
    contains HTML content.
    
    Args:
        url (str): URL to check.
        timeout (int): Request timeout in seconds. Defaults to DEFAULT_TIMEOUT.
    
    Returns:
        Dict: Dictionary containing check results with keys:
            - url (str): The checked URL
            - status_code (int|None): HTTP status code or None if failed
            - response_time (float|None): Response time in seconds or None if failed
            - ok (bool): True if request was successful (2xx status)
            - error (str|None): Error message if request failed
            - links (List[str]): List of internal links found (if HTML)
    
    Example:
        >>> result = check_url("https://example.com")
        >>> if result['ok']:
        ...     print(f"Site is up! Response time: {result['response_time']}s")
        >>> else:
        ...     print(f"Site is down: {result['error']}")
    
    Note:
        - Only extracts links from HTML content types
        - Measures actual network response time
        - Handles various HTTP and network errors gracefully
    """
    logger.debug(f"Checking URL: {url}")
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        response_time = round(time.time() - start_time, 3)
        
        # Check if response is OK (2xx status codes)
        is_ok = response.ok
        
        # Extract internal links if content is HTML
        links = []
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            links = list(extract_internal_links(url, response.text))
        
        result = {
            "url": url,
            "status_code": response.status_code,
            "response_time": response_time,
            "ok": is_ok,
            "error": None,
            "links": links
        }
        
        log_level = logging.INFO if is_ok else logging.WARNING
        logger.log(log_level, f"URL check: {url} -> {response.status_code} ({response_time}s)")
        
        return result
        
    except requests.exceptions.Timeout:
        error_msg = f"Timeout after {timeout}s"
        logger.warning(f"URL check failed: {url} -> {error_msg}")
        return {
            "url": url,
            "status_code": None,
            "response_time": None,
            "ok": False,
            "error": error_msg,
            "links": []
        }
    except requests.exceptions.ConnectionError as e:
        error_msg = "Connection error"
        logger.warning(f"URL check failed: {url} -> {error_msg}")
        return {
            "url": url,
            "status_code": None,
            "response_time": None,
            "ok": False,
            "error": error_msg,
            "links": []
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error checking {url}: {error_msg}")
        return {
            "url": url,
            "status_code": None,
            "response_time": None,
            "ok": False,
            "error": error_msg,
            "links": []
        }


def explore_site(base_url: str, max_depth: int = DEPTH) -> List[Dict]:
    """
    Recursively explore a website by following internal links.
    
    Starts from a base URL and explores the site by following internal
    links up to a specified depth. Avoids visiting the same URL twice
    and collects health check data for each discovered page.
    
    Args:
        base_url (str): Starting URL for exploration.
        max_depth (int): Maximum depth to explore. Defaults to DEPTH constant.
    
    Returns:
        List[Dict]: List of check results for all discovered pages.
                   Each result follows the format from check_url().
    
    Example:
        >>> results = explore_site("https://example.com", max_depth=2)
        >>> total_pages = len(results)
        >>> failed_pages = sum(1 for r in results if not r['ok'])
        >>> print(f"Explored {total_pages} pages, {failed_pages} failed")
    
    Note:
        - Uses depth-first exploration strategy
        - Automatically avoids infinite loops by tracking visited URLs
        - Depth 0 = only base URL, depth 1 = base + direct links, etc.
        - Large sites may generate many requests - use appropriate depth
    """
    logger.info(f"Starting site exploration: {base_url} (max depth: {max_depth})")
    
    visited = set()
    results = []
    
    def _explore_recursive(url: str, current_depth: int) -> None:
        """
        Internal recursive function for site exploration.
        
        Args:
            url (str): Current URL to explore
            current_depth (int): Current exploration depth
        """
        # Stop if URL already visited or max depth exceeded
        if url in visited or current_depth > max_depth:
            return
        
        logger.debug(f"Exploring: {url} (depth {current_depth})")
        visited.add(url)
        
        # Check the current URL
        result = check_url(url)
        results.append(result)
        
        # If we haven't reached max depth and found links, explore them
        if current_depth < max_depth and result.get('links'):
            logger.debug(f"Found {len(result['links'])} links at depth {current_depth}")
            for link in result['links']:
                _explore_recursive(link, current_depth + 1)
    
    # Start recursive exploration
    _explore_recursive(base_url, 0)
    
    logger.info(f"Site exploration completed: {len(results)} pages discovered")
    return results


def init_db(db_path: str = DB_PATH) -> None:
    """
    Initialize the SQLite database for storing monitoring results.
    
    Creates the necessary tables if they don't exist:
    - checks: Stores check sessions with timestamps
    - pages: Stores individual page check results linked to check sessions
    
    Args:
        db_path (str): Path to the SQLite database file. 
                      Defaults to DB_PATH constant.
    
    Raises:
        sqlite3.Error: If database operations fail.
    
    Example:
        >>> init_db("monitoring.db")
        >>> print("Database initialized successfully")
    
    Note:
        - Safe to call multiple times (CREATE TABLE IF NOT EXISTS)
        - Creates foreign key relationship between checks and pages
        - Database file is created automatically if it doesn't exist
    """
    try:
        logger.info(f"Initializing database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create checks table for monitoring sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Create pages table for individual page results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                status_code INTEGER,
                response_time REAL,
                ok BOOLEAN,
                error TEXT,
                FOREIGN KEY(check_id) REFERENCES checks(id)
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Database initialization completed successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def save_results(results: List[Dict], db_path: str = DB_PATH) -> str:
    """
    Save monitoring results to the database.
    
    Creates a new check session and saves all page results with
    their associated status codes, response times, and errors.
    
    Args:
        results (List[Dict]): List of check results from explore_site() or check_url().
        db_path (str): Path to the SQLite database file.
                      Defaults to DB_PATH constant.
    
    Returns:
        str: ISO timestamp of the saved check session.
    
    Raises:
        sqlite3.Error: If database operations fail.
    
    Example:
        >>> results = explore_site("https://example.com")
        >>> timestamp = save_results(results)
        >>> print(f"Results saved with timestamp: {timestamp}")
    
    Note:
        - Creates a new check session for each save operation
        - All results are saved atomically (transaction)
        - Returns timestamp for reference and reporting
    """
    if not results:
        logger.warning("No results to save")
        return datetime.utcnow().isoformat()
    
    try:
        logger.info(f"Saving {len(results)} results to database")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create new check session
        timestamp = datetime.utcnow().isoformat()
        cursor.execute("INSERT INTO checks (timestamp) VALUES (?)", (timestamp,))
        check_id = cursor.lastrowid
        
        # Save all page results
        for result in results:
            cursor.execute("""
                INSERT INTO pages (check_id, url, status_code, response_time, ok, error)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                check_id,
                result["url"],
                result["status_code"],
                result["response_time"],
                result["ok"],
                result["error"]
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Results saved successfully with timestamp: {timestamp}")
        return timestamp
        
    except sqlite3.Error as e:
        logger.error(f"Failed to save results to database: {e}")
        raise


def get_latest_check(db_path: str = DB_PATH) -> Tuple[Optional[str], List[Dict]]:
    """
    Retrieve the most recent check results from the database.
    
    Gets the latest monitoring session and all associated page results
    for report generation and status checking.
    
    Args:
        db_path (str): Path to the SQLite database file.
                      Defaults to DB_PATH constant.
    
    Returns:
        Tuple[Optional[str], List[Dict]]: Tuple containing:
            - timestamp (str|None): ISO timestamp of the latest check or None if no data
            - pages (List[Dict]): List of page results with keys:
                - url (str): Page URL
                - status_code (int|None): HTTP status code
                - response_time (float|None): Response time in seconds
                - ok (bool): Success status
                - error (str|None): Error message if failed
    
    Example:
        >>> timestamp, pages = get_latest_check()
        >>> if timestamp:
        ...     failed = [p for p in pages if not p['ok']]
        ...     print(f"Latest check at {timestamp}: {len(failed)} failures")
        >>> else:
        ...     print("No check data available")
    """
    try:
        logger.debug("Retrieving latest check results")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the most recent check
        cursor.execute("SELECT id, timestamp FROM checks ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            logger.info("No check data found in database")
            conn.close()
            return None, []
        
        check_id, timestamp = row
        
        # Get all pages for this check
        cursor.execute("""
            SELECT url, status_code, response_time, ok, error 
            FROM pages 
            WHERE check_id = ?
        """, (check_id,))
        
        pages = []
        for url, status_code, response_time, ok, error in cursor.fetchall():
            pages.append({
                "url": url,
                "status_code": status_code,
                "response_time": response_time,
                "ok": bool(ok),
                "error": error
            })
        
        conn.close()
        
        logger.debug(f"Retrieved {len(pages)} pages from latest check ({timestamp})")
        return timestamp, pages
        
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve latest check: {e}")
        return None, []


def get_history_12h(db_path: str = DB_PATH) -> Tuple[List[str], List[int], List[int]]:
    """
    Generate hourly UP/DOWN statistics for the last 12 hours.
    
    Analyzes check history to create hourly buckets showing the number
    of successful vs failed page checks. Used for trend visualization
    in monitoring reports.
    
    Args:
        db_path (str): Path to the SQLite database file.
                      Defaults to DB_PATH constant.
    
    Returns:
        Tuple[List[str], List[int], List[int]]: Tuple containing:
            - labels (List[str]): Hour labels in HH:MM format
            - up_counts (List[int]): Number of successful checks per hour
            - down_counts (List[int]): Number of failed checks per hour
    
    Example:
        >>> labels, ups, downs = get_history_12h()
        >>> for i, label in enumerate(labels):
        ...     total = ups[i] + downs[i]
        ...     print(f"{label}: {ups[i]} up, {downs[i]} down ({total} total)")
    
    Note:
        - Groups results by hour (ignores minutes/seconds)
        - Only includes data from the last 12 hours
        - Empty hours (no checks) are not included in results
        - Useful for generating trend charts and identifying patterns
    """
    try:
        logger.debug("Generating 12-hour history statistics")
        
        # Calculate cutoff time (12 hours ago)
        cutoff = datetime.utcnow() - timedelta(hours=12)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all page results from the last 12 hours
        cursor.execute("""
            SELECT ch.timestamp, p.ok
            FROM pages p
            JOIN checks ch ON p.check_id = ch.id
            WHERE ch.timestamp >= ?
        """, (cutoff.isoformat(),))
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            logger.info("No history data found for the last 12 hours")
            return [], [], []
        
        # Group by hour
        hourly_stats = {}
        for timestamp_str, ok in data:
            try:
                # Parse timestamp and round to hour
                dt = datetime.fromisoformat(timestamp_str)
                hour = dt.replace(minute=0, second=0, microsecond=0)
                
                # Initialize hour stats if needed
                if hour not in hourly_stats:
                    hourly_stats[hour] = {"up": 0, "down": 0}
                
                # Count up/down
                if ok:
                    hourly_stats[hour]["up"] += 1
                else:
                    hourly_stats[hour]["down"] += 1
                    
            except ValueError as e:
                logger.warning(f"Skipping invalid timestamp: {timestamp_str}")
                continue
        
        # Sort hours and extract data
        sorted_hours = sorted(hourly_stats.keys())
        labels = [hour.strftime("%H:%M") for hour in sorted_hours]
        up_counts = [hourly_stats[hour]["up"] for hour in sorted_hours]
        down_counts = [hourly_stats[hour]["down"] for hour in sorted_hours]
        
        logger.debug(f"Generated history for {len(labels)} hours")
        return labels, up_counts, down_counts
        
    except sqlite3.Error as e:
        logger.error(f"Failed to generate history statistics: {e}")
        return [], [], []


def generate_html_report(timestamp: str, pages: List[Dict], output_path: str = OUTPUT_HTML) -> None:
    """
    Generate an HTML monitoring report with interactive charts.
    
    Creates a comprehensive HTML report including:
    - Current status overview with success/failure counts
    - Status code distribution chart
    - 12-hour trend analysis
    - Detailed page-by-page results
    
    Args:
        timestamp (str): Timestamp of the check being reported.
        pages (List[Dict]): List of page check results.
        output_path (str): Path where the HTML report should be saved.
                          Defaults to OUTPUT_HTML constant.
    
    Raises:
        jinja2.TemplateError: If template rendering fails.
        IOError: If the output file cannot be written.
    
    Example:
        >>> timestamp, pages = get_latest_check()
        >>> generate_html_report(timestamp, pages, "monitor_report.html")
        >>> print("Report generated successfully")
    
    Note:
        - Requires Jinja2 template in templates/report_template.html
        - Generates interactive charts using Plotly.js
        - Report includes both current status and historical trends
        - Output file can be opened directly in web browsers
    """
    try:
        logger.info(f"Generating HTML report for {len(pages)} pages")
        
        # Analyze status codes for current check
        status_codes = [p["status_code"] for p in pages if p["status_code"] is not None]
        status_counter = Counter(status_codes)
        status_labels = list(map(str, status_counter.keys()))
        status_counts = list(status_counter.values())
        
        # Get 12-hour history for trend chart
        history_labels, history_up, history_down = get_history_12h()
        
        # Calculate summary statistics
        total_pages = len(pages)
        successful_pages = sum(1 for p in pages if p['ok'])
        failed_pages = total_pages - successful_pages
        avg_response_time = None
        
        if pages:
            response_times = [p['response_time'] for p in pages if p['response_time'] is not None]
            if response_times:
                avg_response_time = round(sum(response_times) / len(response_times), 3)
        
        # Load and render template
        env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))
        template = env.get_template(TEMPLATE_NAME)
        
        html_content = template.render(
            # Basic info
            timestamp=timestamp,
            pages=pages,
            
            # Summary stats
            total_pages=total_pages,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            avg_response_time=avg_response_time,
            
            # Status code distribution
            status_labels=status_labels,
            status_counts=status_counts,
            
            # Historical trend data
            hist_labels=history_labels,
            hist_up=history_up,
            hist_down=history_down
        )
        
        # Write report to file
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated successfully: {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate HTML report: {e}")
        raise


def notify_if_fail(pages: List[Dict], title: str = NOTIF_TITLE) -> None:
    """
    Send system notification if any pages failed their health checks.
    
    Analyzes check results and sends a desktop notification listing
    all failed pages with their status codes or error messages.
    
    Args:
        pages (List[Dict]): List of page check results.
        title (str): Notification title. Defaults to NOTIF_TITLE constant.
    
    Example:
        >>> timestamp, pages = get_latest_check()
        >>> notify_if_fail(pages, "Website Monitor Alert")
    
    Note:
        - Only sends notification if there are failures
        - Uses system notify-send command (Linux desktop)
        - Lists up to 10 failed pages to avoid notification overflow
        - Gracefully handles notify-send unavailability
    """
    failed_pages = [p for p in pages if not p["ok"]]
    
    if not failed_pages:
        logger.debug("All pages are healthy, no notification needed")
        return
    
    try:
        logger.warning(f"Found {len(failed_pages)} failed pages, sending notification")
        
        # Limit to first 10 failures to avoid overwhelming notification
        display_failures = failed_pages[:10]
        more_failures = len(failed_pages) - len(display_failures)
        
        # Format failure list
        failure_list = []
        for page in display_failures:
            status = page.get('status_code', '?')
            if page.get('error'):
                status = f"Error: {page['error'][:30]}"
            failure_list.append(f"• {page['url']} → {status}")
        
        message = "Sites DOWN:\n" + "\n".join(failure_list)
        if more_failures > 0:
            message += f"\n... and {more_failures} more"
        
        # Send system notification
        os.system(f'notify-send "{title}" "{message}"')
        logger.info(f"Failure notification sent for {len(failed_pages)} failed pages")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def job() -> None:
    """
    Main monitoring job that performs a complete check cycle.
    
    Executes a full monitoring cycle including:
    1. Database initialization
    2. Loading sites to monitor
    3. Exploring each site recursively
    4. Saving results to database
    5. Generating HTML report
    6. Sending failure notifications
    
    This function is designed to be called by schedulers or as a standalone check.
    
    Example:
        >>> job()  # Run a single check cycle
        
        # Or schedule it
        >>> import schedule
        >>> schedule.every(30).minutes.do(job)
    
    Note:
        - Handles all errors gracefully to avoid breaking scheduled runs
        - Logs progress and timing information
        - Generates reports even if some sites fail
        - Safe to run concurrently (uses separate database connections)
    """
    start_time = time.time()
    logger.info("Starting monitoring job")
    
    try:
        # Initialize database
        init_db()
        
        # Load sites to monitor
        sites = load_sites()
        if not sites:
            logger.warning("No sites to monitor")
            return
        
        # Explore all sites
        all_pages = []
        for site in sites:
            logger.info(f"Exploring site: {site}")
            try:
                site_results = explore_site(site)
                all_pages.extend(site_results)
                logger.info(f"Site exploration completed: {len(site_results)} pages found")
            except Exception as e:
                logger.error(f"Failed to explore site {site}: {e}")
                continue
        
        if not all_pages:
            logger.warning("No pages to check")
            return
        
        # Save results
        timestamp = save_results(all_pages)
        
        # Get latest results for reporting
        _, latest_pages = get_latest_check()
        
        # Generate HTML report
        generate_html_report(timestamp, latest_pages)
        
        # Send notifications for failures
        notify_if_fail(latest_pages)
        
        # Log job completion
        elapsed_time = round(time.time() - start_time, 2)
        total_pages = len(all_pages)
        failed_pages = sum(1 for p in latest_pages if not p['ok'])
        
        logger.info(f"Monitoring job completed in {elapsed_time}s: "
                   f"{total_pages} pages checked, {failed_pages} failures")
        
        print(f"[{datetime.utcnow().isoformat()}] Check completed - "
              f"{total_pages} pages, {failed_pages} failures, report updated")
        
    except Exception as e:
        logger.error(f"Monitoring job failed: {e}", exc_info=True)


if __name__ == "__main__":
    """
    Standalone execution mode for the crawler module.
    
    When run directly, performs an immediate check and then schedules
    recurring checks every 30 minutes.
    """
    logger.info("Starting Zangbéto website monitoring service")
    
    try:
        # Run initial check immediately
        job()
        
        # Schedule recurring checks every 30 minutes
        schedule.every(30).minutes.do(job)
        logger.info("Monitoring scheduled every 30 minutes")
        
        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Monitoring service stopped by user")
        print("\nMonitoring service stopped.")
    except Exception as e:
        logger.error(f"Monitoring service crashed: {e}", exc_info=True)
        raise