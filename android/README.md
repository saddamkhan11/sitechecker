# Android app (Capacitor WebView wrapper)

The app is the live website inside an Android WebView. Most of the work is permissions, not code.

## One-time setup (needs Node 18+ and Android Studio)

```bash
cd android
npm install
npx cap add android
```

1. Put your real HTTPS address in `capacitor.config.json` → `server.url`.
2. Add permissions to `android/app/src/main/AndroidManifest.xml` inside `<manifest>`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-feature android:name="android.hardware.camera" android:required="false" />
```

3. Photo inputs (`<input type="file" capture="environment">`) open the camera in Capacitor's WebView
   once the CAMERA permission is granted. Test this on a real phone: it is off in a plain WebView.
   The 🎤 voice button uses `getUserMedia` + `MediaRecorder`; the WebView must grant the microphone
   (Capacitor asks for RECORD_AUDIO at runtime). Spoken replies use the phone's text-to-speech:
   install **Urdu** in Settings → Google Speech Services → Install voice data for the best result.
4. Back button: `@capacitor/app` is installed. The site already goes back one page; to be sure,
   add this to `MainActivity.java` or rely on Capacitor's default (`history.back()` when possible).
5. Build: `npx cap sync android && npx cap open android`, then **Build → Generate Signed Bundle / APK**.

## Before Google Play

- Test on two or three low-cost Android phones (camera, tilt sensor, offline photo queue).
- Developer account, privacy policy page (photos, phone number, location are stored), screenshots.
- Leave iPhone for later: Apple often rejects wrapped websites.

The site is also installable without the app: open it in Chrome → menu → **Install app**
(web manifest + service worker are already in place).
