package com.nexvant.engineering;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Origin-only server selection; HTTP requires explicit private LAN permission. */
public final class ServerAddress {
    private ServerAddress() {}

    public static String normalize(String value, boolean allowLan) {
        try {
            URI uri = new URI(value.trim());
            String scheme = uri.getScheme();
            String host = uri.getHost();
            if (scheme == null || host == null || uri.getUserInfo() != null ||
                    uri.getQuery() != null || uri.getFragment() != null ||
                    !(uri.getPath() == null || uri.getPath().isEmpty() || uri.getPath().equals("/"))) {
                throw new IllegalArgumentException("Enter the server origin only, for example https://sales.example.com");
            }
            scheme = scheme.toLowerCase(Locale.ROOT);
            host = host.toLowerCase(Locale.ROOT);
            if (!scheme.equals("https") && !(scheme.equals("http") && allowLan && privateIpv4(host))) {
                throw new IllegalArgumentException("Use HTTPS, or enable trusted LAN mode for a private IPv4 address.");
            }
            int port = uri.getPort();
            if (port == 0 || port > 65535 || port < -1) throw new IllegalArgumentException("Invalid server port.");
            if ((scheme.equals("https") && port == 443) || (scheme.equals("http") && port == 80)) port = -1;
            return new URI(scheme, null, host, port, "/", null, null).toASCIIString();
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("Enter a valid HTTPS server address.");
        }
    }

    public static boolean sameOrigin(String first, String second) {
        try {
            URI a = new URI(first), b = new URI(second);
            return a.getScheme() != null && a.getHost() != null && a.getScheme().equalsIgnoreCase(b.getScheme()) &&
                    a.getHost().equalsIgnoreCase(b.getHost()) && effectivePort(a) == effectivePort(b) && b.getUserInfo() == null;
        } catch (Exception e) { return false; }
    }

    private static int effectivePort(URI uri) {
        return uri.getPort() != -1 ? uri.getPort() : ("https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80);
    }

    private static boolean privateIpv4(String host) {
        String[] parts = host.split("\\.", -1);
        if (parts.length != 4) return false;
        int[] n = new int[4];
        for (int i = 0; i < 4; i++) {
            if (!parts[i].matches("0|[1-9][0-9]{0,2}")) return false;
            n[i] = Integer.parseInt(parts[i]);
            if (n[i] > 255) return false;
        }
        return n[0] == 10 || (n[0] == 172 && n[1] >= 16 && n[1] <= 31) ||
                (n[0] == 192 && n[1] == 168);
    }
}
