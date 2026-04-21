package com.reportclaw.openclawchat.config;

import jakarta.validation.constraints.NotBlank;
import java.nio.file.Path;
import java.time.Duration;
import org.springframework.validation.annotation.Validated;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Validated
@ConfigurationProperties(prefix = "openclaw")
public class OpenClawProperties {

    @NotBlank
    private String gatewayUrl = "ws://192.168.4.188:18789";

    private String gatewayToken = "";

    private String explicitDeviceToken = "";

    @NotBlank
    private String defaultSessionKey = "agent:main:main";

    @NotBlank
    private String deviceStateDir = "../examples/openclaw-gateway-ws/.runtime";

    @NotBlank
    private String clientId = "cli";

    @NotBlank
    private String clientVersion = "0.1.0";

    @NotBlank
    private String platform = detectPlatform();

    @NotBlank
    private String deviceFamily = "desktop";

    @NotBlank
    private String locale = "zh-CN";

    @NotBlank
    private String userAgent = "openclaw-spring-ui/0.1.0";

    private boolean preferStoredDeviceToken = true;

    private Duration connectTimeout = Duration.ofSeconds(20);

    private Duration readTimeout = Duration.ofMinutes(5);

    public String getGatewayUrl() {
        return gatewayUrl;
    }

    public void setGatewayUrl(String gatewayUrl) {
        this.gatewayUrl = gatewayUrl;
    }

    public String getGatewayToken() {
        return gatewayToken;
    }

    public void setGatewayToken(String gatewayToken) {
        this.gatewayToken = gatewayToken;
    }

    public String getExplicitDeviceToken() {
        return explicitDeviceToken;
    }

    public void setExplicitDeviceToken(String explicitDeviceToken) {
        this.explicitDeviceToken = explicitDeviceToken;
    }

    public String getDefaultSessionKey() {
        return defaultSessionKey;
    }

    public void setDefaultSessionKey(String defaultSessionKey) {
        this.defaultSessionKey = defaultSessionKey;
    }

    public String getDeviceStateDir() {
        return deviceStateDir;
    }

    public void setDeviceStateDir(String deviceStateDir) {
        this.deviceStateDir = deviceStateDir;
    }

    public Path resolveDeviceStateDir() {
        return Path.of(deviceStateDir).normalize();
    }

    public String getClientId() {
        return clientId;
    }

    public void setClientId(String clientId) {
        this.clientId = clientId;
    }

    public String getClientVersion() {
        return clientVersion;
    }

    public void setClientVersion(String clientVersion) {
        this.clientVersion = clientVersion;
    }

    public String getPlatform() {
        return platform;
    }

    public void setPlatform(String platform) {
        this.platform = platform;
    }

    public String getDeviceFamily() {
        return deviceFamily;
    }

    public void setDeviceFamily(String deviceFamily) {
        this.deviceFamily = deviceFamily;
    }

    public String getLocale() {
        return locale;
    }

    public void setLocale(String locale) {
        this.locale = locale;
    }

    public String getUserAgent() {
        return userAgent;
    }

    public void setUserAgent(String userAgent) {
        this.userAgent = userAgent;
    }

    public boolean isPreferStoredDeviceToken() {
        return preferStoredDeviceToken;
    }

    public void setPreferStoredDeviceToken(boolean preferStoredDeviceToken) {
        this.preferStoredDeviceToken = preferStoredDeviceToken;
    }

    public Duration getConnectTimeout() {
        return connectTimeout;
    }

    public void setConnectTimeout(Duration connectTimeout) {
        this.connectTimeout = connectTimeout;
    }

    public Duration getReadTimeout() {
        return readTimeout;
    }

    public void setReadTimeout(Duration readTimeout) {
        this.readTimeout = readTimeout;
    }

    private static String detectPlatform() {
        String os = System.getProperty("os.name", "").toLowerCase();
        if (os.contains("win")) {
            return "windows";
        }
        if (os.contains("mac")) {
            return "macos";
        }
        return "linux";
    }
}
