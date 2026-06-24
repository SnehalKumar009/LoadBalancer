package com.example.lb;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.time.Instant;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InfoController {

    @Value("${app.id:app-unknown}")
    private String appId;

    @GetMapping("/healthz")
    public Map<String, Object> health() {
        return Map.of(
                "status", "UP",
                "appId", appId,
                "timestamp", Instant.now().toString()
        );
    }

    @GetMapping("/")
    public Map<String, Object> index() throws UnknownHostException {
        return Map.of(
                "message", "Spring Boot backend behind ATS",
                "appId", appId,
                "hostname", InetAddress.getLocalHost().getHostName(),
                "timestamp", Instant.now().toString()
        );
    }
}

