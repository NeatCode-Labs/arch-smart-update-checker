# HOW_ASUC_WORKS.md

## Overview

Arch Smart Update Checker (ASUC) is a security-focused update manager for Arch Linux and its derivatives. It provides both a modern GUI and a CLI, helping users stay informed about important news and advisories before updating their system. ASUC is designed to be safe, robust, and user-friendly, with advanced detection, news filtering, and secure update mechanisms.

---

## High-Level Architecture

```mermaid
flowchart TD
    A["User Action (GUI/CLI)"] --> B["ASUC Core Logic"]
    B --> C1["Distribution & Kernel Detection"]
    B --> C2["News Fetching & Filtering"]
    B --> C3["Package Manager Operations"]
    C3 --> D1["Sync Database"]
    C3 --> D2["Check for Updates"]
    C3 --> D3["Update All"]
    B --> E["Security & Validation"]
    B --> F["UI Feedback & History"]
```

---

## Key Components

| Component                | Description                                                                 |
|--------------------------|-----------------------------------------------------------------------------|
| **GUI (Tkinter)**        | Main user interface, dashboard, quick actions, news, and update history     |
| **CLI**                  | Command-line interface for advanced/automated use                           |
| **Distribution Detector**| Detects your Linux distribution and kernel for tailored news/updates        |
| **News Fetcher**         | Downloads and filters news relevant to your installed packages              |
| **Package Manager**      | Interfaces securely with `pacman` for all package operations                |
| **Security Layer**       | Input validation, subprocess sandboxing, authentication, and audit logging  |
| **Thread Manager**       | Runs long operations in the background to keep UI responsive                |

---

## What Happens When...

### 1. **User Clicks "Sync Database"**

**Goal:** Refresh the local package database from the latest mirror data.

**Step-by-step:**
1. **Confirmation Dialog:** User is asked to confirm the sync action.
2. **Progress Dialog:** A new window shows sync progress and status.
3. **Authentication:**
   - Tries `pkexec` (polkit) for privilege escalation.
   - If on a hardened kernel or `pkexec` fails, falls back to `sudo` (with or without password, using Zenity for password prompt if needed).
   - If passwordless sudo is available, uses it directly.
4. **Command Execution:** Runs `pacman -Sy --noconfirm` securely (no shell, no injection risk).
5. **Real-time Output:** Progress is streamed live to the dialog.
6. **Result Handling:**
   - On success: UI updates, sync time is refreshed.
   - On failure: Error is shown, with hints if authentication failed (e.g., missing polkit agent).
7. **Threading:** All heavy work is done in a background thread to keep the UI responsive.

**Diagram:**
```mermaid
sequenceDiagram
    participant U as User
    participant G as GUI
    participant S as Secure Subprocess
    U->>G: Clicks "Sync Database"
    G->>G: Show confirmation dialog
    G->>G: Show progress dialog
    G->>S: Start sync (pkexec/sudo)
    S->>G: Stream output
    S-->>G: Return success/failure
    G->>U: Show result, update sync time
```

---

### 2. **Distribution and Kernel Detection**

**How it works:**
- **Distribution:** Checks for specific files (e.g., `/etc/arch-release`, `/etc/manjaro-release`) to identify the distro. If not found, reads `/etc/os-release` and parses `ID` or `NAME` fields.
- **Kernel:** Uses `uname -r` to get the kernel version and checks for keywords like "hardened" to adjust authentication methods.
- **Feeds:** Based on detected distro, selects the right news feeds (e.g., Manjaro, EndeavourOS, etc.).
- **Architecture:** Uses `platform.machine()` to detect system architecture.

**Why it matters:** Ensures the app fetches the right news and uses the correct package manager commands for your system.

---

### 3. **User Clicks "Search for Updates"**

**Goal:** Check for available package updates and show relevant news.

**Step-by-step:**
1. **UI Animation:** Dashboard shows a "checking" animation.
2. **Background Thread:** Starts a secure thread to avoid freezing the UI.
3. **Cache Clearing:** Clears package manager cache to ensure fresh results.
4. **Update Check:** Calls `pacman -Qu` (via a secure wrapper) to get a list of upgradable packages.
5. **News Fetching:** Downloads all configured news feeds (RSS/Atom).
6. **News Filtering:**
   - Extracts package names from news items.
   - Matches news to packages that have updates.
   - Only shows news relevant to your system and pending updates.
7. **UI Update:** Shows the list of updates and relevant news in a new frame.
8. **Dashboard Refresh:** Updates stats cards and last check time.

**Diagram:**
```mermaid
flowchart TD
    A["User clicks Search for Updates"] --> B["Start background thread"]
    B --> C["Clear cache"]
    C --> D["Check for updates (pacman -Qu)"]
    D --> E["Fetch news feeds"]
    E --> F["Filter news for updated packages"]
    F --> G["Update UI with results"]
```

---

### 4. **User Clicks "Update All"**

**Goal:** Perform a full system upgrade (`pacman -Syu`).

**Step-by-step:**
1. **Confirmation Dialog:** User is warned this will update all packages.
2. **Progress Dialog:** Shows real-time update output.
3. **Authentication:** Uses `pkexec` or `sudo` as with sync.
4. **Command Execution:** Runs `pacman -Syu --noconfirm` securely.
5. **Output Streaming:** All output is shown live in the dialog.
6. **Result Handling:**
   - On success: UI updates, update history is recorded.
   - On failure: Error is shown, with troubleshooting hints.
7. **Threading:** Runs in a background thread for safety and responsiveness.

---

## When is Update History Recorded?

Update history in ASUC is recorded automatically after updates, so you always have an audit trail of what changed on your system.

**Update history is recorded after:**
- **A successful full system update** (when you click "Update All" or run a system upgrade via the GUI/CLI).
- **Selective package updates** (when you apply updates from the updates/news screen).

**How it works:**
- After the update process completes, ASUC parses the output to determine which packages were actually updated (excluding reinstalls).
- It collects version information (old/new) for each updated package when possible.
- A new history entry is created, including:
  - Timestamp
  - List of updated packages
  - Success/failure status
  - Exit code
  - Duration of the update
  - Version info (if available)
- This entry is saved to the update history file in your config directory.
- The update history panel in the GUI is refreshed to show the new entry immediately.

**Note:** If no packages were actually updated (e.g., only reinstalls), no history entry is recorded.

---

## Security and Safety

- **No Shell Execution:** All system commands are run as arrays, never as shell strings, preventing injection.
- **Input Validation:** All user and system inputs are sanitized.
- **Authentication:** Uses polkit (`pkexec`) or `sudo` with password prompt fallback, never stores passwords.
- **Thread Management:** All long-running or privileged operations are run in managed background threads.
- **Audit Logging:** Security events and errors are logged for troubleshooting.
- **AppArmor/SELinux:** Optional security profiles are provided for advanced users.

---

## Update and News Matching Logic

- **Package Extraction:** Uses pattern matching to find package names in news items.
- **Relevance Filtering:** Only news affecting packages you have (and that have updates) is shown.
- **Distribution Awareness:** News feeds are tailored to your detected distribution.

---

## Example Table: Authentication Fallbacks

| Scenario                | Method Used         | User Prompted? | Notes                                 |
|-------------------------|--------------------|---------------|---------------------------------------|
| Standard kernel, polkit | pkexec             | Yes           | Default, most secure                  |
| Hardened kernel         | sudo/zenity        | Yes           | Zenity password dialog if needed      |
| Passwordless sudo       | sudo (no password) | No            | Used if available                     |
| No polkit agent         | Error shown        | N/A           | User is told how to fix               |

---

## Summary

ASUC is designed to be both powerful and safe. It keeps you informed about important news before you update, detects your system details automatically, and always runs privileged operations securely. All heavy work is done in the background, so the app stays responsive and user-friendly.

---

*For more details, see the source code or reach out via GitHub Issues!* 