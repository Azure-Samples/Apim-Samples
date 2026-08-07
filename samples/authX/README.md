# Samples: AuthX - Authentication & Authorization

Sets up a simple authentication (authN) and authorization (authZ) combination for role-based access control (RBAC) to a mock _Employees_ API and its operations.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected _Run All_ runtime (excl. infrastructure prerequisite): ~2-3 minutes**

## 🎯 Objectives

1. Understand how API Management supports OAuth 2.0 authentication (authN) with JSON Web Tokens (JWT).
1. Learn how authorization (authZ) can be accomplished based on JWT claims.
1. Configure authN and authZ at various levels in the API Management hierarchy.
1. Use external secrets in policies.

## 📝 Scenario

This sample combines _authentication (authN)_ and _authorization (authZ)_ into _authX_. This scenario focuses on a Human Resources API that requires privileged role-based access to GET and to POST data. This is simplistic but shows the combination of authN and authZ.

There are two personas at play:

- `HR Administrator` - holds broad rights to the API
- `HR Associate` - has read-only permissions

Both personas are part of an HR_Members group and may access the HR Employees API, but its operations permissions are more granular.

### 💡 Notes

Many organizations require 100% authentication for their APIs. While that is prudent and typically done at the global _All APIs_ level, we refrain from doing so here as to not impact other samples. Instead, we focus on authentication at the API Management API and API operation levels.
