# TODO List - Zangbéto Website Monitor

##  Priority Features

### YAML Configuration Reader
- [ ] **Replace  sites.txt (replace or just add on top) with YAML configuration** for more flexible site definitions
  - [ ] Support for site metadata (name, description, tags, criticality level)
  - [ ] Per-site configuration (timeout, retry count, check interval)
  - [ ] Site grouping and categorization
  - [ ] Environment-specific configurations (dev, staging, prod)

### API Monitoring Support  
- [ ] **REST API endpoint monitoring** with YAML configuration
  - [ ] HTTP method specification (GET, POST, PUT, DELETE)
  - [ ] Request headers and authentication (API keys, Bearer tokens)
  - [ ] Request body for POST/PUT operations
  - [ ] Response validation (status codes, JSON schema, response time)
  - [ ] Health check endpoints vs functional endpoints

### Enhanced Output Configuration
- [ ] **Multiple output formats** specified in YAML
  - [ ] HTML reports (current + enhanced templates)
  - [ ] JSON export for external tools integration
  - [ ] CSV export for spreadsheet analysis
  - [ ] PDF reports for formal documentation
  - [ ] Webhook notifications with custom payloads ?

### YAML Schema Example
```yaml
# sites-config.yaml
monitoring:
  global:
    timeout: 10
    retry_count: 3
    user_agent: "Zangbeto/1.1.0"
    
  outputs:
    - type: html
      template: enhanced
      path: "./reports/monitoring-report.html"
    - type: json
      path: "./reports/monitoring-data.json"
    - type: webhook
      url: "https://hooks.slack.com/services/..."
      
  sites:
    - name: "Company Website"
      url: "https://mycompany.com"
      type: website
      crawl_depth: 2
      criticality: high
      tags: ["production", "public"]
      
    - name: "Internal API"
      url: "https://api.internal.com/health"
      type: api
      method: GET
      headers:
        Authorization: "Bearer ${API_TOKEN}"
      expected_status: [200]
      response_validation:
        json_schema: "./schemas/health-check.json"
        max_response_time: 2.0
      criticality: critical
      tags: ["api", "internal", "critical"]
      
    - name: "User Registration API"
      url: "https://api.service.com/users"
      type: api
      method: POST
      headers:
        Content-Type: "application/json"
        X-API-Key: "${USER_API_KEY}"
      body: |
        {
          "test": true,
          "dry_run": true
        }
      expected_status: [200, 201]
      criticality: medium
```

### Expected Output Types
- [ ] **HTML Reports**
  - [ ] Current enhanced template with site-by-site analysis
  - [ ] Executive summary template for management
  - [ ] Technical details template for DevOps teams
  
- [ ] **JSON Export**
  - [ ] Machine-readable format for CI/CD integration
  - [ ] Structured data for external monitoring tools
  - [ ] Historical data export with filtering
  
- [ ] **CSV Export**
  - [ ] Tabular data for spreadsheet analysis
  - [ ] Time-series data for trend analysis
  - [ ] Site performance metrics over time
  
- [ ] **PDF Reports**
  - [ ] Professional reports for stakeholders (via custom jinja template)
  - [ ] SLA compliance reports
  - [ ] Incident summary reports

## 🔧 Implementation Tasks

### Phase 1: YAML Reader Infrastructure
- [ ] Add PyYAML dependency to requirements.txt
- [ ] Create `config.py` module for YAML parsing
- [ ] Define configuration schema with validation
- [ ] Implement backward compatibility with sites.txt
- [ ] Add configuration validation and error handling

### Phase 2: API Monitoring Core
- [ ] Extend `check_url()` function for API requests
- [ ] Add support for different HTTP methods
- [ ] Implement request body and headers handling
- [ ] Add response validation (status codes, JSON schema)
- [ ] Create API-specific error handling and reporting

### Phase 3: Output Format Extensions
- [ ] Create abstract `OutputGenerator` base class
- [ ] Implement `HTMLGenerator` (refactor existing)
- [ ] Implement `JSONGenerator` for structured export
- [ ] Implement `CSVGenerator` for tabular export
- [ ] Implement `PDFGenerator` using reportlab or weasyprint
- [ ] Add webhook output for real-time notifications

### Phase 4: Enhanced Reporting
- [ ] Update database schema for API monitoring results
- [ ] Modify report templates to handle mixed website/API data
- [ ] Add API-specific metrics and visualizations
- [ ] Implement site grouping and filtering in reports
- [ ] Add criticality-based alerting and escalation

## 🎯 Configuration Examples

### Website Monitoring
```yaml
- name: "E-commerce Site"
  url: "https://shop.example.com"
  type: website
  crawl_depth: 3
  include_patterns: ["/products/*", "/category/*"]
  exclude_patterns: ["/admin/*", "/api/*"]
  criticality: high
  check_interval: 300  # 5 minutes
```

### API Health Check
```yaml
- name: "Payment API Health"
  url: "https://api.payment.com/health"
  type: api
  method: GET
  expected_response:
    status: [200]
    json_contains: {"status": "healthy"}
    max_response_time: 1.0
  criticality: critical
```

### Authenticated API Test
```yaml
- name: "User Profile API"
  url: "https://api.service.com/profile/test-user"
  type: api
  method: GET
  headers:
    Authorization: "Bearer ${API_TOKEN}"
    X-Client-Version: "1.0"
  expected_response:
    status: [200, 404]  # 404 is acceptable for test user
    headers:
      Content-Type: "application/json"
  retry_on_failure: 2
```

##  Additional Enhancements

### Configuration Management
- [ ] Environment variable substitution in YAML
- [ ] Configuration hot-reloading without restart
- [ ] Configuration validation on startup
- [ ] Multiple configuration file support
- [ ] Configuration versioning and migration

### Advanced Features
- [ ] Site dependency mapping (if A fails, expect B to fail)
- [ ] Maintenance windows configuration
- [ ] Custom alert thresholds per site/API


### Integration & Automation
- [ ] CI/CD pipeline integration examples
- [ ] Docker containerization improvements


---

*Priority: High | Timeline: v1.2.0 | Dependencies: PyYAML, schema validation*