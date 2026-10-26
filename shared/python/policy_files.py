"""Locate and read sample and shared APIM policy files.

Autoreload: reload_safe
Stateless path and file-loading functions support automatic reload. Reread changed policy files explicitly.
"""

import inspect
import os
from pathlib import Path

# APIM Samples imports
from apimtypes import find_project_root, get_project_root
from console import print_warning


def read_and_modify_policy_xml(policy_xml_filepath: str, replacements: dict[str, str], sample_name: str = None) -> str:
    """
    Read and return the contents of a policy XML file, then modifies it by replacing placeholders with provided values.

    Args:
        policy_xml_filepath (str): Path to the policy XML file.

    Returns:
        str: Contents of the policy XML file.
    """

    policy_xml_filepath = determine_policy_path(policy_xml_filepath, sample_name)
    # print(f'📄 Reading policy XML from : {policy_xml_filepath}')  # debug

    # Read the specified policy XML file
    with open(policy_xml_filepath, 'r', encoding='utf-8') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

    if replacements is not None and isinstance(replacements, dict):
        # Replace placeholders in the policy XML with provided values
        for key, value in replacements.items():
            placeholder = '{' + key + '}'

            if placeholder in policy_template_xml:
                policy_template_xml = policy_template_xml.replace(placeholder, value)
            else:
                print_warning(f"Placeholder '{placeholder}' not found in the policy XML file.")

    return policy_template_xml


def determine_shared_policy_path(policy_xml_filename: str) -> str:
    """Determine the full path to a shared APIM policy fragment file."""
    return str(Path(find_project_root()) / 'shared' / 'apim-policies' / 'fragments' / policy_xml_filename)


def determine_policy_path(policy_xml_filepath_or_filename: str, sample_name: str = None) -> str:
    """Resolve a sample policy path, preferring the canonical policy directory."""
    # Determine if this is a full path or just a filename
    path_obj = Path(policy_xml_filepath_or_filename)

    # Legacy mode check: if named_values is None, always treat as legacy (backwards compatibility)
    # OR if it looks like a path (contains separators or is absolute)
    # Note: Check for leading slash to handle POSIX paths on Windows
    if path_obj.is_absolute() or policy_xml_filepath_or_filename.startswith('/') or '/' in policy_xml_filepath_or_filename or '\\' in policy_xml_filepath_or_filename:
        # Legacy mode: treat as full path
        policy_xml_filepath = policy_xml_filepath_or_filename
    else:
        # Smart mode: auto-detect sample directory
        if sample_name is None:
            try:
                # Get the current frame's filename (the notebook or script calling this function)
                frame = inspect.currentframe()
                caller_frame = frame.f_back

                # Try to get the filename from the caller's frame
                if hasattr(caller_frame, 'f_globals') and '__file__' in caller_frame.f_globals:
                    caller_file = caller_frame.f_globals['__file__']
                    caller_path = Path(caller_file).resolve()
                else:
                    # Fallback for Jupyter notebooks: use current working directory
                    caller_path = Path(os.getcwd()).resolve()

                # Walk up the directory tree to find the samples directory structure
                current_path = caller_path.parent if caller_path.is_file() else caller_path

                # Look for samples directory in the path
                path_parts = current_path.parts
                if 'samples' in path_parts:
                    samples_index = path_parts.index('samples')
                    if samples_index + 1 < len(path_parts):
                        sample_name = path_parts[samples_index + 1]
                    else:
                        raise ValueError('Could not detect sample name from path')
                else:
                    raise ValueError('Not running from within a samples directory')

            except Exception as e:
                raise ValueError(f'Could not auto-detect sample name. Please provide sample_name parameter explicitly. Error: {e}') from e

        # Prefer the canonical policy directory while migrated samples coexist
        # with legacy samples that still keep policy files at the sample root.
        project_root = get_project_root()
        sample_path = Path(project_root) / 'samples' / sample_name
        canonical_path = sample_path / 'apim-policies' / policy_xml_filepath_or_filename
        legacy_path = sample_path / policy_xml_filepath_or_filename
        policy_xml_filepath = str(canonical_path if canonical_path.exists() else legacy_path)

    return policy_xml_filepath


def read_policy_xml(policy_xml_filepath_or_filename: str, named_values: dict[str, str] = None, sample_name: str = None) -> str:
    """
    Read and return the contents of a policy XML file, with optional named value formatting.

    Can work in two modes:
    1. Legacy mode: Pass a full file path (backwards compatible)
    2. Smart mode: Pass just a filename and auto-detect sample directory

    Args:
        policy_xml_filepath_or_filename (str): Full path to policy XML file OR just filename for auto-detection.
        named_values (dict[str, str], optional): Dictionary of named values to format in the policy XML.
        sample_name (str, optional): Override the auto-detected sample name if needed.

    Returns:
        str: Contents of the policy XML file with optional named values formatted.

    Examples:
        # Legacy usage - full path
        policy_xml = read_policy_xml('/path/to/policy.xml')

        # Smart usage - auto-detects sample directory
        policy_xml = read_policy_xml('hr_all_operations.xml', {
            'jwt_signing_key': jwt_key_name,
            'hr_member_role_id': 'HRMemberRoleId'
        })
    """

    policy_xml_filepath = determine_policy_path(policy_xml_filepath_or_filename, sample_name)
    # print(f'📄 Reading policy XML from : {policy_xml_filepath}')  # debug

    # Read the specified policy XML file
    with open(policy_xml_filepath, 'r', encoding='utf-8') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

    # Apply named values formatting if provided
    if named_values is not None and isinstance(named_values, dict):
        # Format the policy XML with named values (double braces for APIM named value syntax)
        formatted_replacements = {}
        for placeholder, named_value in named_values.items():
            formatted_replacements[placeholder] = '{{' + named_value + '}}'

        # Apply the replacements
        policy_template_xml = policy_template_xml.format(**formatted_replacements)

    return policy_template_xml
