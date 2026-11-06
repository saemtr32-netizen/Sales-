# Nexvant Engineering for Windows

The desktop controller starts the full sales application on this PC and opens it in your browser. It has Start, Open application, and Stop buttons. No internet connection or hosted server is required for normal Windows use.

## Run from source

Install Python 3.10 or newer from python.org (include Tcl/Tk and the Python launcher), then double-click `start-windows.bat` in the repository root. Choose your own administrator and separate data-clearing passwords on first use. Closing the controller stops the server; it does not delete records.

Desktop data is stored at `%LOCALAPPDATA%\NexvantEngineering\data\sales.db`, outside the installation directory. An existing `SALES_DB` environment variable overrides that path. When running from source and an old `data/sales.db` exists, the controller offers to copy it into the desktop data directory using SQLite's backup API. Keep the original backup until you have checked the imported records.

## Build a portable Windows executable

Run on Windows 10/11 with Python 3.10+ and Tkinter installed:

```powershell
powershell -ExecutionPolicy RemoteSigned -File windows\build.ps1
```

The build creates a local virtual environment, installs pinned PyInstaller, smoke-tests the server, bundles the Python runtime and static assets, and smoke-tests `windows\dist\NexvantEngineering.exe`. Internet access is needed only to download build tooling. The recipient of the resulting executable does not need Python installed. The executable is unsigned; signing and installer creation are separate distribution steps. Build on Windows: PyInstaller does not cross-compile Windows executables from Linux.

Alternatively, push the repository to GitHub and manually run **Build Windows desktop application** in the Actions tab. The workflow runs the business tests and build checks on Windows, then uploads the executable as a downloadable artifact. It does not publish a release automatically.

The headless smoke test uses a disposable database, starts a real loopback HTTP server, checks the first-run API and all static assets, then stops it. It never reads or alters business records:

```powershell
py -3 windows\desktop.py --smoke-test
```

## Android on the same private network

Stop the desktop server, check **Allow phones on my trusted private network**, and start it again. This binds port 8000 on the PC's network interfaces. Allow port 8000 through Windows Firewall for private networks only. On the phone, connect to the same trusted Wi-Fi and configure the Android client with `http://<PC-LAN-IPv4>:8000` (find the PC's IPv4 address with `ipconfig`). Keep the PC awake and the controller running. Both clients use the same database; the phone has no offline database or automatic sync.

Local-network HTTP is intended only for a trusted private network. For remote access, serve the application behind an HTTPS reverse proxy and use its HTTPS URL in Android. Do not forward the raw HTTP port through your router.

## Back up or move the database

Stop the controller first, then copy the entire `%LOCALAPPDATA%\NexvantEngineering\data` folder to a private backup location. To restore, stop the controller and replace that folder with the backup. Keep backups private because they contain financial records and password hashes. Updating the executable does not remove this data directory.

## Verification limits

The source controller and bundled-asset smoke test can be exercised on Linux without opening the Tkinter window. A Windows build and interactive Windows desktop check must run on Windows; source validation alone does not establish that a Windows binary has been built or tested.
