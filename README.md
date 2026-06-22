# BC250 Manager

BC250 Manager is a Python 3.13 desktop application built with PySide6.

This initial version focuses on the application skeleton:

- A main window with left-side navigation.
- Separate modules for Dashboard, Disks, Steam, EmuDeck, and Settings.
- A clean package structure for future feature work.

## Disk Detection

The Disks module uses a dedicated `DiskManager` service to detect supported
partitions with `lsblk -J`. The GUI does not execute shell commands directly.

This feature is read-only:

- It does not modify `fstab`.
- It does not mount partitions.
- It does not require root permissions.

## Development

Install dependencies in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Run the app:

```powershell
bc250-manager
```

Or run the module directly:

```powershell
python -m bc250_manager
```
