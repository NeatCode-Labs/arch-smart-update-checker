# SELinux Policy for Arch Smart Update Checker

This directory contains the SELinux security policy for the Arch Smart Update Checker application.

## Overview

The SELinux policy provides mandatory access control (MAC) using type enforcement. It creates a confined domain (`asuc_t`) for the application, restricting its access to only necessary system resources.

## Prerequisites

SELinux on Arch Linux requires:

1. **SELinux-enabled kernel**: Install from AUR or compile custom kernel
2. **SELinux userspace tools**: Available in AUR
3. **Policy development files**: `selinux-policy-devel` or equivalent

**Note**: Arch Linux does not ship with SELinux by default. Setting up SELinux on Arch requires significant system modifications.

## Installation

### Quick Install

Run the installation script as root:
```bash
sudo ./install.sh
```

### Manual Installation

1. Build the policy module:
   ```bash
   make
   ```

2. Install the module:
   ```bash
   sudo make install
   ```

3. Relabel files:
   ```bash
   sudo make relabel
   ```

## Policy Structure

- **asuc.te** - Type Enforcement rules defining permissions
- **asuc.fc** - File Context definitions for labeling files
- **asuc.if** - Interface definitions for interaction with other policies
- **Makefile** - Build configuration

## Security Domains

### asuc_t (Main Domain)
- Runs the application with restricted permissions
- Read-only access to system files
- Read-write access to user configuration
- Network access for RSS feeds
- Can execute package management tools

### asuc_elevated_t (Elevated Domain)
- Transitions from asuc_t via sudo
- Additional permissions for package installation
- Can modify system packages

## File Types

- **asuc_exec_t** - Executable files
- **asuc_config_t** - Configuration files
- **asuc_log_t** - Log files  
- **asuc_cache_t** - Cache files
- **asuc_tmp_t** - Temporary files
- **asuc_lock_t** - Lock files

## Testing

1. **Set permissive mode for testing**:
   ```bash
   sudo semanage permissive -a asuc_t
   ```

2. **Run the application and check for denials**:
   ```bash
   sudo ausearch -m avc -ts recent
   ```

3. **Analyze denials**:
   ```bash
   sudo audit2allow -a -l -r
   ```

4. **Switch to enforcing mode**:
   ```bash
   sudo semanage permissive -d asuc_t
   ```

## Troubleshooting

### View Current Status
```bash
# Check if module is loaded
sudo semodule -l | grep asuc

# View file contexts
sudo semanage fcontext -l | grep asuc

# Check current mode
getenforce
```

### Common Issues

1. **Module won't load**: Check for syntax errors with `checkmodule`
2. **Permission denied**: Check AVC denials in audit log
3. **Files not labeled**: Run `sudo make relabel`

### Debug Commands
```bash
# Real-time monitoring
sudo tail -f /var/log/audit/audit.log | grep AVC

# Generate policy suggestions
sudo audit2allow -a -M asuc-local

# Check file labels
ls -Z /usr/bin/asuc-*
```

## Customization

To add local modifications:

1. Create local policy file:
   ```bash
   sudo audit2allow -a -M asuc-local
   ```

2. Review generated rules in `asuc-local.te`

3. Install local modifications:
   ```bash
   sudo semodule -i asuc-local.pp
   ```

## Uninstallation

Remove the policy module:
```bash
sudo make uninstall
```

## Security Considerations

- Policy assumes standard Arch Linux file locations
- Network access is allowed for package downloads
- Transitions to elevated domain require authentication
- Some denials are expected and silenced (dontaudit rules)

## Integration with Other Policies

The policy includes interfaces for:
- User domain transitions
- DBus communication
- Configuration management
- Log file access

Other policies can use these interfaces to interact safely with ASUC. 