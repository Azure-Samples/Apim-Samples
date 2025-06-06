# Dev Container Setup Notes

This document summarizes the improvements made to the dev container configuration for cross-platform compatibility and better user experience.

## 🔧 Key Improvements Made

### 1. Fixed Azure CLI Feature Configuration
- **Issue**: Invalid version string in `devcontainer.json`
- **Fix**: Updated Azure CLI feature to use `"version": "latest"`

### 2. Cross-Platform Azure CLI Authentication
- **Issue**: Azure CLI config mounting was Windows-specific and caused container startup failures
- **Solution**: Commented out automatic mounting; users now sign in with tenant-specific `az login --tenant <your-tenant>` inside container
- **Benefits**: 
  - Works on Windows, macOS, and Linux
  - No more container startup failures
  - Clear authentication flow

### 3. Interactive Azure CLI Configuration (Enhanced)
- **Created**: `configure-azure-mount.py` - Interactive setup script
- **Enhanced**: Integrated into automatic dev container setup process
- **Features**:
  - Automatic platform detection (Windows, macOS, Linux)
  - User choice between mounting local config vs manual login
  - Automatic devcontainer.json configuration
  - Creates backups before making changes
  - **NEW**: Integrated into initial setup flow with appropriate messaging
  - **NEW**: Environment variable detection for initial vs. manual setup
- **Benefits**:
  - No more manual editing of JSON files
  - Platform-appropriate configuration
  - Clear guidance for users
  - **NEW**: Seamless integration with dev container startup
  - **NEW**: Context-aware instructions based on setup phase
- **Updated**: Both `setup.sh` and `setup.ps1` to include interactive configuration
- **Enhanced**: Instructions adapt based on whether it's initial setup or manual configuration

### 4. Enhanced Documentation
- **Updated**: `.devcontainer/README.md` with clear authentication instructions
- **Updated**: Root `README.md` with separate dev container vs. local setup sections
- **Added**: Reference to interactive configuration script

### 5. Improved Verification Script
- **Enhanced**: Better error handling for missing tools
- **Added**: Clear next steps and troubleshooting guidance
- **Fixed**: Graceful handling when Azure CLI is not available

## 🏗️ Current Configuration

### Dev Container Features
- **Base**: Python 3.12 on Debian Bullseye
- **Azure CLI**: Latest version with automatic installation
- **Extensions**: Full Jupyter, Python, Azure, and GitHub Copilot support
- **Environment**: PYTHONPATH configured for shared modules

### Authentication Approach
The container now supports **both** approaches with easy configuration:

#### Option 1: Interactive Configuration (New!)
```bash
python .devcontainer/configure-azure-mount.py
```
This script automatically:
- Detects your platform
- Prompts for your preference
- Configures devcontainer.json appropriately
- Provides clear next steps

#### Option 2: Manual Login (Universal)
```bash
# Log in to your specific Azure tenant
az login --tenant <your-tenant-id-or-domain>

# Set your target subscription
az account set --subscription <your-subscription-id-or-name>

# Verify your context
az account show
```

#### Option 3: Platform-Specific Mounting (Advanced)
Configured automatically by the interactive script based on your platform.

## 🧪 Testing

### New Automated Setup Flow (Latest Enhancement)
1. **Container Creation**: User creates dev container (Codespaces or VS Code)
2. **Automatic Installation**: Dependencies install automatically via `postCreateCommand`
3. **Interactive Configuration**: User is prompted during setup to configure Azure CLI authentication:
   - Option 1: Mount local Azure config (preserves authentication between rebuilds)
   - Option 2: Use manual tenant-specific login (requires `az login --tenant <your-tenant>` after each container start)  
   - Option 3: Configure manually later
4. **Intelligent Instructions**: Next steps adapt based on user's choice and setup context
5. **Ready to Go**: Environment is fully configured for APIM development

### Manual Configuration (Anytime)
Users can reconfigure Azure CLI authentication at any time:
```bash
python .devcontainer/configure-azure-mount.py
```

### Verification Process
1. Start dev container (automated setup runs automatically)
2. Run: `python .devcontainer/verify-setup.py`
3. Run: `az login --tenant <your-tenant-id-or-domain>`
4. Set subscription: `az account set --subscription <your-subscription-id-or-name>`
5. Execute: `shared/jupyter/verify-az-account.ipynb`

### Expected Results
- All Python packages installed ✅
- Jupyter kernel "APIM Samples Python" available ✅
- Azure CLI functional after login ✅
- Infrastructure notebooks ready to execute ✅

## 🔮 Future Considerations

1. **Platform Detection**: Could implement automatic platform detection for mounts
2. **Service Principal**: Consider supporting service principal authentication for CI/CD scenarios
3. **Extension Updates**: Monitor for new Azure/Python extensions that could enhance the experience
4. **Container Registry**: Consider hosting a pre-built container image for faster startup

## 🤝 Contributing

When making changes to the dev container:
1. Test on multiple platforms (Windows, macOS, Linux)
2. Update documentation to reflect changes
3. Run the verification script to ensure functionality
4. Consider backward compatibility for existing users

## 📞 Support

If users encounter issues:
1. Check the verification script output
2. Review `.devcontainer/README.md` troubleshooting section
3. Try rebuilding the container
4. Ensure Azure CLI login is successful

---

*Last updated: December 2024*
