package com.reportclaw.openclawchat;

import com.reportclaw.openclawchat.config.OpenClawProperties;
import com.reportclaw.openclawchat.config.RagFlowProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({OpenClawProperties.class, RagFlowProperties.class})
public class OpenClawChatApplication {

    public static void main(String[] args) {
        SpringApplication.run(OpenClawChatApplication.class, args);
    }
}
