# Azure Front Door, API Management & Container Apps Architecture

```mermaid
flowchart LR
    apps([Apps]):::appStyle
    afd[Azure Front Door]:::azureStyle
    apim[API Management]:::azureStyle
    aca[Container Apps]:::azureStyle
    appinsights[Application Insights]:::azureStyle
    loganalytics[Log Analytics]:::azureStyle

    apps -->|API Consumers| afd
    afd -->|Routes traffic| apim
    apim -->|Backend| aca
    apim -->|Sends telemetry| appinsights
    appinsights -->|Stores data| loganalytics

    classDef appStyle fill:#ADD8E6,stroke:#333,stroke-width:2px
    classDef azureStyle fill:#0078D4,stroke:#333,stroke-width:2px,color:#fff
```
