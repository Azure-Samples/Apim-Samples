# API Management & Container Apps Architecture

```mermaid
flowchart LR
    apps([Apps]):::appStyle
    apim[API Management]:::azureStyle
    aca[Container Apps]:::azureStyle
    appinsights[Application Insights]:::azureStyle
    loganalytics[Log Analytics]:::azureStyle

    apps -->|API Consumers| apim
    apim -->|Backend APIs| aca
    apim -->|Sends telemetry| appinsights
    appinsights -->|Stores telemetry| loganalytics

    classDef appStyle fill:#ADD8E6,stroke:#333,stroke-width:2px
    classDef azureStyle fill:#0078D4,stroke:#333,stroke-width:2px,color:#fff
```
