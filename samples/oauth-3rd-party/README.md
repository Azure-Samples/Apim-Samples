# Samples: OAuth 2.0 with 3rd Party

Sets up a 3rd party integration via [Azure API Management Credential Manager](https://learn.microsoft.com/azure/api-management/credentials-overview).  

***This sample has prerequisites! Please follow the instructions below.***

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~2-3 minutes**

## 🎯 Objectives

1. Distinguish between authentication to APIM via JSON Web Tokens and to the 3rd party using Credential Manager.
1. Understand how API Management supports OAuth 2.0 authentication (authN) with JSON Web Tokens (JWT).
1. Learn how authorization (authZ) can be accomplished based on JWT claims.
1. Configure authN and authZ at the API level (simpler than _AuthX-Pro_)
1. Use external secrets in policies.
1. Experience how API Management policy fragments simplify shared logic.

## 📝 Scenario

We chose Spotify as it provides an extensive REST API and has relatively generous limits on free API access. This makes for a relatively straight-forward experience for this sample. 
Specifically, this sample uses Spotify's REST API to obtain information about its deep music and artist catalog. API Management is registered as an application in Spotify's applications with its own client ID and client secret for a given scope. This application is then set up as a generic OAuth 2.0 integration in Credential Manager.  
Furthermore, we build on the knowledge gained from the _AuthX_ and _AuthX-Pro_ samples to authentication callers and authorize their use of the Spotify integration. 

We use only one persona in this sample:

- `Marketing Member` - holds read rights.

The API hierarchy is as follows:

1. All APIs / global
    This is a great place to do authentication, but we refrain from doing it in the sample as to not affect other samples. 
1. Marketing Member

## Prerequisites

This sample requires a little bit of manual pre-work in order to create a high-fidelity setup:

1. A Spotify Account
1. A Spotify Application

### A Spotify Account

1. You can use your existing Spotify account or sign up for a new one [here](https://www.spotify.com/us/signup). Please ensure you adhere to Spotify's terms & conditions of use.

### A Spotify Application

In order for API Management to gain access to Spotify's API, we need to create an application that represents API Management. 

1. Open or log into the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
1. Review and accept the _Spotify Developer Terms of Service_, if required.
1. Proceed with verifying your email address, if required.
1. If the Dashboard does not open immediately, select it from the menu after clicking on your profile name (top-right corner).
1. [Create the app](https://developer.spotify.com/dashboard/create):
    - **App Name**: _APIM_
    - **App Description**: _API Management_
    - **Redirect URIs**: https://localhost:8080/callback
        We will update this placeholder once we have the APIM URL.
    - **Which API/SDKs are you planning to use?** _Web API_
1. Once the app has been created, **note the _Client ID_ and _Client secret_**. We will need them for the Credential Manager setup.
1. Leave the Dashboard page open in your browser, as we will need to replaec the Redirect URI shortly.
1. Proceed to the [create](./create.ipynb) Jupyter notebook and follow directions there.

## Acknowledgement

We thank [Spotify](https://www.spotify.com) for access to their API. Keep building great products!
