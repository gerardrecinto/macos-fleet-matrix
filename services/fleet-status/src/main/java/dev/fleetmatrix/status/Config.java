package dev.fleetmatrix.status;

import java.io.IOException;
import java.time.Clock;
import org.springframework.boot.health.contributor.Health;
import org.springframework.boot.health.contributor.HealthIndicator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class Config {
    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }

    /** Down when the state file is missing or malformed, so a bad mount fails the readiness probe. */
    @Bean
    HealthIndicator fleetState(StateReader reader) {
        return () -> {
            try {
                return Health.up().withDetail("runners", reader.read().size()).build();
            } catch (IOException e) {
                return Health.down().withDetail("error", e.getMessage()).build();
            }
        };
    }
}
