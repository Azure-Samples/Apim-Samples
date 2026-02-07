# Screenshots for APIM Costing Sample

This directory contains screenshots showing expected results after running the costing sample.

## Screenshots to Add

Please capture and add the following screenshots after deployment:

### 1. Application Insights - Request Volume
**Filename**: `workbook-request-volume.png`
- Navigate to Application Insights → Logs
- Run query showing request count by subscription
- Capture chart visualization

### 2. Cost Allocation Dashboard
**Filename**: `workbook-cost-allocation.png`
- Navigate to Azure Monitor Workbooks (when deployed)
- Show cost allocation by business unit/subscription
- Capture full dashboard view

### 3. Error Rate Analysis
**Filename**: `workbook-error-rates.png`
- Show Log Analytics query results for error rates by subscription
- Include chart showing 4xx/5xx distribution

### 4. Log Analytics - Sample Query
**Filename**: `log-analytics-query.png`
- Show one of the sample Kusto queries running in Log Analytics
- Capture both query and results

### 5. Cost Management Export Configuration
**Filename**: `cost-management-export.png`
- Azure Portal → Cost Management → Exports
- Show configured export with storage account destination

## Screenshot Guidelines

- Use high resolution (at least 1920x1080)
- Capture full browser window or relevant panel
- Ensure sensitive data (subscription IDs, resource names) are either masked or use sample data
- Use PNG format for clarity
- File names should match exactly as specified above

## How to Capture

After running the notebook:
1. Wait 5-10 minutes for logs to populate
2. Navigate to each resource in Azure Portal
3. Run the sample queries provided in the notebook
4. Capture screenshots of results
5. Add them to this directory
6. Update the main README.md with actual screenshot references
