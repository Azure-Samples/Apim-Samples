"""Compile MockAPI consumers and verify secure template contracts without deploying."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_INFRASTRUCTURES = ('apim-aca', 'afd-apim-pe', 'appgw-apim', 'appgw-apim-pe')


@pytest.fixture(scope = 'module', params = _INFRASTRUCTURES)
def template(request):
    executable = shutil.which('bicep') or str(Path.home() / '.azure' / 'bin' / ('bicep.exe' if os.name == 'nt' else 'bicep'))
    if not Path(executable).is_file():
        pytest.skip('An existing Bicep CLI is required; this test never installs tooling.')
    result = subprocess.run([executable, 'build', str(_ROOT / 'infrastructure' / request.param / 'main.bicep'), '--stdout'], capture_output = True, text = True, check = True)
    assert not result.stderr.strip(), result.stderr

    return json.loads(result.stdout)


def _resources(template):
    resources = template['resources']
    return list(resources.values()) if isinstance(resources, dict) else resources


def _module(template, name):
    return next(resource for resource in _resources(template) if resource['name'] == name)


def test_mockapi_credentials_and_named_value_remain_secure(template):
    assert template['parameters']['mockApiCredentials']['type'] == 'secureObject'
    named_value = _module(template, 'mockApiKeyNamedValue')
    assert named_value['properties']['parameters']['namedValueIsSecret']['value'] is True
    nested = named_value['properties']['template']
    assert nested['parameters']['namedValueValue']['type'] == 'securestring'
    assert set(nested['outputs']) == {'namedValueResourceId'}
    for backend_name in ('aca-backend-1', 'aca-backend-2'):
        backend = _module(template, backend_name)
        assert backend['properties']['parameters']['credentialHeaders']['value'] == {'X-MockAPI-Key': ['{{mockapi-key}}']}


def test_mockapi_runtime_is_pinned_persistent_and_single_replica(template):
    module = _module(template, 'mockApiModule')['properties']['template']
    assert module['parameters']['credentials']['type'] == 'secureObject'
    resources = _resources(module)
    storage = next(item for item in resources if item['type'] == 'Microsoft.Storage/storageAccounts')
    assert storage['properties']['allowBlobPublicAccess'] is False
    assert storage['properties']['allowSharedKeyAccess'] is False
    assert storage['properties']['publicNetworkAccess'] == "[if(empty(parameters('storageVirtualNetworkId')), 'Enabled', 'Disabled')]"
    container_module = next(item for item in resources if item['type'] == 'Microsoft.Resources/deployments' and 'minReplicas' in item['properties']['parameters'])
    parameters = container_module['properties']['parameters']
    assert parameters['minReplicas']['value'] == parameters['maxReplicas']['value'] == 1
    assert module['variables']['containerImage'] == 'simonkurtzmsft/mockapi:1.10.0@sha256:540bec5c04730b1fa7337679685e34e4704b5d4ac0fb7adc3681e0dd1e190a85'
    environment = {entry['name']: entry for entry in parameters['environmentVariables']['value']}
    assert environment['MockApi__DashboardUsername']['value'] == 'admin'
    assert environment['MockApi__ApiKey']['secretRef'] == 'mock-api-key'
    assert environment['MockApi__DashboardPasswordHash']['secretRef'] == 'dashboard-password-hash'
    assert 'MockApi__ConfigurationBlobUri' in environment
    assert set(module['outputs']) == {'storageAccountName', 'containerAppNames', 'containerAppFqdns'}


def test_mockapi_dashboard_outputs_use_https_root_urls(template):
    """All MockAPI infrastructures expose dashboard links without changing API paths."""
    output = template['outputs']['mockApiDashboardUrls']
    assert output['type'] == 'array'
    dashboard_urls = "map(reference('mockApiModule').outputs.containerAppFqdns.value, lambda('fqdn', format('https://{0}/', lambdaVariables('fqdn'))))"
    if 'useACA' in template['parameters']:
        assert output['value'] == f"[if(parameters('useACA'), {dashboard_urls}, createArray())]"
    else:
        assert output['value'] == f'[{dashboard_urls}]'


def test_private_storage_wires_endpoint_dns_and_environment_networking(template):
    """Keep Blob traffic private without making the APIM-ACA dashboards private."""
    mock_module = _module(template, 'mockApiModule')
    module = mock_module['properties']['template']
    resources = _resources(module)
    endpoint = next(item for item in resources if item['type'] == 'Microsoft.Network/privateEndpoints')
    assert endpoint['condition'] == "[not(empty(parameters('storageVirtualNetworkId')))]"
    assert endpoint['properties']['subnet']['id'] == "[parameters('storagePrivateEndpointSubnetId')]"
    connection, = endpoint['properties']['privateLinkServiceConnections']
    assert connection['properties']['groupIds'] == ['blob']
    dns = _module(module, 'mockApiStorageDns')
    assert dns['properties']['parameters']['vnetId']['value'] == "[parameters('storageVirtualNetworkId')]"
    zone_group = next(item for item in resources if item['type'] == 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups')
    assert zone_group['properties']['privateDnsZoneConfigs'][0]['name'] == 'blob'
    parameters = mock_module['properties']['parameters']
    if 'useACA' not in template['parameters']:
        assert parameters['storageVirtualNetworkId']['value'] == "[reference('vnetModule').outputs.vnetId.value]"
        environment = _module(template, 'acaEnvModule')['properties']['parameters']
        assert environment['internalVnet']['value'] is False
        assert environment['subnetResourceId']['value'] == "[format('{0}/subnets/aca', reference('vnetModule').outputs.vnetId.value)]"
    else:
        assert 'storageVirtualNetworkId' not in parameters
