"""
Script to show all soft-deleted (not yet purged) API Management and Key Vault resources.
These resources are in a recoverable state and can be restored or purged.
"""

import sys
import io
import argparse
from datetime import datetime
from pathlib import Path

# Configure UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# APIM Samples imports
import azure_resources as az


def _get_suggested_purge_command() -> str:
    """Return a purge command that works from the current working directory."""

    script_path = Path(__file__).resolve()
    cwd_path = Path.cwd().resolve()

    try:
        rel_path = script_path.relative_to(cwd_path)
        return f'python {rel_path.as_posix()} --purge'
    except ValueError:
        return f'python "{script_path}" --purge'


def parse_date(date_str: str) -> str:
    """Parse and format date string for display."""
    if not date_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return date_str


def get_deleted_apim_services() -> list:
    """Get all soft-deleted API Management services."""
    output = az.run('az apim deletedservice list -o json')

    if not output.success:
        print('❌ Failed to retrieve deleted APIM services')
        print(f'   Error: {output.text}')
        return []

    if output.is_json and output.json_data:
        return output.json_data if isinstance(output.json_data, list) else []

    return []


def show_deleted_apim_services(services: list):
    """Show all soft-deleted API Management services."""
    print('\n' + '='*80)
    print('SOFT-DELETED API MANAGEMENT SERVICES')
    print('='*80 + '\n')

    if not services:
        print('✅ No soft-deleted API Management services found')
        return

    print(f'Found {len(services)} soft-deleted API Management service(s):\n')

    for i, service in enumerate(services, 1):
        service_name = service.get('name', 'Unknown')
        location = service.get('location', 'Unknown')
        deletion_date = parse_date(service.get('deletionDate', ''))
        scheduled_purge = parse_date(service.get('scheduledPurgeDate', ''))
        service_id = service.get('serviceId', 'N/A')

        print(f'{i}/{len(services)}:')
        print(f'    Service Name     : {service_name}')
        print(f'    Location         : {location}')
        print(f'    Deletion Date    : {deletion_date}')
        print(f'    Purge Date       : {scheduled_purge}')
        print(f'    Service ID       : {service_id}')
        print(f'    Purge AZ CLI     : az apim deletedservice purge --service-name {service_name} --location "{location}"')
        print()

    print('To purge an APIM service:')
    print('   az apim deletedservice purge --service-name <name> --location <location>')
    print()
    print('To restore an APIM service (if supported):')
    print('   Check Azure portal or contact Azure support')
    print()


def get_deleted_key_vaults() -> list:
    """Get all soft-deleted Key Vaults."""
    output = az.run('az keyvault list-deleted -o json')

    if not output.success:
        print('❌ Failed to retrieve deleted Key Vaults')
        print(f'   Error: {output.text}')
        return []

    if output.is_json and output.json_data:
        return output.json_data if isinstance(output.json_data, list) else []

    return []


def show_deleted_key_vaults(vaults: list):
    """Show all soft-deleted Key Vaults."""
    print('\n' + '='*80)
    print('SOFT-DELETED KEY VAULTS')
    print('='*80 + '\n')

    if not vaults:
        print('✅ No soft-deleted Key Vaults found')
        return

    # Separate vaults by purge protection status
    protected_vaults = [v for v in vaults
                       if v.get('properties', {}).get('purgeProtectionEnabled', False)]

    print(f'Found {len(vaults)} soft-deleted Key Vault(s):\n')

    for i, vault in enumerate(vaults, 1):
        vault_name = vault.get('name', 'Unknown')
        location = vault.get('properties', {}).get('location', 'Unknown')
        deletion_date = parse_date(vault.get('properties', {}).get('deletionDate', ''))
        scheduled_purge = parse_date(vault.get('properties', {}).get('scheduledPurgeDate', ''))
        vault_id = vault.get('properties', {}).get('vaultId', 'N/A')
        purge_protection = vault.get('properties', {}).get('purgeProtectionEnabled', False)

        print(f'{i}/{len(vaults)}:')
        print(f'    Vault Name       : {vault_name}')
        print(f'    Location         : {location}')
        print(f'    Deletion Date    : {deletion_date}')
        print(f'    Purge Date       : {scheduled_purge}')
        print(f'    Purge Protection : {"🔒 ENABLED" if purge_protection else "❌ Disabled"}')
        print(f'    Vault ID         : {vault_id}')
        print(f'    Purge AZ CLI     : az keyvault purge --name {vault_name} --location "{location}" --no-wait')
        print()

    if protected_vaults:
        print(f'⚠️  {len(protected_vaults)} vault(s) have PURGE PROTECTION enabled and cannot be manually purged.')
        print('   These vaults will be automatically purged on their scheduled purge date.')
        print()

    print('To purge a Key Vault (without purge protection):')
    print('   az keyvault purge --name <name> --location <location> --no-wait')
    print()
    print('To recover a Key Vault:')
    print('   az keyvault recover --name <name>')
    print()


def purge_apim_services(services: list) -> int:
    """Purge all soft-deleted APIM services."""
    if not services:
        return 0

    print('\n' + '='*80)
    print('PURGING API MANAGEMENT SERVICES')
    print('='*80 + '\n')

    success_count = 0
    failed_count = 0

    for i, service in enumerate(services, 1):
        service_name = service.get('name', 'Unknown')
        location = service.get('location', 'Unknown')

        print(f'[{i}/{len(services)}] Purging APIM service: {service_name} (location: {location})')

        output = az.run(
            f'az apim deletedservice purge --service-name {service_name} --location {location} --no-wait',
            'Successfully initiated purge',
            'Failed to initiate purge'
        )

        if output.success:
            print('   ✅ Successfully initialized purge\n')
            success_count += 1
        else:
            print('   ❌ Failed to initiage purge\n')
            failed_count += 1

    print(f'APIM Purge Results: {success_count} succeeded, {failed_count} failed')
    return success_count


def purge_key_vaults(vaults: list) -> tuple[int, int]:
    """Purge all soft-deleted Key Vaults that don't have purge protection.

    Returns:
        Tuple of (success_count, skipped_count)
    """
    if not vaults:
        return 0, 0

    # Filter out vaults with purge protection
    purgeable_vaults = [v for v in vaults
                       if not v.get('properties', {}).get('purgeProtectionEnabled', False)]
    protected_vaults = [v for v in vaults
                       if v.get('properties', {}).get('purgeProtectionEnabled', False)]

    print('\n' + '='*80)
    print('PURGING KEY VAULTS')
    print('='*80 + '\n')

    if protected_vaults:
        print(f'ℹ️  Skipping {len(protected_vaults)} vault(s) with purge protection enabled:')
        for vault in protected_vaults:
            vault_name = vault.get('name', 'Unknown')
            print(f'   🔒 {vault_name} - purge protection prevents manual deletion')
        print()

    if not purgeable_vaults:
        print('ℹ️  No purgeable Key Vaults (all have purge protection enabled)')
        return 0, len(protected_vaults)

    success_count = 0
    failed_count = 0

    for i, vault in enumerate(purgeable_vaults, 1):
        vault_name = vault.get('name', 'Unknown')
        location = vault.get('properties', {}).get('location', 'Unknown')

        print(f'[{i}/{len(purgeable_vaults)}] Purging Key Vault: {vault_name} (location: {location})')

        output = az.run(
            f'az keyvault purge --name {vault_name} --location {location} --no-wait',
            'Successfully initiated purge',
            'Failed to initiage purge'
        )

        if output.success:
            print('   ✅ Successfully initiated purge\n')
            success_count += 1
        else:
            print('   ❌ Failed to initiate purge\n')
            failed_count += 1

    print(f'Key Vault Purge Results: {success_count} succeeded, {failed_count} failed, '
          f'{len(protected_vaults)} skipped (purge protected)')
    return success_count, len(protected_vaults)


def confirm_purge(apim_count: int, kv_count: int, kv_protected: int) -> bool:
    """Ask user to confirm purge operation."""
    print('\n' + '='*80)
    print('⚠️  PURGE CONFIRMATION')
    print('='*80)
    print('\nYou are about to PERMANENTLY DELETE the following resources:')
    print(f'  • {apim_count} API Management service(s)')
    print(f'  • {kv_count} Key Vault(s)')
    if kv_protected > 0:
        print(f'\nℹ️  Note: {kv_protected} Key Vault(s) with purge protection will be skipped')
    print('\n⚠️  WARNING: This action is IRREVERSIBLE!')
    print('   Once purged, these resources CANNOT be recovered.')
    print('\nType "PURGE ALL" to confirm (or press Enter to cancel): ', end='')

    try:
        confirmation = input().strip()
        return confirmation == 'PURGE ALL'
    except (KeyboardInterrupt, EOFError):
        print('\n\n❌ Operation cancelled by user')
        return False


def main():
    """Main function to show and optionally purge all soft-deleted resources."""
    parser = argparse.ArgumentParser(
        description='Show and optionally purge soft-deleted Azure resources (APIM and Key Vaults)'
    )
    parser.add_argument(
        '--purge',
        action='store_true',
        help='Prompt to purge all soft-deleted resources'
    )
    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Skip confirmation prompt when purging (use with caution!)'
    )

    args = parser.parse_args()

    print('\n' + '='*80)
    print('AZURE SOFT-DELETED RESOURCES')
    print('='*80)
    print('\nChecking for soft-deleted resources in the current subscription...')

    # Get current subscription info
    output = az.run('az account show -o json')
    if output.success and output.is_json and output.json_data:
        print(f"\nSubscription    : {output.json_data.get('name', 'Unknown')}")
        print(f"Subscription ID : {output.json_data.get('id', 'Unknown')}\n")

    # Get all resources
    apim_services = get_deleted_apim_services()
    key_vaults = get_deleted_key_vaults()

    # Show resources
    show_deleted_apim_services(apim_services)
    show_deleted_key_vaults(key_vaults)

    apim_count = len(apim_services)
    kv_count = len(key_vaults)
    total_count = apim_count + kv_count

    # Summary
    print('='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total soft-deleted APIM services : {apim_count}')
    print(f'Total soft-deleted Key Vaults    : {kv_count}')
    print()

    if not total_count:
        print('✅ No soft-deleted resources found in this subscription.')
        print()
        return 0

    print('⚠️  Note: Soft-deleted resources will be automatically purged on their')
    print('   scheduled purge date. You can manually purge them sooner or recover')
    print('   them (for Key Vaults) before the purge date.')

    # Handle purge option
    if args.purge:
        # Count protected Key Vaults
        kv_protected = sum(1 for v in key_vaults
                          if v.get('properties', {}).get('purgeProtectionEnabled', False))
        kv_purgeable = kv_count - kv_protected

        # Check if there's actually anything to purge
        total_purgeable = apim_count + kv_purgeable
        if not total_purgeable:
            print('\nℹ️  No purgeable resources found.')
            if kv_protected > 0:
                print(f'   All {kv_protected} Key Vault(s) have purge protection enabled.')
                print('   These will be automatically purged on their scheduled purge dates.')
            print()
            return 0

        # Ask for confirmation unless --yes flag is provided
        if args.yes or confirm_purge(apim_count, kv_purgeable, kv_protected):
            print('\n🗑️  Starting purge operation...\n')

            apim_purged = purge_apim_services(apim_services)
            kv_purged, kv_skipped = purge_key_vaults(key_vaults)

            print('\n' + '='*80)
            print('PURGE SUMMARY')
            print('='*80)
            print(f'API Management services purged: {apim_purged}/{apim_count}')
            print(f'Key Vaults purged: {kv_purged}/{kv_purgeable}')
            if kv_skipped > 0:
                print(f'Key Vaults skipped (purge protected): {kv_skipped}')
            print(f'Total resources purged: {apim_purged + kv_purged}/{apim_count + kv_purgeable}')
            print()

            expected_purged = apim_count + kv_purgeable
            if apim_purged + kv_purged == expected_purged:
                print('✅ All purgeable resources successfully purged')
            else:
                print('⚠️  Some resources failed to purge. Check the errors above.')
        else:
            print('\n❌ Purge operation cancelled')
    else:
        print('\n💡 To purge all these resources, run:')
        print(f'   {_get_suggested_purge_command()}')

    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
