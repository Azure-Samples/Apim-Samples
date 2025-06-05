import sys
sys.path.append('shared/python')
import utils
import subprocess
import json

# Get a managed identity token for testing
print('Getting managed identity token for storage access...')
token_output = utils.run(
    'az account get-access-token --resource https://storage.azure.com/ --query accessToken -o tsv',
    'Retrieved access token',
    'Failed to get access token'
)

if token_output.success:
    token = token_output.text.strip()
    print(f'Token retrieved (first 50 chars): {token[:50]}...')
    
    # Test blob access with Authorization header
    blob_url = 'https://st3n7hvonlutykg.blob.core.windows.net/samples/hello.txt'
    
    print(f'Testing blob access with Authorization header...')
    print(f'URL: {blob_url}')
    
    # Use PowerShell to run curl
    curl_cmd = ['curl', '-H', f'Authorization: Bearer {token}', blob_url]
    
    print(f'Running curl command...')
    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
        print(f'Curl exit code: {result.returncode}')
        print(f'Stdout: {result.stdout}')
        print(f'Stderr: {result.stderr}')
    except Exception as e:
        print(f'Error running curl: {e}')
else:
    print('Failed to get access token')
