# Simple API Management Architecture

```mermaid
flowchart LR
    apps([Apps]):::appStyle
    apis([APIs]):::apiStyle
    apim[API Management]:::azureStyle
    appinsights[Application Insights]:::azureStyle
    loganalytics[Log Analytics]:::azureStyle

    apps -->|API Consumers| apim
    apis -.->|Deployed to| apim
    apim -->|Sends telemetry| appinsights
    appinsights -->|Stores telemetry| loganalytics

    classDef appStyle fill:#ADD8E6,stroke:#333,stroke-width:2px
    classDef apiStyle fill:#90EE90,stroke:#333,stroke-width:2px
    classDef azureStyle fill:#0078D4,stroke:#333,stroke-width:2px,color:#fff
```
