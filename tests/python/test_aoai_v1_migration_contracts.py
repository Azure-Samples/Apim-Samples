"""Offline PAYG deployment and migration-contract checks, not live Azure evidence."""

import ast
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import utils

# APIM Samples imports
from apimtypes import AzureOpenAIModel

SAMPLE = Path(__file__).resolve().parents[2] / 'samples' / 'aoai-v1-migration'


def notebook():
    """Read notebook source without executing a real remote operation."""
    return json.loads((SAMPLE / 'create.ipynb').read_text(encoding = 'utf-8'))


def test_notebook_clean_and_configuration_defaults():
    """Outputs must contain no private execution material."""
    cells = notebook()['cells']
    assert len({cell['id'] for cell in cells}) == len(cells)
    assert [cell['cell_type'] for cell in cells[:4]] == ['markdown', 'markdown', 'markdown', 'code']
    assert 'What This Sample Does' in ''.join(cells[1]['source'])
    assert 'Initialize Notebook Variables' in ''.join(cells[2]['source'])
    sources = []
    for cell in cells:
        if cell['cell_type'] == 'code':
            assert cell['outputs'] == [] and cell['execution_count'] is None
            source = ''.join(cell['source'])
            tree = ast.parse(source)
            seen_statement = False
            for statement in tree.body:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    assert not seen_statement, 'Imports must be at the top of each cell'
                else:
                    seen_statement = True
            sources.append(source)
    config = sources[0]
    assignments = {
        statement.targets[0].id: statement.value
        for statement in ast.parse(config).body
        if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name)
    }
    assert ast.literal_eval(assignments['index']) == 1
    assert ast.literal_eval(assignments['sample_name']) == 'aoai-v1-migration-1'
    assert ast.unparse(assignments['primary_model']) == 'AzureOpenAIModel.GPT_5_MINI'
    assert ast.unparse(assignments['secondary_model']) == 'AzureOpenAIModel.GPT_5_NANO'
    assert ast.literal_eval(assignments['model_sku']) == 'GlobalStandard'
    assert AzureOpenAIModel.GPT_5_MINI.version == '2025-08-07'
    assert 'INFRASTRUCTURE.SIMPLE_APIM' in config
    assert "utils.enable_module_autoreload('migration_helpers')" in config
    assert 'require_existing_infrastructure' not in ''.join(sources)


def test_payg_iac_and_isolation():
    """Provision real PAYG resources while leaving existing monitoring alone."""
    main = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    assert "@allowed(['Standard', 'GlobalStandard'])" in main
    assert "kind: 'OpenAI'" in main and "name: 'S0'" in main
    assert 'name: modelSku' in main and 'capacity: model.capacity' in main
    assert 'disableLocalAuth: true' in main
    assert 'version: model.version' in main and "versionUpgradeOption: 'NoAutoUpgrade'" in main
    assert "@batchSize(1)\nresource modelDeploymentResources 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01'" in main
    assert '@minLength(2)\n@maxLength(2)\nparam models array' in main
    assert main.count('= [for model in models: {') == 4  # Deployments, backends, pools, output.
    assert '../../shared/bicep/modules/apim/v1/backend-pool.bicep' in main
    assert 'backendPoolName: model.poolName' in main
    assert 'backends: [\n      { name: model.backendName, priority: 1, weight: 100 }\n    ]' in main
    assert 'dependsOn: [pools, modelDeploymentResources, apimOpenAiRole]' in main
    assert 'scope: openAiAccount' in main and 'apimService.identity.principalId' in main
    assert 'uniqueString(resourceGroup().id, sampleName)' in main
    assert "param sampleName string = 'aoai-v1-migration-1'" in main
    assert '../../shared/bicep/modules/apim/v1/api.bicep' in main
    assert '../../shared/bicep/modules/apim/v1/backend.bicep' in main
    assert 'appInsightsInstrumentationKey:' not in main
    assert 'diagnosticSettings' not in main and 'workbooks' not in main
    assert "resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing" in main
    assert "resource appInsights 'Microsoft.Insights/components@2020-02-02' existing" in main
    assert 'api: api' in main
    assert 'loadTextContent(' not in main
    assert 'param modelAlias' not in main and 'param legacyApiVersion' not in main
    assert 'Microsoft.ApiManagement/service/namedValues' not in main


def test_policy_contracts():
    """Derive pool names directly without dictionaries, fallback or body rewriting."""
    legacy = ET.parse(SAMPLE / 'apim-policies' / 'legacy.xml').getroot()
    v1 = ET.parse(SAMPLE / 'apim-policies' / 'v1.xml').getroot()
    for root in (legacy, v1):
        assert root.find('inbound')[0].tag == 'base'
        assert len(root.find('backend')) == 1
        assert root.find('backend/forward-request').attrib['timeout'] == '60'
        assert root.find('backend/forward-request').attrib['buffer-response'] == 'false'
        assert root.find('backend/forward-request').attrib['fail-on-error-status-code'] == 'false'
        assert not list(root.iter('retry'))
        assert root.find('inbound/set-backend-service').attrib['backend-id'] == '@((string)context.Variables["backendPool"])'
        assert len(list(root.iter('authentication-managed-identity'))) == 1
        assert not list(root.find('inbound').iter('choose'))
        assert not list(root.find('inbound').iter('set-body'))
        routing = root.find('inbound/set-variable')
        assert routing.attrib['name'] == 'backendPool'
        assert 'Dictionary' not in routing.attrib['value']
        assert 'ContainsKey' not in routing.attrib['value']
        assert 'DEFAULT_POOL' not in routing.attrib['value']
        assert not list(root.iter('set-query-parameter'))
        removed = {header.attrib['name'] for header in root.iter('set-header') if header.attrib['exists-action'] == 'delete'}
        assert {'Authorization', 'api-key', 'Ocp-Apim-Subscription-Key'} <= removed
    assert legacy.find('inbound/rewrite-uri').attrib == {
        'template': '@("/openai/deployments/" + Uri.EscapeDataString(context.Request.MatchedParameters["deployment"]) + "/chat/completions")',
        'copy-unmatched-params': 'true',
    }
    assert v1.find('inbound/rewrite-uri').attrib['template'] == '/openai/v1/chat/completions'
    assert v1.find('inbound/rewrite-uri').attrib['copy-unmatched-params'] == 'false'
    assert legacy.find('inbound/set-variable').attrib['value'] == '@(context.Request.MatchedParameters["deployment"] + "-pool")'
    routing = v1.find('inbound/set-variable').attrib['value']
    assert routing.count('context.Request.Body.As<JObject>(preserveContent: true)') == 1
    assert 'selector.Type == JTokenType.String' in routing
    assert 'return model + "-pool";' in routing
    assert 'catch' not in routing and 'try' not in routing


@pytest.mark.parametrize('contract', ['legacy', 'v1'])
def test_gateway_errors_are_traced_without_parsing(contract):
    """Verify error-policy structure; offline checks do not execute APIM C#."""
    policy = ET.parse(SAMPLE / 'apim-policies' / f'{contract}.xml').getroot()
    on_error = policy.find('on-error')
    assert [child.tag for child in on_error] == ['set-variable', 'trace', 'base', 'set-status', 'set-header', 'set-body']
    status = on_error.find('set-variable')
    assert status.attrib['name'] == 'errorStatus'
    assert ' '.join(status.attrib['value'].split()) == (
        '@( context.Response != null && context.Response.StatusCode >= 400 && context.Response.StatusCode <= 599 '
        '? context.Response.StatusCode '
        ': context.LastError != null && context.LastError.Reason == "Timeout" ? 504 '
        ': context.LastError != null && context.LastError.Reason == "BackendConnectionFailure" ? 502 : 500 )'
    )
    assert on_error.find('set-status').attrib['code'] == '@((int)context.Variables["errorStatus"])'
    trace = on_error.find('trace')
    assert trace.attrib == {'source': 'AoaiMigrationError', 'severity': 'error'}
    assert trace.find('message').text == '@("Azure OpenAI request failed")'
    assert {item.attrib['name']: item.attrib['value'] for item in trace.findall('metadata')} == {
        'contract': contract,
        'requestId': '@(context.RequestId.ToString())',
        'status': '@(((int)context.Variables["errorStatus"]).ToString())',
        'source': '@(context.LastError == null ? "" : context.LastError.Source)',
        'reason': '@(context.LastError == null ? "" : context.LastError.Reason)',
    }
    expressions = [value for element in on_error.iter() for value in [element.text or '', *element.attrib.values()]]
    assert not any('Request.Body' in expression or 'Response.Body' in expression for expression in expressions)
    assert not list(policy.iter('return-response'))
    assert len(list(policy.iter('set-body'))) == 1
    assert on_error.find('set-header').attrib == {'name': 'Content-Type', 'exists-action': 'override'}
    assert on_error.find('set-header/value').text == 'application/json'
    assert json.loads(on_error.find('set-body').text) == {
        'error': {'code': 'gateway_error', 'message': 'The gateway could not route or complete the request.'},
    }


@pytest.mark.parametrize('contract', ['legacy', 'v1'])
def test_backend_http_errors_stay_on_the_response_path(contract):
    """Guard the 404-to-500 regression without pretending to execute APIM C#."""
    policy = ET.parse(SAMPLE / 'apim-policies' / f'{contract}.xml').getroot()
    assert policy.find('backend/forward-request').attrib['fail-on-error-status-code'] == 'false'
    outbound = policy.find('outbound')
    assert [child.tag for child in outbound] == ['choose', 'base', 'set-header']
    header = outbound.find('set-header')
    assert header.attrib == {'name': 'x-migration-backend-pool', 'exists-action': 'override'}
    assert header.find('value').text == '@((string)context.Variables["backendPool"])'
    choose = outbound.find('choose')
    assert [child.tag for child in choose] == ['when']
    when = choose.find('when')
    assert when.attrib['condition'] == '@(context.Response.StatusCode >= 400 && context.Response.StatusCode <= 599)'
    assert [child.tag for child in when] == ['trace']
    trace = when.find('trace')
    assert trace.attrib == {'source': 'AoaiMigrationError', 'severity': 'error'}
    assert trace.find('message').text == '@("Azure OpenAI returned an HTTP error")'
    assert {item.attrib['name']: item.attrib['value'] for item in trace.findall('metadata')} == {
        'contract': contract,
        'requestId': '@(context.RequestId.ToString())',
        'status': '@(context.Response.StatusCode.ToString())',
        'source': 'backend',
        'reason': 'http_error',
    }
    assert not any(list(outbound.iter(tag)) for tag in ['set-status', 'set-body', 'return-response'])


def test_notebook_staged_workflow_with_mocked_remote_boundaries(monkeypatch):
    """Execute the actual cells offline and observe legacy-test-before-v1 ordering."""
    events = []
    deployments = []

    class FakeNotebookHelper:
        """Implement the NotebookHelper boundary without Azure."""

        def __init__(self, *args, **kwargs):
            self.deployment = args[3]

        def deploy_sample(self, params):
            names = [api['name'] for api in params['apis']['value']]
            events.append(('deploy', names))
            deployments.append(params)

            return params

        def get_deployment_context(self, output):
            return SimpleNamespace(
                apim_gateway_url = 'https://offline.invalid',
                apis = [{'name': api['name'], 'subscriptionPrimaryKey': api['name']} for api in output['apis']['value']],
            )

        def create_apim_requests(self, *args):
            raise AssertionError('Smoke runner should be mocked')

    def fake_smoke(factory, path, payload, **kwargs):
        events.append(('smoke', path, payload.copy(), kwargs.copy()))
        if payload.get('model') == 'unknown-model':
            assert kwargs['expected_status'] == 500
            assert kwargs['retry_delays'] == ()
            assert 'expected_pool' not in kwargs

        return SimpleNamespace(
            status_code = kwargs.get('expected_status', 200), has_completion = kwargs.get('expected_status', 200) == 200,
            attempts = 1, backend_pool = kwargs.get('expected_pool'), model = kwargs.get('expected_model'),
            response_time = 0.25, prompt_tokens = 10, completion_tokens = 5, total_tokens = 15,
        )

    monkeypatch.syspath_prepend(str(SAMPLE))
    monkeypatch.setattr(utils, 'NotebookHelper', FakeNotebookHelper)
    monkeypatch.setattr(utils, 'enable_module_autoreload', lambda *args: None)
    namespace = {}
    code = [''.join(cell['source']) for cell in notebook()['cells'] if cell['cell_type'] == 'code']
    exec(code[0], namespace)
    for api_name, policy_name in [('legacy_api', 'pol_legacy'), ('v1_api', 'pol_v1')]:
        api = namespace[api_name]
        assert api.policyXml == namespace[policy_name]
        assert api.policyXml == (SAMPLE / 'apim-policies' / f'{api_name.split("_")[0]}.xml').read_text(encoding = 'utf-8')
        policy = ET.fromstring(api.policyXml)
        assert policy.find('inbound/set-backend-service').attrib['backend-id'] == '@((string)context.Variables["backendPool"])'
        for model in namespace['model_configuration']:
            assert model['poolName'] == f'{model["deploymentName"]}-pool'
            assert model['deploymentName'] not in api.policyXml
        assert api.subscriptionRequired is True
        assert api.operations[0].to_dict()['method'] == 'POST'
    assert namespace['legacy_api'].operations[0].templateParameters == [{'name': 'deployment', 'type': 'string', 'required': True}]
    assert namespace['legacy_api'].path == f'{namespace["sample_name"]}/openai'
    assert namespace['legacy_api'].displayName == 'Azure OpenAI Chat Completions'
    assert namespace['v1_api'].path == f'{namespace["sample_name"]}/openai/v1'
    assert namespace['legacy_api'].tags == namespace['v1_api'].tags == ['aoai-v1-migration', 'ai-gateway']
    monkeypatch.setattr(namespace['migration_helpers'], 'test', fake_smoke)
    report = Mock(return_value = SAMPLE / 'offline-report.html')
    monkeypatch.setattr(namespace['migration_helpers'], 'generate_report', report)
    exec(code[1], namespace)
    with pytest.raises(AssertionError, match = 'legacy baseline'):
        exec(code[3], namespace)
    for source in code[2:]:
        exec(source, namespace)
    assert [event[0] for event in events] == ['deploy', 'smoke', 'smoke', 'deploy', 'smoke', 'smoke', 'smoke', 'smoke', 'smoke']
    assert len(deployments[0]['apis']['value']) == 1
    assert deployments[1]['apis']['value'][0] == deployments[0]['apis']['value'][0]
    assert len(deployments[1]['apis']['value']) == 2
    assert namespace['tests'].total_tests == 26
    assert namespace['tests'].tests_failed == 0
    report.assert_called_once()
    assert len(report.call_args.args[0]) == 7
    assert [probe.stage for probe in report.call_args.args[0]] == [
        'Legacy Before', 'Legacy Before', 'v1', 'v1', 'Legacy After', 'Legacy After', 'v1 Rejection',
    ]
    assert report.call_args.args[1].name == 'aoai-v1-migration-1-report.html'
    assert deployments[0]['apis']['value'][0]['policyXml'] == namespace['pol_legacy']
    assert deployments[1]['apis']['value'][1]['policyXml'] == namespace['pol_v1']
    assert deployments[0]['models'] == deployments[1]['models'] == {'value': namespace['model_configuration']}
    assert {item['name'] for item in namespace['model_configuration']} == {'gpt-5-mini', 'gpt-5-nano'}
    assert deployments[0]['sampleName']['value'] == deployments[1]['sampleName']['value'] == namespace['sample_name']
    assert deployments[0]['location']['value'] == namespace['rg_location']
    for index, model in enumerate(namespace['model_configuration']):
        before, v1, after = events[1 + index], events[4 + index], events[7 + index]
        assert before[1:3] == after[1:3]  # Exact legacy URL/body reused.
        assert {key: value for key, value in before[3].items() if key != 'warmup'} == after[3]
        assert before[3]['warmup'] is True
        assert 'warmup' not in v1[3] and 'warmup' not in after[3]
        assert before[1] == (
            f'/{namespace["sample_name"]}/openai/deployments/{model["deploymentName"]}/chat/completions'
            f'?api-version={namespace["legacy_api_version"]}'
        )
        assert v1[1] == f'/{namespace["sample_name"]}/openai/v1/chat/completions'
        assert 'model' not in before[2]
        assert before[2]['reasoning_effort'] == 'low'
        assert before[2]['max_completion_tokens'] == 1024
        assert v1[2]['model'] == model['deploymentName']
        for event in (before, v1, after):
            assert event[3]['expected_pool'] == f'{namespace["sample_name"]}-{model["name"]}-pool'
            assert event[3]['expected_model'] == f'{model["name"]}-{model["version"]}'
        assert '?' not in v1[1]
    assert events[6][2]['model'] == 'unknown-model'
    assert events[6][3]['expected_status'] == 500
    assert 'expected_pool' not in events[6][3]

    def failed_rejection(factory, path, payload, **kwargs):
        if payload.get('model') == 'unknown-model':
            raise RuntimeError('rejection unavailable')

        return fake_smoke(factory, path, payload, **kwargs)

    monkeypatch.setattr(namespace['migration_helpers'], 'test', failed_rejection)
    with pytest.raises(RuntimeError, match = 'rejection unavailable'):
        exec(code[4], namespace)
    assert namespace['v1_rejection'] is None
    assert namespace['legacy_after'] == {}
    with pytest.raises(AssertionError, match = 'Run all probes'):
        exec(code[-1], namespace)
    assert report.call_count == 1
    namespace['legacy_before'].pop(namespace['model_configuration'][1]['deploymentName'])
    deployment_count = len(deployments)
    with pytest.raises(AssertionError, match = 'both pools'):
        exec(code[3], namespace)
    assert len(deployments) == deployment_count
    exec(code[1], namespace)
    assert namespace['legacy_before'] == {}
    assert namespace['v1_success'] == namespace['legacy_after'] == {}
    assert namespace['v1_rejection'] is None
    with pytest.raises(AssertionError, match = 'Run all probes'):
        exec(code[-1], namespace)
    assert report.call_count == 1


@pytest.mark.parametrize('stage', [1, 3])
@pytest.mark.parametrize('configuration', [
    {},
    {'sample_name': 'aoai-v1-migration-1'},
    {'sample_name': 'aoai-v1-migration-1', 'bicep_parameters': {'labName': {'value': 'aoai-v1-migration-1'}}},
    {'sample_name': 'aoai-v1-migration-1', 'bicep_parameters': {'sampleName': {'value': 'aoai-v1-migration-2'}}},
    {
        'sample_name': 'aoai-v1-migration-1',
        'bicep_parameters': {'sampleName': {'value': 'aoai-v1-migration-1'}, 'modelAlias': {'value': 'old-alias'}},
    },
    {
        'sample_name': 'aoai-v1-migration-1',
        'bicep_parameters': {'sampleName': {'value': 'aoai-v1-migration-1'}, 'legacyApiVersion': {'value': '2024-10-21'}},
    },
    {
        'sample_name': 'aoai-v1-migration-1',
        'bicep_parameters': {'sampleName': {'value': 'aoai-v1-migration-1'}, 'modelName': {'value': 'gpt-5-mini'}},
    },
])
def test_deployment_rejects_stale_kernel_configuration_before_remote_calls(stage, configuration):
    """Point outdated kernels to the initialization cell instead of failing in ARM."""
    helper = Mock(spec = utils.NotebookHelper)
    namespace = {**configuration, 'nb_helper': helper, 'legacy_before': SimpleNamespace(has_completion = True)}
    code = [''.join(cell['source']) for cell in notebook()['cells'] if cell['cell_type'] == 'code']
    with pytest.raises(AssertionError, match = 'Re-run Cell 4'):
        exec(code[stage], namespace)
    helper.deploy_sample.assert_not_called()


def evidence_namespace():
    """Build complete final-cell inputs without executing configuration or Azure calls."""
    models = [
        {'name': name, 'version': '2025-08-07', 'deploymentName': name, 'poolName': f'{name}-pool'}
        for name in ('gpt-5-mini', 'gpt-5-nano')
    ]
    success = {
        model['deploymentName']: SimpleNamespace(
            status_code = 200, has_completion = True, backend_pool = model['poolName'],
            model = f'{model["name"]}-{model["version"]}',
        )
        for model in models
    }

    return {
        'model_configuration': models, 'legacy_before': success.copy(), 'v1_success': success.copy(), 'legacy_after': success.copy(),
        'v1_rejection': SimpleNamespace(status_code = 500, has_completion = False),
        'sample_folder': 'aoai-v1-migration', 'nb_helper': SimpleNamespace(deployment = None),
        'migration_helpers': SimpleNamespace(ProbeEvidence = Mock(), generate_report = Mock()),
    }


@pytest.mark.parametrize('missing', ['legacy_after', 'v1_rejection'])
def test_evidence_requires_completed_probe_cells(missing):
    """Executing reporting before its prerequisite cells gives a useful error."""
    namespace = evidence_namespace()
    namespace.pop(missing)
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(SystemExit, match = 'Run both migration stages'):
        exec(source, namespace)
    namespace['migration_helpers'].generate_report.assert_not_called()


@pytest.mark.parametrize('stage', ['legacy_before', 'v1_success', 'legacy_after'])
def test_evidence_rejects_incomplete_model_results(stage):
    """Reporting requires both models in every contract stage, not a partial run."""
    namespace = evidence_namespace()
    namespace[stage].pop('gpt-5-nano')
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'Run all probes'):
        exec(source, namespace)
    namespace['migration_helpers'].generate_report.assert_not_called()


def test_evidence_rejects_missing_negative_probe():
    """Complete successes alone cannot replace the unknown-model rejection probe."""
    namespace = evidence_namespace()
    namespace['v1_rejection'] = None
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'unknown-model rejection'):
        exec(source, namespace)
    namespace['migration_helpers'].generate_report.assert_not_called()


@pytest.mark.parametrize('stage', ['legacy_before', 'v1_success', 'legacy_after'])
@pytest.mark.parametrize('field,value', [
    ('status_code', 500), ('has_completion', False), ('backend_pool', 'wrong-pool'), ('model', 'wrong-snapshot'),
])
def test_evidence_does_not_write_report_when_success_checks_fail(stage, field, value):
    """All status, completion, pool and snapshot checks must pass before reporting."""
    namespace = evidence_namespace()
    namespace[stage]['gpt-5-mini'] = SimpleNamespace(**{**vars(namespace[stage]['gpt-5-mini']), field: value})
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'Migration checks failed'):
        exec(source, namespace)
    assert namespace['tests'].total_tests == 26
    assert namespace['tests'].tests_failed == 1
    namespace['migration_helpers'].generate_report.assert_not_called()


@pytest.mark.parametrize('field,value', [('status_code', 200), ('has_completion', True)])
def test_evidence_does_not_write_report_when_rejection_checks_fail(field, value):
    """An unexpected negative-probe outcome cannot receive a success report."""
    namespace = evidence_namespace()
    namespace['v1_rejection'] = SimpleNamespace(**{**vars(namespace['v1_rejection']), field: value})
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'Migration checks failed'):
        exec(source, namespace)
    assert namespace['tests'].tests_failed == 1
    namespace['migration_helpers'].generate_report.assert_not_called()


def test_only_current_lab_artifacts_remain():
    """Do not retain misleading fault-gate policies or PTU runbooks."""
    assert {path.name for path in (SAMPLE / 'apim-policies').glob('*.xml')} == {'legacy.xml', 'v1.xml'}
    assert {path.name for path in (SAMPLE / 'queries').glob('*.kql')} == {'migration-requests.kql'}
    assert not (SAMPLE / 'openai-role.bicep').exists()
    readme = (SAMPLE / 'README.md').read_text(encoding = 'utf-8')
    assert 'No pre-existing Azure OpenAI' in readme
    assert 'APIM_ACA is unsupported' in readme
