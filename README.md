# Zangbéto – Night Guardian

<p align="center">
<img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcREvNSSk-Op-0QgGDqch5TZujeZ2Ys-q6hZaw&s" alt="Zangbéto – Night Guardian" width="600"/>
</p>

[Zangbéto](https://en.wikipedia.org/wiki/Zangbeto) is a lightweight and local website monitoring tool. It periodically checks the availability of static and dynamic pages, generates detailed HTML reports with **site-by-site analysis**, and sends intelligent notifications when incidents occur or connectivity is restored.

## How It Works

Zangbéto operates as a **recursive web crawler** that monitors your websites' health automatically. Here's what happens during each monitoring cycle:

1. **Connectivity Check**: Before each monitoring cycle, verifies internet connectivity using multiple reliable endpoints to avoid false alerts during network outages

2. **Site Discovery**: Starting from your configured URLs (in `sites.txt`), Zangbéto explores each website by following internal links up to a configurable depth (default: 2 levels)

3. **Health Checks**: For every discovered page, it performs HTTP requests measuring:
   - Response time (how fast your site responds)
   - Status codes (200 OK, 404 Not Found, 500 errors, etc.)
   - Availability (can the page be reached?)

4. **Data Storage**: All results are stored in a local SQLite database with timestamps and connectivity status, creating a comprehensive historical record

5. **Enhanced Report Generation**: After each check, generates an interactive HTML report featuring:
   - **Site-by-site analysis** with individual success rates and metrics
   - **Global overview** with total success/failure statistics
   - **Status code distribution per domain** (pie charts)
   - **Historical trends per site** showing evolution over time
   - **Incident tracking** with recent failures per domain
   - **12-hour trend analysis** (up/down over time)
   - **Detailed page-by-page results** grouped by domain

6. **Smart Notifications**: 
   - **Instant alerts** for site failures with detailed error information
   - **Connectivity alerts** when internet connection is lost/restored
   - **Scheduled reports** (every 12 hours by default) with clickable notifications
   - **Multi-channel support**: system notifications, email, Slack, Telegram

**Example scenario**: You add `https://mycompany.com` to your sites list. Zangbéto will check the homepage, then follow links to `/about`, `/contact`, `/products`, etc., testing each page every 30 minutes. The enhanced report shows each domain separately with individual success rates, recent incidents, and trends. If connectivity is lost, you'll be notified and monitoring will pause until restored.

## 📦 Tech Stack

* **Language**: Python 3+
* **HTTP**: `requests`
* **Parsing**: `BeautifulSoup4`
* **Scheduling**: `schedule` (portability)
* **Database**: SQLite (`sqlite3`)
* **Templates**: Jinja2
* **Charts**: Plotly.js (via CDN)
* **Notifications**: Multi-channel via `notify.py` (system, email, Slack, Telegram)
* **Linux Supervision**: systemd (unit + timer)

**Note**: `notify-send` is available on Linux desktops (default on most distributions)

### Installing notify-send

**Ubuntu**
```bash
sudo apt install libnotify-bin
```

**Fedora**
```bash
sudo dnf install libnotify
```

**Arch Linux**
```bash
sudo pacman -Sy libnotify
```

## Project Structure

```
Zangbeto/
├── main.py                          # Main script and CLI with advanced options
├── crawler.py                       # Web exploration, HTTP tests, enhanced reporting
├── notify.py                        # Multi-channel notification manager
├── templates/
│   ├── report_template.html         # Legacy template (simple)
│   └── enhanced_report_template.html # New enhanced template (site-by-site)
├── history.db                       # SQLite database for check history
├── requirements.txt                 # Python dependencies
├── setup.sh                         # Automated setup and systemd configuration
└── README.md                        # Documentation and usage guide
```

## Quick Start Guide

1. **Clone and setup**:
   ```bash
   git clone https://github.com/yourusername/zangbeto
   cd zangbeto
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure sites** - Create `sites.txt`:
   ```bash
   echo "https://your-website.com" > sites.txt
   echo "https://your-api.com" >> sites.txt
   ```

3. **Test the setup**:
   ```bash
   # Quick test - single check with enhanced report
   python main.py --one-shot
   ```

4. **Start monitoring**:
   ```bash
   # Continuous monitoring with enhanced reporting
   python main.py
   ```

That's it! Open the generated `rapport.html` in your browser to see the enhanced monitoring results with site-by-site analysis.

## Configuration

### Sites Configuration
Create a `sites.txt` file with URLs to monitor (one per line):
```
https://example.com
https://mycompany.org
https://api.myservice.net
```

### CLI Arguments

**Basic Options:**
* `-f`, `--frequency`: Check interval in minutes (default: 30)
* `-o`, `--output`: HTML report file path (default: `rapport.html`)
* `-i`, `--interval`: Interval in hours for complete report notifications (default: 12)

**Execution Modes:**
* `-c`, `--count`: Run a specific number of check cycles then exit (default: infinite)
* `--one-shot`: Run a single check and exit (equivalent to `--count 1`)

**Connectivity Options:**
* `--skip-connectivity`: Skip internet connectivity checks (use with caution)
* `--connectivity-wait`: Minutes to wait for connectivity restoration (default: 2)

**Historical Analysis:**
* `--history`: Enable historical data retrieval mode
* `--start`: Start date for historical data (ISO format or predefined: today, yesterday, last_7d, last_30d, etc.)
* `--end`: End date for historical data (ISO format, optional)

### Environment Variables (Optional)
For extended notifications, create a `.env` file:
```bash
# Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Slack notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Telegram notifications
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

## Usage

### Continuous Monitoring 
```bash
# Start continuous monitoring with enhanced reports
python main.py

# Custom frequency - check every 10 minutes
python main.py --frequency 10

# Custom report interval - send reports every 6 hours
python main.py --interval 6

# Monitor with custom connectivity settings
python main.py --connectivity-wait 5
```

### Limited Monitoring (Testing)
```bash
# Quick test - single check with enhanced report
python main.py --one-shot

# Run exactly 5 check cycles then exit
python main.py --count 5

# Test with custom settings and enhanced reporting
python main.py --one-shot --frequency 1 --output enhanced_test.html
```

### Historical Analysis
```bash
# Generate report for the last 7 days
python main.py --history --start last_7d

# Generate report for a specific period
python main.py --history --start 2023-10-01T00:00:00 --end 2023-10-07T23:59:59

# Generate report for predefined periods
python main.py --history --start today
python main.py --history --start yesterday
python main.py --history --start last_30d
```

### Output Examples
* **Enhanced Reports**: Interactive HTML files with site-by-site analysis, trends, and incident tracking
* **Smart Notifications**: 
  - Instant alerts for site failures with detailed error info
  - Connectivity status notifications (lost/restored)
  - Clickable report notifications that open in browser
* **Console**: Real-time progress with connectivity status and detailed logging

**Example console output:**
```
2025-01-30 10:30:15 - INFO - Starting check job #1 of 3
2025-01-30 10:30:16 - INFO - Internet connectivity confirmed via https://www.google.com
2025-01-30 10:30:18 - INFO - Loaded 2 sites to monitor
2025-01-30 10:30:22 - INFO - Site exploration completed: 8 pages found
2025-01-30 10:30:23 - INFO - Analyzed 2 sites with 8 unique URLs
2025-01-30 10:30:23 - INFO - All sites are healthy
2025-01-30 10:30:24 - INFO - Enhanced HTML report generated successfully
```

## 🔧 systemd Integration (Linux)

For background execution with automatic startup and management:

**Automated Setup:**
```bash
chmod +x setup.sh
sudo ./setup.sh
```

**Manual Setup:**
1. **Create service files**:
   ```bash
   sudo cp systemd/zangbeto.service /etc/systemd/system/
   sudo cp systemd/zangbeto.timer /etc/systemd/system/
   ```

2. **Enable and start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable zangbeto.timer
   sudo systemctl start zangbeto.timer
   ```

3. **Monitor and manage**:
   ```bash
   # Check timer status
   systemctl list-timers --all | grep zangbeto
   
   # View logs with connectivity info
   journalctl -u zangbeto.service -f
   
   # Manual run
   sudo systemctl start zangbeto.service
   ```

## Key Features & Improvements

###  Enhanced Reporting
- **Site-by-site analysis** with individual success rates and response times
- **Visual availability badges** (high/medium/low availability)
- **Status code distribution per domain** with color-coded pie charts
- **Historical trend analysis per site** showing evolution over time
- **Recent incident tracking** with detailed error information
- **Responsive design** optimized for desktop and mobile viewing

###  Smart Connectivity Handling
- **Pre-check connectivity verification** using multiple reliable endpoints
- **Automatic waiting** for connectivity restoration (configurable timeout)
- **Connectivity status notifications** (lost/restored alerts)
- **Database logging** of connectivity issues for analysis
- **Graceful degradation** during network outages

###  Historical Analysis
- **Flexible date range queries** with predefined periods (today, yesterday, last_7d, etc.)
- **Historical report generation** with custom time ranges
- **Trend analysis** showing site performance over time
- **Incident correlation** across different time periods

###  Advanced Notifications
- **Multi-channel notification system** (system, email, Slack, Telegram)
- **Intelligent failure alerts** with detailed error information
- **Connectivity status notifications** for network issues
- **Clickable report notifications** that open reports in browser
- **Asynchronous notification handling** to avoid blocking main process

###  Enhanced Data Management
- **Connectivity status tracking** in database schema
- **Improved data organization** with proper foreign key relationships
- **Automatic database migration** for existing installations
- **Comprehensive logging** with debug information

## What About Testing APIs (REST APIs for Now)?

That's a great question because nowadays, most modern web applications are split into two main components: the backend (API) and the frontend.

When it comes to monitoring or testing APIs in production, there are generally two main approaches:

1. **Direct API testing**, where requests are made directly to the live endpoints.  
   This method carries risks such as:
   - Modifying production data
   - Triggering authentication or authorization issues  
   While manageable, it can raise security and data integrity concerns.

2. **Internal health-check endpoints**, where one or more special routes are created specifically for monitoring purposes.  
   These endpoints:
   - Perform internal checks on other routes or logic
   - Return a summary or detailed result about system health  

The second approach is often safer and cleaner:
- No side effects on production data
- Fewer security concerns
- Easier to automate and monitor

Future versions of this project aim to support both website and API monitoring, including health-check mechanisms for REST APIs.

## Alternatives

Yeah, there are plenty of alternatives out there. For medium to large teams, robust monitoring and alerting tools like **[Grafana](https://github.com/grafana/grafana)**, **[Prometheus](https://github.com/prometheus/prometheus)**, and others are already widely used—and they do their job very well.

This project is not meant to be a drop-in replacement for those tools (just look at how small it is, haha). Instead, it's a lightweight solution I built to quickly check if my websites are down, even quietly in the background.

That said, I'm always open to better suggestions and contributions.

## 📝 Roadmap (v2+)

**Core Improvements:**
* ✅ **Enhanced site-by-site reporting** (v1.1)
* ✅ **Smart connectivity handling** (v1.1)
* ✅ **Historical data analysis** (v1.1)
* ✅ **Multi-channel notifications** (v1.1)
* Unit tests and CI/CD pipeline
* Asynchronous crawler for better performance
* Dynamic pages support (Playwright/Selenium)
* Advanced retry logic and timeout handling

**Reporting & Visualization:**
* ✅ **Improved UI with site-by-site analysis** (v1.1)
* ✅ **Incident tracking and trends** (v1.1)
* Automatic PDF export
* Real-time web dashboard (Flask/React)
* Custom alert thresholds and rules
* SLA tracking and uptime calculations
* Custom templates definition and usage

**Notifications & Integrations:**
* ✅ **Multi-channel support (Email, Slack, Telegram)** (v1.1)
* ✅ **Smart connectivity notifications** (v1.1)
* Other channels support (SMS, Discord, Teams)
* Webhook support for custom integrations
* Alert escalation policies
* Maintenance windows and alert suppression

**Other Features:**
* Multi-user authentication and role management
* API monitoring with JSON/XML validation
* Protected sites monitoring (login flows)

**Platform & Deployment:**
* Windows support and native installers

**Data Management:**
* ✅ **Enhanced database schema with connectivity tracking** (v1.1)
* ✅ **Flexible historical data queries** (v1.1)
* Advanced retention policies and data purging 
* Performance metrics and trends analysis

---

*Zangbéto – Version 1.1.0*