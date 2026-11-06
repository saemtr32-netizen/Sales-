# Nexvant Engineering for Android

A native Android 8.0+ client for the Nexvant sales and finance server. It uses the
same mobile-friendly interface and administrator login as Windows, with native
printing / Save as PDF, logo file selection, and JSON export through Android's
document picker. No storage permission is needed. The launcher icon is a neutral
N monogram; upload your company logo in the application's Settings for documents.

This is a **connected app**. It does not run the Python server on the phone or
store an offline business database. Keep the Windows/server computer running.
The phone and computer use one database; there is no separate sync step.

## Install and connect

1. Copy `app/build/outputs/apk/debug/nexvant-debug.apk` to the phone, open it,
   and permit installation from that source when Android asks. This development
   APK is not a Google Play release.
2. On Windows, start the server in LAN mode as described in the main README.
3. Connect both devices to trusted private Wi-Fi. Enter the computer's private
   IPv4 address, e.g. `http://192.168.1.20:8000`, and enable **Allow HTTP on a
   trusted private Wi-Fi network**. Do not enter `127.0.0.1` or `localhost`:
   those refer to the phone itself. Allow the server's port only on Windows'
   private firewall profile.
4. For access away from that network, configure the server behind an HTTPS
   reverse proxy and enter its HTTPS origin, e.g. `https://sales.example.com`.
   This repository does not provision or publicly host that endpoint.
5. Create the administrator on first use, or log in to the existing account.
   Use Print buttons inside the app to print invoices, quotations, statements,
   and reports or save them as PDFs.

HTTPS is the default. Optional HTTP accepts RFC1918 IPv4 addresses only, and
transmits passwords/data without encryption; use only on a private network you
trust. The client never accepts invalid TLS certificates, blocks other origins
and mixed content, disables file access and third-party cookies, and excludes
app data from Android backups. The **Server** button lets you change connection
settings and signs out locally. The address is stored, never the password.

## Build

Open this `android/` directory in Android Studio. Install Android SDK platform 35
and build-tools 35.0.0. The Gradle project uses Android Gradle Plugin 8.7.3
(Gradle 8.9 and JDK 17+). Android Studio can build the debug APK or create a signed
release. No third-party runtime dependencies are used.

A Gradle-independent Linux/macOS build is also provided. It requires the same
Android SDK, a JDK with `java`, `javac`, and `keytool`, Python 3, and bash:

```sh
cd android
export ANDROID_HOME=/path/to/android-sdk
bash test-addresses.sh
bash build-debug.sh
```

`ANDROID_BUILD_TOOLS` may select an equivalent build-tools directory if your SDK
uses a different layout. On JRE-only systems an independently verified Eclipse
Java compiler JAR can be supplied via `ECJ_JAR`; otherwise `javac` is used. Scripts
do not download unverified dependencies or disable TLS/package verification.

The debug signing key is generated locally in ignored `.debug/`; preserve it if
you need future APK updates to install over this development build. For company
distribution, create and securely retain a release signing key in Android Studio
and generate a signed release. Never commit private signing keys. Changing the
signing key requires uninstalling the previous APK first.

## Validation

`test-addresses.sh` checks address normalization, HTTPS defaults, LAN opt-in,
private address validation, and same-origin restrictions. `build-debug.sh`
compiles the real Android source, packages/dexes it, and verifies APK signatures.
An Android device or emulator is still needed to validate installation,
WebView UI, native printing, file selection, and export end to end.
