# Test script to validate OpenSSL certificate creation
Write-Host "Testing OpenSSL certificate creation approach..."

$keyPath = "/tmp/test-apim.key"
$certPath = "/tmp/test-apim.crt" 
$pfxPath = "/tmp/test-apim.pfx"
$password = "TestPassword123!"

try {
    # Test if OpenSSL is available
    $opensslVersion = Invoke-Expression "openssl version 2>&1"
    Write-Host "OpenSSL version: $opensslVersion"
    
    # Generate private key
    Write-Host "Generating private key..."
    $keyResult = Invoke-Expression "openssl genrsa -out $keyPath 2048 2>&1"
    Write-Host "Key generation result: $keyResult"
    
    # Create self-signed certificate
    Write-Host "Creating self-signed certificate..."
    $certResult = Invoke-Expression "openssl req -new -x509 -key $keyPath -out $certPath -days 365 -subj '/CN=apim.local' 2>&1"
    Write-Host "Certificate creation result: $certResult"
    
    # Convert to PFX
    Write-Host "Converting to PFX format..."
    $pfxResult = Invoke-Expression "openssl pkcs12 -export -out $pfxPath -inkey $keyPath -in $certPath -password pass:$password 2>&1"
    Write-Host "PFX conversion result: $pfxResult"
    
    # Check if files were created
    if (Test-Path $pfxPath) {
        Write-Host "✅ SUCCESS: PFX certificate created successfully at $pfxPath"
        
        # Get file size
        $fileSize = (Get-Item $pfxPath).Length
        Write-Host "PFX file size: $fileSize bytes"
    } else {
        Write-Host "❌ FAIL: PFX certificate was not created"
    }
    
} catch {
    Write-Host "❌ ERROR: $($_.Exception.Message)"
} finally {
    # Clean up test files
    Remove-Item -Path $keyPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $certPath -Force -ErrorAction SilentlyContinue  
    Remove-Item -Path $pfxPath -Force -ErrorAction SilentlyContinue
    Write-Host "Test files cleaned up"
}
