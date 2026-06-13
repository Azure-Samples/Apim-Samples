# Samples: AuthX Pro - Authentication & Authorization

Sets up a more sophisticate authentication (authN) and authorization (authZ) combination for role-based access control (RBAC) to a mock API and its operations.  

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~2-3 minutes**

## 🎯 Objectives

1. Understand how API Management supports OAuth 2.0 authentication (authN) with JSON Web Tokens (JWT).
1. Learn how authorization (authZ) can be accomplished based on JWT claims.
1. Configure authN and authZ at various levels in the API Management hierarchy - product, API, and API operations
1. Use external secrets in policies.
1. Experience how API Management policy fragments simplify shared logic.

## 📝 Scenario

This sample, compared to the simpler *AuthX*, introduces use of API Management Product and policy fragments to simplify and consolidate shared logic. When considering scaling, consider this as your starting point.

The same two personas from *AuthX* are at play:

- `HR Administrator` - holds broad rights to the API
- `HR Associate` - has read-only permissions

The API hierarchy is as follows:

1. All APIs / global
    This is a great place to do authentication, but we refrain from doing it in the sample as to not affect other samples.
1. HR Product
    Perform authentication and authorization for HR_Member in the JWT claims. Continue on success; otherwise, return 401.
1. HR Employee & Benefits APIs
