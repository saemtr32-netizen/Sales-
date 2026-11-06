package com.nexvant.engineering;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/** Connected Android client. Business data and authentication remain on the server. */
public class MainActivity extends Activity {
    private static final int SAVE_JSON = 101, SELECT_FILE = 102;
    private LinearLayout root;
    private WebView browser;
    private String serverOrigin = "";
    private String pendingExport;
    private ValueCallback<Uri[]> fileCallback;
    private SharedPreferences preferences;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        preferences = getSharedPreferences("connection", MODE_PRIVATE);
        String saved = preferences.getString("origin", "");
        if (saved.isEmpty()) showConnection();
        else {
            try { openServer(ServerAddress.normalize(saved, preferences.getBoolean("lan", false))); }
            catch (IllegalArgumentException e) { showConnection(); }
        }
    }

    private int dp(int n) { return (int) (n * getResources().getDisplayMetrics().density + 0.5f); }

    private LinearLayout layout() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        view.setBackgroundColor(Color.rgb(248, 249, 245));
        view.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets i = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                v.setPadding(i.left, i.top, i.right, i.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        setContentView(view);
        root = view;
        return view;
    }

    private TextView text(String value, int size) {
        TextView label = new TextView(this);
        label.setText(value); label.setTextSize(size);
        label.setTextColor(Color.rgb(18, 61, 53));
        label.setPadding(dp(4), dp(8), dp(4), dp(8));
        return label;
    }

    private void showConnection() {
        if (browser != null) { browser.stopLoading(); browser.destroy(); browser = null; }
        layout();
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(24), dp(32), dp(24), dp(24));
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(form);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, -1));
        form.addView(text("NEXVANT ENGINEERING", 25));
        form.addView(text("Sales & finance, wherever you work", 18));
        form.addView(text("Connect to your company's Nexvant server. Your phone and Windows computer share the same records while connected. An Internet or local network connection is required.", 15));
        EditText address = new EditText(this);
        address.setSingleLine(true);
        address.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        address.setHint("https://sales.example.com");
        address.setText(preferences.getString("origin", ""));
        form.addView(address);
        CheckBox lan = new CheckBox(this);
        lan.setText("Allow HTTP on a trusted private Wi-Fi network");
        lan.setChecked(preferences.getBoolean("lan", false));
        form.addView(lan);
        form.addView(text("For local Windows use: http://192.168.x.x:8000. HTTP does not encrypt passwords or business data; use it only on a private network you trust. Use HTTPS for remote access.", 13));
        Button connect = new Button(this); connect.setText("Connect to server");
        connect.setOnClickListener(v -> {
            try {
                String origin = ServerAddress.normalize(address.getText().toString(), lan.isChecked());
                preferences.edit().putString("origin", origin).putBoolean("lan", lan.isChecked()).apply();
                CookieManager.getInstance().removeAllCookies(removed -> openServer(origin));
            } catch (IllegalArgumentException e) { address.setError(e.getMessage()); }
        });
        form.addView(connect);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void openServer(String origin) {
        serverOrigin = origin;
        layout();
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        TextView title = text("Nexvant", 18);
        title.setPadding(dp(12), dp(12), dp(4), dp(12));
        toolbar.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button reload = new Button(this); reload.setText("Reload");
        reload.setOnClickListener(v -> { if (browser != null) browser.loadUrl(serverOrigin); });
        toolbar.addView(reload);
        Button settings = new Button(this); settings.setText("Server");
        settings.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle("Change server?")
                .setMessage("You will leave the current page and sign out on this device. Unsaved form changes will be lost.")
                .setNegativeButton("Stay", null).setPositiveButton("Change", (d, w) -> {
                    CookieManager.getInstance().removeAllCookies(null);
                    showConnection();
                }).show());
        toolbar.addView(settings);
        root.addView(toolbar);
        browser = new WebView(this);
        WebSettings config = browser.getSettings();
        config.setJavaScriptEnabled(true);
        config.setDomStorageEnabled(false);
        config.setAllowFileAccess(false);
        // Android's document picker grants access only to the image selected by the user.
        // Navigation and ordinary resources remain restricted to the selected origin.
        config.setAllowContentAccess(true);
        config.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        config.setSafeBrowsingEnabled(true);
        config.setSupportMultipleWindows(false);
        config.setJavaScriptCanOpenWindowsAutomatically(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(browser, false);
        browser.addJavascriptInterface(new AppBridge(), "NexvantAndroid");
        browser.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (ServerAddress.sameOrigin(serverOrigin, request.getUrl().toString())) return false;
                message("This app opens only your selected Nexvant server."); return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String scheme = request.getUrl().getScheme();
                if ("data".equals(scheme) || "blob".equals(scheme) || ServerAddress.sameOrigin(serverOrigin, request.getUrl().toString())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                message("The server certificate could not be verified. Fix its HTTPS certificate before connecting.");
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) message("Cannot reach the server. Check its address, Windows server, and network, then tap Reload.");
            }
        });
        browser.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent pick = new Intent(Intent.ACTION_GET_CONTENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE);
                try { startActivityForResult(pick, SELECT_FILE); }
                catch (android.content.ActivityNotFoundException e) { fileCallback.onReceiveValue(null); fileCallback = null; message("No file picker is available."); }
                return true;
            }
        });
        root.addView(browser, new LinearLayout.LayoutParams(-1, 0, 1));
        browser.loadUrl(origin);
    }

    private boolean trustedPage() { return browser != null && ServerAddress.sameOrigin(serverOrigin, browser.getUrl()); }
    private void message(String value) { runOnUiThread(() -> Toast.makeText(this, value, Toast.LENGTH_LONG).show()); }

    public final class AppBridge {
        @JavascriptInterface public void printDocument() {
            runOnUiThread(() -> {
                if (!trustedPage()) return;
                PrintManager manager = (PrintManager) getSystemService(PRINT_SERVICE);
                manager.print("Nexvant Engineering", browser.createPrintDocumentAdapter("Nexvant Engineering"),
                        new PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build());
            });
        }

        @JavascriptInterface public void saveBackup(String json, String filename) {
            if (json == null || json.length() > 10_000_000) { message("Export is too large for mobile; use the Windows browser."); return; }
            try { new JSONObject(json); } catch (Exception e) { message("Invalid JSON export."); return; }
            runOnUiThread(() -> {
                if (!trustedPage()) return;
                if (pendingExport != null) { message("Finish the current export first."); return; }
                pendingExport = json;
                String name = filename == null ? "nexvant-records.json" : filename.replaceAll("[^A-Za-z0-9_.-]", "_");
                if (!name.endsWith(".json")) name += ".json";
                Intent save = new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json")
                        .addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE, name);
                try { startActivityForResult(save, SAVE_JSON); }
                catch (android.content.ActivityNotFoundException e) { pendingExport = null; message("No document picker is available."); }
            });
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == SELECT_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(result == RESULT_OK && data != null && data.getData() != null ? new Uri[]{data.getData()} : null);
            fileCallback = null;
        }
        if (request == SAVE_JSON) {
            if (result == RESULT_OK && data != null && data.getData() != null && pendingExport != null) {
                try (OutputStream stream = getContentResolver().openOutputStream(data.getData(), "wt")) {
                    if (stream == null) throw new java.io.IOException("No destination");
                    stream.write(pendingExport.getBytes(StandardCharsets.UTF_8));
                    message("Records exported. Keep this file private.");
                } catch (Exception e) { message("Could not save the export. Please try again."); }
            }
            pendingExport = null;
        }
    }

    @Override public void onBackPressed() {
        if (browser != null && browser.canGoBack()) browser.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (browser != null) browser.destroy();
        pendingExport = null;
        super.onDestroy();
    }
}
