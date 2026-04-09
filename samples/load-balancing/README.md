# Samples: Load Balancing

Sets up an APIM instance that demonstrates load balancing and circuit breaking across backends.

⚙️ **Supported infrastructures**: apim-aca, afd-apim-pe

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~3 minutes**

## 🎯 Objectives

1. Understand how backends can be configured to balance load in a prioritized, weighted manner.
1. Learn how circuit breakers aid with load balancing.
1. Configure how retries in API Management policies can result in more successful requests.

## 🛩️ Lab Components

This lab integrates into an existing Azure Container Apps architecture and sets up the following:

- One container app that serves multiple mock Web API endpoints returning 429 error codes.
- Three separate backends are set up in APIM that each point to a different endpoint on this container app (e.g. /api/0, /api/1, etc.).
- Four separate backend pool with varying load balancer setups are configured using these three backends.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure *does not* yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure *does* exist, adjust the `user-defined parameters` in the *Initialize notebook variables* below. Please ensure that all parameters match your infrastructure.
