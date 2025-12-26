"""
Shared test helpers, mock factories, and assertion utilities.
"""

import io
import logging
import builtins
from collections.abc import Callable
from unittest.mock import Mock, MagicMock, mock_open, patch
import json as json_module

# APIM Samples imports
from apimtypes import APIM_SKU, APIMNetworkMode, API, APIOperation, PolicyFragment, Output, HTTP_VERB


# ------------------------------
#    PATCH HELPERS
# ------------------------------

def patch_open_for_text_read(
    monkeypatch,
    *,
    match: str | Callable[[str], bool],
    read_data: str | None = None,
    raises: Exception | None = None
):
    """Patch builtins.open for a specific text-mode path match.

    Only intercepts when 'b' is not present in the requested mode.
    All other opens are delegated to the real built-in open.
    """
    real_open = builtins.open
    open_mock = mock_open(read_data=read_data) if read_data is not None else None

    def open_selector(file, *args, **kwargs):
        mode = kwargs.get('mode', args[0] if args else 'r')
        file_str = str(file)
        is_match = match(file_str) if callable(match) else file_str == str(match)

        if is_match and 'b' not in mode:
            if raises is not None:
                raise raises
            return open_mock(file, *args, **kwargs)

        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', open_selector)
    return open_mock


def mock_popen(monkeypatch, *, stdout_lines: list[str], returncode: int = 0) -> None:
    """Patch subprocess.Popen with a context-manager friendly mock process."""

    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = returncode
            self.stdout = iter(stdout_lines)

        def wait(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr('subprocess.Popen', MockProcess)


def patch_os_paths(
    monkeypatch,
    *,
    cwd: str = '/test/dir',
    exists: bool | Callable[[str], bool] = True,
    basename: str | Callable[[str], str] = 'test-dir'
) -> None:
    """Patch common os.getcwd / os.path.exists / os.path.basename for tests."""
    monkeypatch.setattr('os.getcwd', MagicMock(return_value=cwd))

    if callable(exists):
        monkeypatch.setattr('os.path.exists', exists)
    else:
        monkeypatch.setattr('os.path.exists', MagicMock(return_value=exists))

    if callable(basename):
        monkeypatch.setattr('os.path.basename', basename)
    else:
        monkeypatch.setattr('os.path.basename', MagicMock(return_value=basename))


# ------------------------------
#    MOCK FACTORIES
# ------------------------------

def create_mock_output(success: bool = True, text: str = '', json_data: dict | None = None) -> Output:
    """
    Factory for creating consistent mock Azure CLI Output objects.

    Args:
        success: Whether the command succeeded
        text: Text output from command
        json_data: JSON data from command

    Returns:
        Output object configured with provided values
    """
    output = Output(success, text)
    if json_data is not None:
        output.json_data = json_data
    return output


def create_mock_az_module(
    rg_exists: bool = True,
    rg_name: str = 'rg-test-infrastructure-01',
    account_info: tuple = ('test_user', 'test_user_id', 'test_tenant', 'test_subscription'),
    resource_suffix: str = 'abc123def456',
    run_success: bool = True,
    run_output: dict | str | None = None
):
    """
    Factory for creating a mock azure_resources (az) module.

    Args:
        rg_exists: Whether resource group exists
        rg_name: Resource group name to return
        account_info: Tuple of (user, user_id, tenant, subscription)
        resource_suffix: Unique suffix for resources
        run_success: Default success state for az.run calls
        run_output: Default output for az.run calls

    Returns:
        Mock configured with common azure_resources patterns
    """
    mock_az = Mock()
    mock_az.get_infra_rg_name.return_value = rg_name
    mock_az.create_resource_group.return_value = None
    mock_az.does_resource_group_exist.return_value = rg_exists
    mock_az.get_account_info.return_value = account_info
    mock_az.get_unique_suffix_for_resource_group.return_value = resource_suffix

    # Configure default run output
    if run_output is None:
        run_output = {'outputs': 'test'}

    mock_output = Mock()
    mock_output.success = run_success

    if isinstance(run_output, dict):
        mock_output.json_data = run_output
        mock_output.get.return_value = 'https://test-apim.azure-api.net'
        mock_output.getJson.return_value = ['api1', 'api2']
    else:
        mock_output.text = run_output

    mock_az.run.return_value = mock_output

    return mock_az


def create_mock_utils_module(
    tags: dict | None = None,
    policy_xml: str = '<policies><inbound><base /></inbound></policies>',
    policy_path: str = '/mock/path/policy.xml',
    verify_result: bool = True
):
    """
    Factory for creating a mock utils module.

    Args:
        tags: Infrastructure tags to return
        policy_xml: XML content for policies
        policy_path: Path to policy files
        verify_result: Result of infrastructure verification

    Returns:
        Mock configured with common utils patterns
    """
    if tags is None:
        tags = {'environment': 'test', 'project': 'apim-samples'}

    mock_utils = Mock()
    mock_utils.build_infrastructure_tags.return_value = tags
    mock_utils.read_policy_xml.return_value = policy_xml
    mock_utils.determine_shared_policy_path.return_value = policy_path
    mock_utils.verify_infrastructure.return_value = verify_result

    return mock_utils


def create_sample_policy_fragments(count: int = 2) -> list[PolicyFragment]:
    """
    Factory for creating sample PolicyFragment objects for testing.

    Args:
        count: Number of policy fragments to create

    Returns:
        List of PolicyFragment objects
    """
    return [
        PolicyFragment(
            f'Test-Fragment-{i+1}',
            f'<policy>test{i+1}</policy>',
            f'Test fragment {i+1}'
        )
        for i in range(count)
    ]


def create_sample_apis(count: int = 2) -> list[API]:
    """
    Factory for creating sample API objects for testing.

    Args:
        count: Number of APIs to create

    Returns:
        List of API objects
    """
    return [
        API(
            f'test-api-{i+1}',
            f'Test API {i+1}',
            f'/test{i+1}',
            f'Test API {i+1} description',
            f'<policy>api{i+1}</policy>'
        )
        for i in range(count)
    ]


def create_sample_api_operations(count: int = 2) -> list[APIOperation]:
    """
    Factory for creating sample APIOperation objects for testing.

    Args:
        count: Number of operations to create

    Returns:
        List of APIOperation objects
    """
    verbs = [HTTP_VERB.GET, HTTP_VERB.POST, HTTP_VERB.PUT, HTTP_VERB.DELETE]
    return [
        APIOperation(
            f'operation-{i+1}',
            f'Operation {i+1}',
            verbs[i % len(verbs)],
            f'/resource{i+1}',
            f'<policy>operation{i+1}</policy>'
        )
        for i in range(count)
    ]


# ------------------------------
#    ASSERTION HELPERS
# ------------------------------

def assert_bicep_params_structure(params: dict) -> None:
    """
    Verify bicep parameters have the expected structure.

    Args:
        params: Bicep parameters dictionary to validate

    Raises:
        AssertionError: If structure is invalid
    """
    assert isinstance(params, dict), "Bicep params must be a dict"

    # Common required parameters
    required_keys = ['location', 'resourceSuffix']
    for key in required_keys:
        assert key in params, f"Missing required bicep parameter: {key}"
        assert 'value' in params[key], f"Parameter {key} missing 'value' key"


def assert_infrastructure_components(
    infra,
    expected_min_apis: int = 1,
    expected_min_pfs: int = 6,
    check_rg: bool = True
) -> None:
    """
    Verify infrastructure instance has expected components initialized.

    Args:
        infra: Infrastructure instance to check
        expected_min_apis: Minimum number of APIs expected
        expected_min_pfs: Minimum number of policy fragments expected
        check_rg: Whether to check resource group attributes

    Raises:
        AssertionError: If components don't meet expectations
    """
    # Initialize components
    apis = infra._define_apis()
    pfs = infra._define_policy_fragments()

    assert len(apis) >= expected_min_apis, \
        f"Expected at least {expected_min_apis} APIs, got {len(apis)}"
    assert len(pfs) >= expected_min_pfs, \
        f"Expected at least {expected_min_pfs} policy fragments, got {len(pfs)}"

    if check_rg:
        assert hasattr(infra, 'rg_name'), "Infrastructure missing rg_name"
        assert hasattr(infra, 'rg_location'), "Infrastructure missing rg_location"
        assert infra.rg_name, "rg_name should not be empty"


def assert_api_structure(api: API, check_operations: bool = False) -> None:
    """
    Verify API object has all required fields properly set.

    Args:
        api: API object to validate
        check_operations: Whether to validate operations list

    Raises:
        AssertionError: If API structure is invalid
    """
    assert api.name, "API name should not be empty"
    assert api.displayName, "API displayName should not be empty"
    assert api.path, "API path should not be empty"
    assert hasattr(api, 'operations'), "API missing operations attribute"
    assert hasattr(api, 'tags'), "API missing tags attribute"
    assert hasattr(api, 'productNames'), "API missing productNames attribute"

    if check_operations:
        assert isinstance(api.operations, list), "API operations must be a list"


def assert_policy_fragment_structure(pf: PolicyFragment) -> None:
    """
    Verify PolicyFragment object has all required fields properly set.

    Args:
        pf: PolicyFragment object to validate

    Raises:
        AssertionError: If PolicyFragment structure is invalid
    """
    assert pf.name, "PolicyFragment name should not be empty"
    assert pf.policyXml, "PolicyFragment policyXml should not be empty"
    assert hasattr(pf, 'description'), "PolicyFragment missing description"


# ------------------------------
#    TEST DATA GENERATORS
# ------------------------------

def get_sample_bicep_params() -> dict:
    """
    Get a sample bicep parameters dictionary for testing.

    Returns:
        Dictionary with sample bicep parameters
    """
    return {
        'location': {'value': 'eastus2'},
        'resourceSuffix': {'value': 'abc123'},
        'apimSku': {'value': 'BasicV2'},
        'apis': {'value': []},
        'policyFragments': {'value': []}
    }


def get_sample_infrastructure_params() -> dict:
    """
    Get sample parameters for creating Infrastructure instances.

    Returns:
        Dictionary with common infrastructure parameters
    """
    return {
        'rg_location': 'eastus2',
        'index': 1,
        'apim_sku': APIM_SKU.BASICV2,
        'networkMode': APIMNetworkMode.PUBLIC
    }


# ------------------------------
#    HTTP MOCK FACTORIES
# ------------------------------

def create_mock_http_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str | None = None,
    headers: dict | None = None,
    raise_for_status_error: Exception | None = None
):
    """
    Factory for creating mock HTTP response objects.

    Args:
        status_code: HTTP status code
        json_data: JSON response data
        text: Text response content
        headers: Response headers
        raise_for_status_error: Exception to raise on raise_for_status()

    Returns:
        Mock response object configured for HTTP testing
    """
    if headers is None:
        headers = {'Content-Type': 'application/json'}

    if json_data is not None and text is None:
        text = json_module.dumps(json_data, indent=4)
    elif text is None:
        text = ''

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = headers
    mock_response.text = text

    if json_data is not None:
        mock_response.json.return_value = json_data
    else:
        mock_response.json.side_effect = ValueError("No JSON")

    if raise_for_status_error:
        mock_response.raise_for_status.side_effect = raise_for_status_error
    else:
        mock_response.raise_for_status.return_value = None

    return mock_response


def create_mock_session_with_response(response):
    """
    Factory for creating a mock requests.Session with a predefined response.

    Args:
        response: Mock response object or list of responses

    Returns:
        Mock Session object
    """
    mock_session = MagicMock()

    if isinstance(response, list):
        mock_session.request.side_effect = response
    else:
        mock_session.request.return_value = response

    return mock_session


# ------------------------------
#    CONTEXT MANAGERS FOR PATCHING
# ------------------------------

class MockApimRequestsPatches:
    """
    Context manager for common apimrequests module patches.
    Eliminates the need for @patch decorators on every test.

    Usage:
        with MockApimRequestsPatches() as mocks:
            # mocks.request, mocks.print_message, etc. available
            result = apim.singleGet('/path')
    """

    def __init__(self):
        self.patches = []
        self.mocks = {}

    def __enter__(self):
        patch_targets = [
            ('apimrequests.requests.request', 'request'),
            ('apimrequests.print_message', 'print_message'),
            ('apimrequests.print_info', 'print_info'),
            ('apimrequests.print_error', 'print_error'),
            ('apimrequests.print_val', 'print_val'),
            ('apimrequests.print_ok', 'print_ok')
        ]

        for target, name in patch_targets:
            p = patch(target)
            mock = p.__enter__()
            self.patches.append(p)
            setattr(self, name, mock)
            self.mocks[name] = mock

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for p in reversed(self.patches):
            p.__exit__(exc_type, exc_val, exc_tb)


class MockInfrastructuresPatches:
    """
    Context manager for common infrastructures module patches.

    Usage:
        with MockInfrastructuresPatches() as mocks:
            # mocks.az, mocks.utils available
            infra = Infrastructure(...)
    """

    def __init__(self):
        self.patches = []

    def __enter__(self):
        # Patch az
        self.az_patch = patch('infrastructures.az')
        self.az = self.az_patch.__enter__()
        self.az.get_infra_rg_name.return_value = 'rg-test-infrastructure-01'
        self.az.create_resource_group.return_value = None
        self.az.does_resource_group_exist.return_value = True
        self.az.get_account_info.return_value = ('test_user', 'test_user_id', 'test_tenant', 'test_subscription')
        self.az.get_unique_suffix_for_resource_group.return_value = 'abc123def456'

        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = {'outputs': 'test'}
        mock_output.get.return_value = 'https://test-apim.azure-api.net'
        mock_output.getJson.return_value = ['api1', 'api2']
        self.az.run.return_value = mock_output

        self.patches.append(self.az_patch)

        # Patch utils
        self.utils_patch = patch('infrastructures.utils')
        self.utils = self.utils_patch.__enter__()
        self.utils.build_infrastructure_tags.return_value = {'environment': 'test', 'project': 'apim-samples'}
        self.utils.read_policy_xml.return_value = '<policies><inbound><base /></inbound></policies>'
        self.utils.determine_shared_policy_path.return_value = '/mock/path/policy.xml'
        self.utils.verify_infrastructure.return_value = True

        self.patches.append(self.utils_patch)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for p in reversed(self.patches):
            p.__exit__(exc_type, exc_val, exc_tb)


# ------------------------------
#    CONSOLE OUTPUT CAPTURE
# ------------------------------

def capture_console_output(func: Callable, *args, **kwargs) -> str:
    """
    Capture console logging output from a function call.

    Args:
        func: Function to call
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Captured output as string
    """
    captured_output = io.StringIO()

    logger = logging.getLogger('console')
    previous_level = logger.level
    previous_handlers = list(logger.handlers)
    previous_propagate = logger.propagate

    handler = logging.StreamHandler(captured_output)
    handler.setFormatter(logging.Formatter('%(message)s'))

    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    try:
        func(*args, **kwargs)
        return captured_output.getvalue()
    finally:
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
