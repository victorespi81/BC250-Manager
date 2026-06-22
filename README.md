# BC250 Manager

BC250 Manager is a Python 3.13 desktop application built with PySide6.

This initial version focuses on the application skeleton:

- A main window with left-side navigation.
- Separate modules for Dashboard, Disks, Steam, EmuDeck, and Settings.
- A clean package structure for future feature work.

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
