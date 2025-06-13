# APIM Samples Test Matrix

This document outlines the compatibility between samples and infrastructure types, providing a comprehensive test matrix to ensure all components work correctly in both local development and Codespaces environments. The format allows for manual check-off during testing sessions.

## Printable Test Checklist

| Sample / Infrastructure | SIMPLE_APIM | APIM_ACA | AFD_APIM_PE |
|-------------------------|------------|----------|------------|
| **INFRASTRUCTURE** | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |
| **authX** | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |
| **authX-pro** | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |
| **general** | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |
| **load-balancing** | N/A | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |
| **secure-blob-access** | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |
| **INFRASTRUCTURE clean-up** | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container | [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Local<br>[&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;] Dev Container |

## Infrastructure Types

The repository currently supports the following infrastructure types:

1. **SIMPLE_APIM** - Simple API Management with no dependencies
2. **APIM_ACA** - Azure API Management connected to Azure Container Apps
3. **AFD_APIM_PE** - Azure Front Door Premium connected to Azure API Management (Standard V2) via Private Link

## Testing Requirements

To ensure robust functionality across environments, all samples should:

1. Be tested in both local development and Codespaces/Dev Container environments
2. Pass all tests for their supported infrastructures as indicated in the matrix above
3. Be verified that the `supported_infrastructures` variable in each sample's `create.ipynb` file is correctly reflected in this matrix

## Testing Workflow

1. Print this document for manual tracking or use markdown checkboxes in digital form
2. For each combination of sample, infrastructure, and environment:
   - Deploy the infrastructure and sample
   - Run tests 
   - Mark the corresponding checkbox when tests pass
3. Document any issues encountered in the "Test Notes" section below

## Test Procedure

For each sample and infrastructure combination:

1. Deploy the infrastructure using the appropriate method:
   ```bash
   cd infrastructure/<infrastructure-name>
   # Execute the create.ipynb notebook
   ```

2. Deploy and test the sample:
   ```bash
   cd samples/<sample-name>
   # Execute the create.ipynb notebook with the matching infrastructure
   ```

3. Verify that all operations work correctly and no errors are reported

4. Clean up resources when testing is complete:
   ```bash
   # Execute the clean-up.ipynb notebook in the infrastructure directory
   ```

## Test Notes

| Date | Tester | Sample | Infrastructure | Environment | Notes |
|------|--------|--------|---------------|-------------|-------|
| YYYY-MM-DD | Name | sample-name | infra-name | Local/DevC | Any issues or observations |

## General Notes

- "N/A" indicates that the sample does not support that particular infrastructure type
- The `_TEMPLATE` sample is not meant for deployment; it's a template for creating new samples
- The test matrix should be updated whenever new samples or infrastructures are added
- Infrastructure limitations should be documented when a sample is incompatible with a specific infrastructure type
- Tester name, date, and detailed notes should be recorded for any failures or unexpected behavior
