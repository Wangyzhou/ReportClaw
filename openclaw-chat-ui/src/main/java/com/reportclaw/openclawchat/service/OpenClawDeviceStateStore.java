package com.reportclaw.openclawchat.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class OpenClawDeviceStateStore {

    private static final byte[] ED25519_SPKI_PREFIX = hexToBytes("302a300506032b6570032100");
    private static final Path DEVICE_IDENTITY_FILE = Path.of("device-identity.json");
    private static final Path DEVICE_TOKEN_FILE = Path.of("device-token.json");

    private final ObjectMapper objectMapper;

    public OpenClawDeviceStateStore(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public DeviceIdentity loadOrCreateIdentity(Path stateDir) {
        try {
            Files.createDirectories(stateDir);
            Path identityFile = stateDir.resolve(DEVICE_IDENTITY_FILE);
            if (Files.exists(identityFile)) {
                JsonNode json = objectMapper.readTree(Files.readString(identityFile));
                String publicKeyPem = json.path("publicKeyPem").asText("");
                String privateKeyPem = json.path("privateKeyPem").asText("");
                if (!publicKeyPem.isBlank() && !privateKeyPem.isBlank()) {
                    return new DeviceIdentity(
                            fingerprintPublicKey(publicKeyPem),
                            publicKeyPem,
                            privateKeyPem
                    );
                }
            }

            KeyPairGenerator generator = KeyPairGenerator.getInstance("Ed25519");
            KeyPair pair = generator.generateKeyPair();
            String publicKeyPem = toPem("PUBLIC KEY", pair.getPublic().getEncoded());
            String privateKeyPem = toPem("PRIVATE KEY", pair.getPrivate().getEncoded());
            DeviceIdentity identity = new DeviceIdentity(
                    fingerprintPublicKey(publicKeyPem),
                    publicKeyPem,
                    privateKeyPem
            );

            ObjectNode json = objectMapper.createObjectNode();
            json.put("version", 1);
            json.put("deviceId", identity.deviceId());
            json.put("publicKeyPem", identity.publicKeyPem());
            json.put("privateKeyPem", identity.privateKeyPem());
            json.put("createdAtMs", System.currentTimeMillis());
            Files.writeString(identityFile, objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(json) + System.lineSeparator(), StandardCharsets.UTF_8);
            return identity;
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to load or create OpenClaw device identity", exception);
        }
    }

    public StoredDeviceToken loadStoredToken(Path stateDir) {
        try {
            Path tokenFile = stateDir.resolve(DEVICE_TOKEN_FILE);
            if (!Files.exists(tokenFile)) {
                return null;
            }
            JsonNode json = objectMapper.readTree(Files.readString(tokenFile));
            String deviceToken = json.path("deviceToken").asText("");
            if (deviceToken.isBlank()) {
                return null;
            }
            List<String> scopes = objectMapper.convertValue(
                    json.path("scopes"),
                    objectMapper.getTypeFactory().constructCollectionType(List.class, String.class)
            );
            return new StoredDeviceToken(
                    deviceToken,
                    json.path("role").asText("operator"),
                    scopes,
                    json.hasNonNull("issuedAtMs") ? json.get("issuedAtMs").asLong() : null
            );
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to load OpenClaw device token", exception);
        }
    }

    public void saveDeviceToken(Path stateDir, JsonNode authPayload) {
        try {
            if (authPayload == null || authPayload.path("deviceToken").asText("").isBlank()) {
                return;
            }
            Files.createDirectories(stateDir);
            ObjectNode json = objectMapper.createObjectNode();
            json.put("savedAt", Instant.now().toString());
            json.set("deviceToken", authPayload.get("deviceToken"));
            json.put("role", authPayload.path("role").asText("operator"));
            json.set("scopes", authPayload.path("scopes"));
            if (authPayload.hasNonNull("issuedAtMs")) {
                json.set("issuedAtMs", authPayload.get("issuedAtMs"));
            }
            Files.writeString(
                    stateDir.resolve(DEVICE_TOKEN_FILE),
                    objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(json) + System.lineSeparator(),
                    StandardCharsets.UTF_8
            );
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to save OpenClaw device token", exception);
        }
    }

    public String publicKeyBase64Url(DeviceIdentity identity) {
        byte[] raw = deriveRawPublicKey(identity.publicKeyPem());
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw);
    }

    public String fingerprintPublicKey(String publicKeyPem) {
        try {
            byte[] raw = deriveRawPublicKey(publicKeyPem);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return bytesToHex(digest.digest(raw));
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to fingerprint OpenClaw public key", exception);
        }
    }

    public String signPayload(DeviceIdentity identity, String payload) {
        try {
            PrivateKey privateKey = privateKeyFromPem(identity.privateKeyPem());
            java.security.Signature signature = java.security.Signature.getInstance("Ed25519");
            signature.initSign(privateKey);
            signature.update(payload.getBytes(StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(signature.sign());
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to sign OpenClaw device payload", exception);
        }
    }

    private byte[] deriveRawPublicKey(String publicKeyPem) {
        try {
            byte[] der = publicKeyFromPem(publicKeyPem).getEncoded();
            if (der.length == ED25519_SPKI_PREFIX.length + 32) {
                boolean prefixMatches = true;
                for (int index = 0; index < ED25519_SPKI_PREFIX.length; index += 1) {
                    if (der[index] != ED25519_SPKI_PREFIX[index]) {
                        prefixMatches = false;
                        break;
                    }
                }
                if (prefixMatches) {
                    byte[] raw = new byte[32];
                    System.arraycopy(der, ED25519_SPKI_PREFIX.length, raw, 0, 32);
                    return raw;
                }
            }
            return der;
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to derive raw OpenClaw public key", exception);
        }
    }

    private PublicKey publicKeyFromPem(String pem) throws Exception {
        byte[] decoded = Base64.getDecoder().decode(stripPemEnvelope(pem));
        X509EncodedKeySpec spec = new X509EncodedKeySpec(decoded);
        return KeyFactory.getInstance("Ed25519").generatePublic(spec);
    }

    private PrivateKey privateKeyFromPem(String pem) throws Exception {
        byte[] decoded = Base64.getDecoder().decode(stripPemEnvelope(pem));
        PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(decoded);
        return KeyFactory.getInstance("Ed25519").generatePrivate(spec);
    }

    private static String stripPemEnvelope(String pem) {
        return pem
                .replace("-----BEGIN PUBLIC KEY-----", "")
                .replace("-----END PUBLIC KEY-----", "")
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s+", "");
    }

    private static String toPem(String type, byte[] encoded) {
        String base64 = Base64.getMimeEncoder(64, System.lineSeparator().getBytes(StandardCharsets.UTF_8)).encodeToString(encoded);
        return "-----BEGIN " + type + "-----" + System.lineSeparator()
                + base64 + System.lineSeparator()
                + "-----END " + type + "-----" + System.lineSeparator();
    }

    private static byte[] hexToBytes(String value) {
        byte[] bytes = new byte[value.length() / 2];
        for (int index = 0; index < value.length(); index += 2) {
            bytes[index / 2] = (byte) Integer.parseInt(value.substring(index, index + 2), 16);
        }
        return bytes;
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder builder = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            builder.append(String.format("%02x", value));
        }
        return builder.toString();
    }

    public record DeviceIdentity(
            String deviceId,
            String publicKeyPem,
            String privateKeyPem
    ) {
    }

    public record StoredDeviceToken(
            String deviceToken,
            String role,
            List<String> scopes,
            Long issuedAtMs
    ) {
    }
}
