package com.nexvant.engineering;

public final class ServerAddressTest {
    private static int count;
    private static void equal(String wanted, String value) { count++; if (!wanted.equals(value)) throw new AssertionError(value); }
    private static void rejects(String value, boolean lan) {
        count++;
        try { ServerAddress.normalize(value, lan); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Accepted unsafe address: " + value);
    }
    public static void main(String[] args) {
        equal("https://example.com/", ServerAddress.normalize("https://EXAMPLE.com:443", false));
        equal("https://example.com:8443/", ServerAddress.normalize("https://example.com:8443/", false));
        equal("http://192.168.1.2:8000/", ServerAddress.normalize("http://192.168.1.2:8000", true));
        equal("http://172.16.0.1/", ServerAddress.normalize("http://172.16.0.1", true));
        equal("http://10.1.2.3/", ServerAddress.normalize("http://10.1.2.3", true));
        rejects("http://192.168.1.2", false);
        rejects("http://sales.example.com", true);
        rejects("http://8.8.8.8", true);
        rejects("http://172.32.0.1", true);
        rejects("http://192.168.256.1", true);
        rejects("http://192.168.01.1", true);
        rejects("https://user:password@example.com", false);
        rejects("https://example.com/foo", false);
        rejects("https://example.com/?token=secret", false);
        rejects("https://example.com/#fragment", false);
        rejects("file:///etc/passwd", true);
        rejects("javascript:alert(1)", true);
        rejects("https://example.com:0", false);
        rejects("https://example.com:65536", false);
        count++;
        if (!ServerAddress.sameOrigin("https://example.com/", "https://example.com:443/api/status")) throw new AssertionError("Default HTTPS port");
        for (String value : new String[]{"https://other.example.com/", "http://example.com/", "https://example.com:8443/", "https://user@example.com/", "data:text/html,hello"}) {
            count++;
            if (ServerAddress.sameOrigin("https://example.com/", value)) throw new AssertionError("Cross-origin allowed: " + value);
        }
        System.out.println(count + " server-address checks passed");
    }
}
