# AppArmor Profile for Arch Smart Update Checker

This directory contains the AppArmor security profile for the Arch Smart Update Checker application.

## Overview

The AppArmor profile provides mandatory access control (MAC) for the application, restricting its access to system resources based on the principle of least privilege. This adds an additional layer of security beyond the application's built-in security measures.

## Installation

### Prerequisites

1. Install AppArmor:
   ```bash
   sudo pacman -S apparmor
   ```

2. Enable AppArmor service:
   ```bash
   sudo systemctl enable --now apparmor
   ```

3. Add AppArmor to kernel parameters (if not already present):
   - Edit `/etc/default/grub`
   - Add `apparmor=1 security=apparmor` to `GRUB_CMDLINE_LINUX_DEFAULT`
   - Run `sudo grub-mkconfig -o /boot/grub/grub.cfg`
   - Reboot

### Installing the Profile

Run the installation script as root:
```bash
sudo ./install.sh
```

Or manually:
```bash
sudo cp usr.bin.asuc /etc/apparmor.d/
sudo apparmor_parser -r /etc/apparmor.d/usr.bin.asuc
```

## Testing

1. Put the profile in complain mode:
   ```bash
   sudo aa-complain /usr/bin/asuc-cli
   sudo aa-complain /usr/bin/asuc-gui
   ```

2. Run the application normally and check for denials:
   ```bash
   sudo journalctl -f | grep apparmor
   ```

3. Once satisfied, enforce the profile:
   ```bash
   sudo aa-enforce /usr/bin/asuc-cli
   sudo aa-enforce /usr/bin/asuc-gui
   ```

## Profile Details

The profile restricts the application to:

- **Read-only access to:**
  - System information files
  - Python libraries
  - Pacman database
  - SSL certificates
  - Theme and icon files

- **Read-write access to:**
  - User configuration directory (`~/.config/asuc/`)
  - User cache directory (`~/.cache/asuc/`)
  - Temporary files it creates

- **Execute access to:**
  - Python interpreter
  - Package management tools (pacman, checkupdates)
  - Essential system utilities
  - Terminal emulators and text editors

- **Network access:**
  - For RSS feed fetching
  - For package downloads (when elevated)

- **Explicitly denied access to:**
  - SSH keys
  - GPG keys
  - Password stores
  - System configuration files
  - Boot directory
  - Root directory

## Troubleshooting

If the application fails to work properly with the profile enforced:

1. Check AppArmor logs:
   ```bash
   sudo aa-logprof
   ```

2. View denied operations:
   ```bash
   sudo journalctl -b | grep "apparmor.*DENIED"
   ```

3. Temporarily disable the profile:
   ```bash
   sudo aa-disable /usr/bin/asuc-cli
   sudo aa-disable /usr/bin/asuc-gui
   ```

4. Report issues to the project maintainers with the denial logs.

## Customization

If you need to customize the profile for your system:

1. Copy the profile to a new file:
   ```bash
   sudo cp /etc/apparmor.d/usr.bin.asuc /etc/apparmor.d/usr.bin.asuc.local
   ```

2. Edit the local copy and add your rules

3. Reload the profile:
   ```bash
   sudo apparmor_parser -r /etc/apparmor.d/usr.bin.asuc
   ```

## Security Considerations

- The profile assumes the application is installed in standard locations
- Custom Python installations may require profile modifications
- The profile allows network access for RSS feeds and package downloads
- Elevated operations (sudo/pkexec) transition to a less restrictive profile 