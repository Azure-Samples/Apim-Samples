# Samples: General

Sets up a simple APIM instance with a variety of policies to experiment.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~1 minute**

## 🎯 Objectives

1. Experience a variety of policies in any of the infrastructure architectures. You may see several examples from our [APIM policy snippets repo][apim-snippets-repo].
1. Become proficient with how policies operate.
1. Gain confidence in setting up and configuring policies appropriately.

## 🔗 APIs

| API Name                                   | What does it do?                                                                                                                                         |
|:-------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------|
| [Request Headers][req-headers-example]     | Returns a list of the request headers sent to APIM. Useful for debugging. Caution: may include sensitive data (tokens, cookies, keys); use responsibly.  |
| [API ID][api-id-example]                   | Returns the ID of an API as per a predefined standard such as `api-123`. Useful for explicitly identifying an API in telemetry.                          |
| [Correlation ID][correlation-id-example]   | Ensures a correlation ID header is present and returns it. Demonstrates reusable fragment `Correlation-Id`.                                              |

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures][infrastructure-architectures] you wish to use.
1. Press `Run All` in this sample's `create.ipynb` notebook.



[api-id-example]: https://github.com/Azure/api-management-policy-snippets/blob/main/examples/Send%20request%20context%20information%20to%20the%20backend%20service.policy.xml
[apim-snippets-repo]: https://github.com/Azure/api-management-policy-snippets
[correlation-id-example]: https://github.com/Azure/api-management-policy-snippets/blob/main/examples/Add%20correlation%20id%20to%20inbound%20request.policy.xml
[infrastructure-architectures]: ../../README.md#infrastructure-architectures
[req-headers-example]: https://github.com/Azure/api-management-policy-snippets/blob/main/examples/List%20all%20inbound%20headers.policy.xml
