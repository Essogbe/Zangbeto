#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zangbéto Website Crawler and Monitoring Module

This module provides comprehensive website monitoring capabilities including:
- Internet connectivity verification before checks
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
import subprocess
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
from typing import List, Dict, Tuple, Optional, Set, Union


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
DB_PATH = "history.db"
TEMPLATE_PATH = "templates"
TEMPLATE_NAME = "enhanced_report_template.html"
OUTPUT_HTML = "rapport.html"
SITES_FILE = "sites.txt"
DEPTH = 2  # Website exploration depth
NOTIF_TITLE = "Zangbéto Monitor"
DEFAULT_TIMEOUT = 10  # Default HTTP timeout in seconds


sqlite3.register_adapter(datetime, lambda dt: dt.isoformat(" "))
sqlite3.register_converter("timestamp", lambda s: datetime.fromisoformat(s.decode("utf-8")))


# Connectivity test endpoints (reliable services for internet check)
CONNECTIVITY_ENDPOINTS = [
    "https://www.google.com",
    "https://www.cloudflare.com",
    "https://httpbin.org/get",
    "https://www.github.com"
]




def check_internet_connectivity(timeout: int = 5, max_retries: int = 2) -> bool:
    """
    Verify internet connectivity before running site checks.
    
    Tests connectivity by attempting to reach multiple reliable endpoints.
    Uses a shorter timeout and multiple fallbacks to quickly determine
    if internet access is available.
    
    Args:
        timeout (int): Timeout for each connectivity test in seconds.
        max_retries (int): Maximum number of endpoints to try.
    
    Returns:
        bool: True if internet connectivity is available, False otherwise.
    
    Example:
        >>> if check_internet_connectivity():
        ...     print("Internet is available, proceeding with checks")
        ... else:
        ...     print("No internet connection, skipping checks")
    
    Note:
        - Tests multiple endpoints to avoid false negatives
        - Uses short timeout to fail fast
        - Logs connectivity status for debugging
        - Should be called before any site monitoring
    """
    logger.debug("Checking internet connectivity...")
    
    tested_endpoints = 0
    for endpoint in CONNECTIVITY_ENDPOINTS:
        if tested_endpoints >= max_retries:
            break
            
        try:
            tested_endpoints += 1
            logger.debug(f"Testing connectivity via: {endpoint}")
            
            response = requests.get(
                endpoint, 
                timeout=timeout,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                logger.info(f"Internet connectivity confirmed via {endpoint}")
                return True
                
        except (requests.exceptions.RequestException, Exception) as e:
            logger.debug(f"Connectivity test failed for {endpoint}: {e}")
            continue
    
    logger.error(f"No internet connectivity detected after testing {tested_endpoints} endpoints")
    return False


def wait_for_connectivity(max_wait_minutes: int = 10, check_interval: int = 30) -> bool:
    """
    Wait for internet connectivity to become available.
    
    Continuously checks for internet connectivity at regular intervals
    until it's available or the maximum wait time is reached.
    
    Args:
        max_wait_minutes (int): Maximum time to wait in minutes.
        check_interval (int): Interval between checks in seconds.
    
    Returns:
        bool: True if connectivity was established, False if timeout reached.
    
    Example:
        >>> if wait_for_connectivity(max_wait_minutes=5):
        ...     print("Connectivity restored, continuing with monitoring")
        ... else:
        ...     print("Connectivity timeout, skipping this check cycle")
    
    Note:
        - Useful for handling temporary network outages
        - Logs waiting progress for user awareness
        - Can be interrupted with KeyboardInterrupt
    """
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    logger.info(f"Waiting for internet connectivity (max {max_wait_minutes} minutes)...")
    
    while (time.time() - start_time) < max_wait_seconds:
        if check_internet_connectivity():
            wait_time = round(time.time() - start_time, 1)
            logger.info(f"Internet connectivity restored after {wait_time} seconds")
            return True
        
        logger.debug(f"Still no connectivity, waiting {check_interval}s before retry...")
        time.sleep(check_interval)
    
    logger.warning(f"Internet connectivity not restored within {max_wait_minutes} minutes")
    return False


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
    Ensures the 'connectivity_check' column exists in the 'checks' table.
    """
    try:

        sqlite3.register_adapter(datetime, lambda dt: dt.isoformat(" "))
        sqlite3.register_converter("timestamp", lambda s: datetime.fromisoformat(s.decode("utf-8")))
        logger.info(f"Initializing database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create checks table for monitoring sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL
            )
        """)

        # Add connectivity_check column if missing
        cursor.execute("PRAGMA table_info(checks)")
        columns = [row[1] for row in cursor.fetchall()]
        if "connectivity_check" not in columns:
            logger.info("Adding missing column 'connectivity_check' to 'checks' table")
            cursor.execute("ALTER TABLE checks ADD COLUMN connectivity_check BOOLEAN DEFAULT 1")

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


def save_results(results: List[Dict], connectivity_ok: bool = True, db_path: str = DB_PATH) -> str:
    """
    Save monitoring results to the database.
    
    Creates a new check session and saves all page results with
    their associated status codes, response times, and errors.
    
    Args:
        results (List[Dict]): List of check results from explore_site() or check_url().
        connectivity_ok (bool): Whether internet connectivity was available during check.
        db_path (str): Path to the SQLite database file.
                      Defaults to DB_PATH constant.
    
    Returns:
        str: ISO timestamp of the saved check session.
    
    Raises:
        sqlite3.Error: If database operations fail.
    
    Example:
        >>> results = explore_site("https://example.com")
        >>> timestamp = save_results(results, connectivity_ok=True)
        >>> print(f"Results saved with timestamp: {timestamp}")
    
    Note:
        - Creates a new check session for each save operation
        - All results are saved atomically (transaction)
        - Returns timestamp for reference and reporting
        - Records connectivity status for analysis
    """
    if not results:
        logger.warning("No results to save")
        return datetime.now().isoformat()

    try:
        logger.info(f"Saving {len(results)} results to database")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create new check session
        timestamp = datetime.now().isoformat()
        cursor.execute("INSERT INTO checks (timestamp, connectivity_check) VALUES (?, ?)",
                      (timestamp, connectivity_ok))
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

def get_hourly_stats(data:Tuple,db_path: str = DB_PATH) -> Tuple[List[str], List[int], List[int]]:
    """
    Generate hourly UP/DOWN statistics from check history.
    Analyzes check history to create hourly buckets showing the number
    of successful vs failed page checks. Used for trend visualization
    in monitoring reports. 

    Args:
        data (Tuple): Tuple containing:
            - timestamps (List[str]): List of ISO timestamps for checks
            - up_downs (List[bool]): List of booleans indicating success (True) or failure (False)
        db_path (str): Path to the SQLite database file.    
                        Defaults to DB_PATH constant.
    Returns:    
        Tuple[List[str], List[int], List[int]]: Tuple containing:
            - labels (List[str]): Hour labels in HH:MM format
            - up_counts (List[int]): Number of successful checks per hour
            - down_counts (List[int]): Number of failed checks per hour
    Example:
        >>> data = (["2023-10-01T12:00:00", "2023-10-01T12:30:00"], [True, False])
        >>> labels, ups, downs = get_hourly_stats(data)
        >>> for i, label in enumerate(labels):
        ...     print(f"{label}: {ups[i]} up, {downs[i]} down")
    

    """
    logger.info("Generating hourly statistics from check history")
    print(len(data))
    timestamps, up_downs = data[0], data[1]
    if not timestamps or not up_downs:
        logger.info("No valid data available for hourly stats")
        return [], [], []

    # Group by hour
    hourly_stats = {}
    for timestamp_str, ok in zip(timestamps, up_downs):
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
        cutoff = datetime.now() - timedelta(hours=12)
        
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




def human_history_period(start: Union[datetime, str], end: Optional[Union[datetime, str]], db_path: str = DB_PATH) -> List[Dict]:

    """    Retrieve check history for a specific time period.
    Fetches all checks and their results within the specified start and end times.
    Args:
        start (Union[datetime, str]): Start of the period to retrieve.
                                      Can be a datetime object or ISO string.
        end (Optional[Union[datetime, str]]): End of the period to retrieve.
                                    Can be a datetime object or ISO string.
        db_path (str): Path to the SQLite database file.
                      Defaults to DB_PATH constant.
                          
    Returns:
        List[Dict]: List of check results within the specified period.
                   Each result contains:
                   - timestamp (str): ISO timestamp of the check
                   - connectivity_check (bool): Whether connectivity was OK
                   - pages (List[Dict]): List of page results with keys:
                       - url (str): Page URL
                       - status_code (int|None): HTTP status code
                       - response_time (float|None): Response time in seconds
                       - ok (bool): Success status
                       - error (str|None): Error message if failed
    
    Example:
        >>> start = datetime(2023, 10, 1, 0, 0)
        >>> end = datetime(2023, 10, 2, 0, 0)
        >>> history = human_history_period(start, end)
        >>> print(f"Retrieved {len(history)} checks from {start} to {end}")
    
    Note:
        - Returns all checks within the specified period
        - Handles empty periods gracefully
        - Useful for generating reports or analyzing trends over time
    """
    PERIODS = {
    "today": (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0), datetime.now()),
    "yesterday": (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1),
                  datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)),
    "this_week": (datetime.now() - timedelta(days=datetime.now().weekday()), datetime.now()),
    "last_week": (datetime.now() - timedelta(days=datetime.now().weekday() + 7), datetime.now() - timedelta(days=datetime.now().weekday())),
    "this_month": (datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0), datetime.now()),
    "last_month": (datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1),
                   datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=datetime.now().day - 1)),
    "last_24h": (datetime.now() - timedelta(hours=24), datetime.now()),
    "last_7d": (datetime.now() - timedelta(days=7), datetime.now()),
    "last_30d": (datetime.now() - timedelta(days=30), datetime.now())
}
    if isinstance(start, str):
        if not end:
            match start:
                case "today":
                    start, end = PERIODS["today"]
                case "yesterday":
                    start, end = PERIODS["yesterday"]
                case "this_week":
                    start, end = PERIODS["this_week"]
                case "last_week":
                    start, end = PERIODS["last_week"]
                case "this_month":
                    start, end = PERIODS["this_month"]
                case "last_month":
                    start, end = PERIODS["last_month"]
                case "last_24h":
                    start, end = PERIODS["last_24h"]
                case "last_7d":
                    start, end = PERIODS["last_7d"]
                case "last_30d":
                    start, end = PERIODS["last_30d"]
                case _:
                    raise ValueError(f"Unknown period: {start}")
            return get_history_period(start, end, db_path)
    elif isinstance(start, datetime):
        if not end:
            end = datetime.now()
            return get_history_period(start, end, db_path)
        elif isinstance(end, datetime):
            return get_history_period(start, end, db_path)
        else:
            raise TypeError("End must be a datetime object or a valid period string")
    else:
        raise TypeError("Start must be a datetime object or a valid period string")

def get_history_period(start: datetime, end: datetime, db_path: str = DB_PATH) -> List[Dict]:
    """
    Retrieve check history for a specific time period.
    Fetches all checks and their results within the specified start and end times.
    Args:
        start (datetime): Start of the period to retrieve.
        end (datetime): End of the period to retrieve.
        db_path (str): Path to the SQLite database file.
                      Defaults to DB_PATH constant.
                          
    Returns:
        List[Dict]: List of check results within the specified period.
                   Each result contains:
                   - timestamp (str): ISO timestamp of the check
                   - connectivity_check (bool): Whether connectivity was OK
                   - pages (List[Dict]): List of page results with keys:
                       - url (str): Page URL
                       - status_code (int|None): HTTP status code
                       - response_time (float|None): Response time in seconds
                       - ok (bool): Success status
                       - error (str|None): Error message if failed
    
    Example:
        >>> start = datetime(2023, 10, 1, 0, 0)
        >>> end = datetime(2023, 10, 2, 0, 0)
        >>> history = get_history_period(start, end)
        >>> print(f"Retrieved {len(history)} checks from {start} to {end}")
    
    Note:
        - Returns all checks within the specified period
        - Handles empty periods gracefully
        - Useful for generating reports or analyzing trends over time
    """
    try:
        logger.info(f"Retrieving history from {start.isoformat()} to {end.isoformat()}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all checks within the specified period
        cursor.execute("""
            SELECT ch.timestamp, ch.connectivity_check, p.url, p.status_code,
                   p.response_time, p.ok, p.error
            FROM checks ch
            JOIN pages p ON ch.id = p.check_id
            WHERE ch.timestamp >= ? AND ch.timestamp <= ?
            ORDER BY ch.timestamp DESC
        """, (start.isoformat(), end.isoformat()))
        
        data = cursor.fetchall()
        conn.close()
        #print(data)
        print(len(data), "rows found in the database for the specified period")

        if not data:
            logger.info("No history data found for the specified period")
            return []
        
        # Organize results by check session
        history = []
        current_check = None
        urls = set()
        
        for row in data:
            
            timestamp, connectivity_check, url, status_code, response_time, ok, error = row
            urls.add(url)
            if current_check is None or current_check['timestamp'] != timestamp:
                if current_check is not None:
                    history.append(current_check)
                
                current_check = {
                    "timestamp": timestamp,
                    "connectivity_check": connectivity_check,
                    "pages": []
                }
            
            current_check['pages'].append({
                "url": url,
                "status_code": status_code,
                "response_time": response_time,
                "ok": bool(ok),
                "error": error
            })
        
        # Add the last check if it exists
        if current_check is not None:
            history.append(current_check)
        
        logger.debug(f"Retrieved {len(history)} checks from history")
        logger.info(f"Found {len(urls)} unique URLs in the history")
        return history
        
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve history: {e}")
        return []

def generate_html_report(timestamp: str, pages: List[Dict], connectivity_ok: bool = True, output_path: str = OUTPUT_HTML, hourly_stats: Optional[Tuple[List[str], List[int], List[int]]] = None) -> None:
    """
    Generate an HTML monitoring report with interactive charts.
    
    Creates a comprehensive HTML report including:
    - Current status overview with success/failure counts
    - Status code distribution chart
    - Detailed page-by-page results
    - Connectivity status indicator
    
    Args:
        timestamp (str): Timestamp of the check being reported.
        pages (List[Dict]): List of page check results.
        connectivity_ok (bool): Whether internet connectivity was available.
        output_path (str): Path where the HTML report should be saved.
                          Defaults to OUTPUT_HTML constant.
    
    Raises:
        jinja2.TemplateError: If template rendering fails.
        IOError: If the output file cannot be written.
    
    Example:
        >>> timestamp, pages = get_latest_check()
        >>> generate_html_report(timestamp, pages, True, "monitor_report.html")
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
        
        # Get 12-hour history for trend chart if hourly_stats not provided
        if hourly_stats is None:
            history_labels, history_up, history_down = get_history_12h()
        else:
            if hourly_stats is not None:
                history_labels, history_up, history_down = hourly_stats
            else:
                history_labels, history_up, history_down = [], [], []
            
       
        
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
            connectivity_ok=connectivity_ok,
            
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


def notify_if_fail(pages: List[Dict], connectivity_ok: bool = True, title: str = NOTIF_TITLE) -> None:
    """
    Send system notification if any pages failed their health checks.
    
    Analyzes check results and sends a desktop notification listing
    all failed pages with their status codes or error messages.
    Includes connectivity status in the notification.
    
    Args:
        pages (List[Dict]): List of page check results.
        connectivity_ok (bool): Whether internet connectivity was available.
        title (str): Notification title. Defaults to NOTIF_TITLE constant.
    
    Example:
        >>> timestamp, pages = get_latest_check()
        >>> notify_if_fail(pages, True, "Website Monitor Alert")
    
    Note:
        - Only sends notification if there are failures or connectivity issues
        - Uses system notify-send command (Linux desktop)
        - Lists up to 10 failed pages to avoid notification overflow
        - Gracefully handles notify-send unavailability
        - Distinguishes between connectivity and site-specific failures
    """
    failed_pages = [p for p in pages if not p["ok"]]
    
    # No notification needed if everything is fine
    if not failed_pages and connectivity_ok:
        logger.debug("All pages are healthy and connectivity is good, no notification needed")
        return
    
    try:
        # Prepare notification message
        message_parts = []
        
        # Add connectivity warning if needed
        if not connectivity_ok or failed_pages:
            # Prepare a list of failed page details (limit to 10)
            failure_list = [
                f"{p['url']} ({p['status_code'] if p['status_code'] is not None else p['error']})"
                for p in failed_pages
            ]
            max_display = 10
            displayed_failures = failure_list[:max_display]
            more_failures = len(failure_list) - max_display if len(failure_list) > max_display else 0

            if not connectivity_ok:
                message_parts.append("Internet connectivity issue detected.")
            if failed_pages:
                message_parts.append("Sites DOWN:\n" + "\n".join(displayed_failures))
                if more_failures > 0:
                    message_parts.append(f"... and {more_failures} more")
        
        message = "\n".join(message_parts)
        
        # Send system notification asynchronously
        logger.info(f"Sending notification: {title} - {message}")
        
        # Use subprocess to call notify-send (Linux desktop notification)
        # This will not block the main thread
        subprocess.Popen(["notify-send", title, message])

        if failed_pages:
            logger.info(f"Failure notification sent for {len(failed_pages)} failed pages")
        if not connectivity_ok:
            logger.info("Connectivity issue notification sent")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def save_connectivity_log(connectivity_ok: bool, db_path: str = DB_PATH) -> None:
    """
    Save connectivity check result even when no site checks are performed.
    
    Records connectivity status in the database for tracking network
    availability patterns and debugging monitoring issues.
    
    Args:
        connectivity_ok (bool): Whether internet connectivity was available.
        db_path (str): Path to the SQLite database file.
    
    Example:
        >>> save_connectivity_log(False)  # Log connectivity failure
    
    Note:
        - Creates a check record with no associated pages
        - Useful for tracking network outages
        - Helps distinguish between site failures and connectivity issues
    """
    try:
        logger.debug(f"Logging connectivity status: {connectivity_ok}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create check record with connectivity status
        timestamp = datetime.utcnow().isoformat()
        cursor.execute("INSERT INTO checks (timestamp, connectivity_check) VALUES (?, ?)", 
                      (timestamp, connectivity_ok))
        
        conn.commit()
        conn.close()
        
        logger.debug("Connectivity status logged successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Failed to log connectivity status: {e}")


def job() -> None:
    """
    Main monitoring job that performs a complete check cycle.
    
    Executes a full monitoring cycle including:
    1. Internet connectivity verification
    2. Database initialization
    3. Loading sites to monitor
    4. Exploring each site recursively (if connectivity is available)
    5. Saving results to database
    6. Generating HTML report
    7. Sending failure notifications
    
    This function is designed to be called by schedulers or as a standalone check.
    Includes connectivity checking to avoid false positives when internet is unavailable.
    
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
        - Skips site checks if no internet connectivity is detected
    """
    start_time = time.time()
    logger.info("Starting monitoring job")
    
    try:
        # Check internet connectivity first
        connectivity_ok = check_internet_connectivity()
        
        if not connectivity_ok:
            logger.warning("No internet connectivity detected, skipping site checks")
            
            # Initialize database and save connectivity status
            init_db()
            save_connectivity_log(connectivity_ok)
            
            # Send notification about connectivity issue
            notify_if_fail([], connectivity_ok)
            
            # Try to wait for connectivity (optional)
            logger.info("Attempting to wait for connectivity...")
            if wait_for_connectivity(max_wait_minutes=2):
                logger.info("Connectivity restored, proceeding with checks")
                connectivity_ok = True
            else:
                logger.warning("Connectivity not restored, skipping this check cycle")
                elapsed_time = round(time.time() - start_time, 2)
                print(f"[{datetime.utcnow().isoformat()}] Check skipped - no internet connectivity ({elapsed_time}s)")
                return
        
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
        
        # Save results with connectivity status
        timestamp = save_results(all_pages, connectivity_ok)
        
        # Get latest results for reporting
        _, latest_pages = get_latest_check()
        
        # Generate HTML report with connectivity status
        generate_html_report(timestamp, latest_pages, connectivity_ok)
        
        # Send notifications for failures or connectivity issues
        notify_if_fail(latest_pages, connectivity_ok)
        
        # Log job completion
        elapsed_time = round(time.time() - start_time, 2)
        total_pages = len(all_pages)
        failed_pages = sum(1 for p in latest_pages if not p['ok'])
        
        connectivity_status = "✓" if connectivity_ok else "✗"
        logger.info(f"Monitoring job completed in {elapsed_time}s: "
                   f"{total_pages} pages checked, {failed_pages} failures, "
                   f"connectivity: {connectivity_status}")
        
        print(f"[{datetime.utcnow().isoformat()}] Check completed - "
              f"{total_pages} pages, {failed_pages} failures, "
              f"connectivity: {connectivity_status}, report updated")
        
    except Exception as e:
        logger.error(f"Monitoring job failed: {e}", exc_info=True)
def generate_enhanced_html_report(timestamp: str, pages: List[Dict], 
                                connectivity_ok: bool = True, 
                                output_path: str = OUTPUT_HTML, 
                                hourly_stats: Optional[Tuple[List[str], List[int], List[int]]] = None) -> None:
    """
    Generate an enhanced HTML monitoring report with detailed site analysis.
    
    Creates a comprehensive HTML report including:
    - Site-by-site analysis with success rates and metrics
    - Current status overview with success/failure counts  
    - Status code distribution per site
    - Historical trends per site (if data available)
    - Detailed page-by-page results grouped by domain
    - Connectivity status indicator
    
    Args:
        timestamp (str): Timestamp of the check being reported.
        pages (List[Dict]): List of page check results.
        connectivity_ok (bool): Whether internet connectivity was available.
        output_path (str): Path where the HTML report should be saved.
        hourly_stats (Optional[Tuple]): Optional hourly statistics data.
    
    Raises:
        jinja2.TemplateError: If template rendering fails.
        IOError: If the output file cannot be written.
    """
    try:
        logger.info(f"Generating enhanced HTML report for {len(pages)} pages")
        
        # Analyze current check by site
        site_stats = analyze_by_site(pages)
        
        # Get historical data for the last 12 hours for site trends
        period_data = []
        try:
            cutoff = datetime.now() - timedelta(hours=12)
            period_data = get_history_period(cutoff, datetime.now())
        except Exception as e:
            logger.warning(f"Could not retrieve historical data: {e}")
        
        # Analyze historical data if available
        historical_stats = {}
        site_trends = {}
        if period_data:
            historical_stats = analyze_historical_data(period_data)
            site_trends = calculate_site_trends(period_data)
        
        # Get 12-hour history for global trend chart if hourly_stats not provided
        if hourly_stats is None:
            history_labels, history_up, history_down = get_history_12h()
        else:
            history_labels, history_up, history_down = hourly_stats
        
        # Calculate global summary statistics
        total_pages = len(pages)
        successful_pages = sum(1 for p in pages if p['ok'])
        failed_pages = total_pages - successful_pages
        overall_success_rate = (successful_pages / total_pages * 100) if total_pages > 0 else 0
        
        avg_response_time = 0
        if pages:
            response_times = [p['response_time'] for p in pages if p['response_time'] is not None]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        # Load and render enhanced template
        env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))
        template = env.get_template("enhanced_report_template.html")
        
        html_content = template.render(
            # Basic info
            timestamp=timestamp,
            period_label=f"Check du {timestamp}",
            pages=pages,
            connectivity_ok=connectivity_ok,
            
            # Site analysis
            site_stats=site_stats,
            site_trends=site_trends,
            historical_stats=historical_stats,
            
            # Global summary stats
            total_pages=total_pages,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            overall_success_rate=overall_success_rate,
            avg_response_time=avg_response_time,
            
            # Historical trend data (global)
            hist_labels=history_labels,
            hist_up=history_up,
            hist_down=history_down
        )
        
        # Write report to file
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Enhanced HTML report generated successfully: {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate enhanced HTML report: {e}")
        raise

def analyze_by_site(pages: List[Dict]) -> Dict:
    """Analyze current check results grouped by site/domain."""
    from urllib.parse import urlparse
    
    site_stats = {}
    urls = set()
    for page in pages:
        domain = urlparse(page['url']).netloc
        urls.add(page['url'])

        if domain not in site_stats:
            site_stats[domain] = {
                'total_pages': 0,
                'successful_pages': 0,
                'failed_pages': 0,
                'avg_response_time': 0,
                'status_codes': Counter(),
                'errors': [],
                'pages': []
            }
        
        stats = site_stats[domain]
        stats['total_pages'] += 1
        stats['pages'].append(page)
        
        if page['ok']:
            stats['successful_pages'] += 1
        else:
            stats['failed_pages'] += 1
            if page['error']:
                stats['errors'].append(page['error'])
        
        if page['status_code']:
            stats['status_codes'][page['status_code']] += 1
        
        if page['response_time']:
            # Calculate running average
            current_avg = stats['avg_response_time']
            n = stats['total_pages']
            stats['avg_response_time'] = (current_avg * (n-1) + page['response_time']) / n
    
    # Calculate success rates
    for domain, stats in site_stats.items():
        if stats['total_pages'] > 0:
            stats['success_rate'] = (stats['successful_pages'] / stats['total_pages']) * 100
        else:
            stats['success_rate'] = 0
    logger.info(f"Analyzed {len(site_stats)} sites with {len(urls)} unique URLs")
    return site_stats

def analyze_historical_data(period_data: List[Dict]) -> Dict:
    """Analyze historical data for trends and patterns."""
    from urllib.parse import urlparse
    
    site_history = {}
    hourly_global = {}
    
    for check in period_data:
        timestamp = check['timestamp']
        dt = datetime.fromisoformat(timestamp)
        hour_key = dt.replace(minute=0, second=0, microsecond=0)
        
        # Global hourly stats
        if hour_key not in hourly_global:
            hourly_global[hour_key] = {'up': 0, 'down': 0, 'total': 0}
        
        for page in check['pages']:
            domain = urlparse(page['url']).netloc
            
            # Site-specific history
            if domain not in site_history:
                site_history[domain] = {
                    'hourly_stats': {},
                    'total_checks': 0,
                    'successful_checks': 0,
                    'response_times': [],
                    'incidents': []
                }
            
            site_stats = site_history[domain]
            site_stats['total_checks'] += 1
            
            # Hourly stats per site
            if hour_key not in site_stats['hourly_stats']:
                site_stats['hourly_stats'][hour_key] = {'up': 0, 'down': 0}
            
            if page['ok']:
                site_stats['successful_checks'] += 1
                site_stats['hourly_stats'][hour_key]['up'] += 1
                hourly_global[hour_key]['up'] += 1
            else:
                site_stats['hourly_stats'][hour_key]['down'] += 1
                hourly_global[hour_key]['down'] += 1
                
                # Record incident
                site_stats['incidents'].append({
                    'timestamp': timestamp,
                    'url': page['url'],
                    'error': page['error'],
                    'status_code': page['status_code']
                })
            
            hourly_global[hour_key]['total'] += 1
            
            if page['response_time']:
                site_stats['response_times'].append(page['response_time'])
    
    # Calculate availability percentages
    for domain, stats in site_history.items():
        if stats['total_checks'] > 0:
            stats['availability'] = (stats['successful_checks'] / stats['total_checks']) * 100
        else:
            stats['availability'] = 0
        
        if stats['response_times']:
            stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
        else:
            stats['avg_response_time'] = 0
    
    return {
        'by_site': site_history,
        'global_hourly': hourly_global
    }

def calculate_site_trends(period_data: List[Dict]) -> Dict:
    """Calculate trends for each site over time."""
    from urllib.parse import urlparse
    
    site_trends = {}
    
    for check in period_data:
        for page in check['pages']:
            domain = urlparse(page['url']).netloc
            
            if domain not in site_trends:
                site_trends[domain] = {
                    'timestamps': [],
                    'success_rates': [],
                    'response_times': [],
                    'status_timeline': []
                }
            
            trends = site_trends[domain]
            trends['timestamps'].append(check['timestamp'])
            trends['status_timeline'].append(1 if page['ok'] else 0)
            
            if page['response_time']:
                trends['response_times'].append(page['response_time'])
            else:
                trends['response_times'].append(None)
    
    return site_trends


generate_html_report = generate_enhanced_html_report

if __name__ == "__main__":
    """
    Standalone execution mode for the crawler module.
    
    When run directly, performs an immediate check and then schedules
    recurring checks every 30 minutes. Includes connectivity checking
    to handle network outages gracefully.
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
        raise Exception("Internet connectivity issues detected!")
