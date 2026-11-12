package dev.fleetmatrix.status;

import java.io.IOException;
import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class FleetController {
    private static final List<String> STATES = List.of("ready", "leased", "draining", "quarantined", "destroyed");
    private final StateReader reader;
    private final Clock clock;

    public FleetController(StateReader reader, Clock clock) {
        this.reader = reader;
        this.clock = clock;
    }

    @GetMapping("/runners")
    public List<Runner> runners() throws IOException {
        return reader.read();
    }

    /** Counts per state, plus leases past their expiry that the reaper has not taken back yet. */
    @GetMapping("/summary")
    public Map<String, Object> summary() throws IOException {
        List<Runner> runners = reader.read();
        double now = clock.millis() / 1000.0;
        Map<String, Long> counts = new LinkedHashMap<>();
        for (String s : STATES) {
            counts.put(s, runners.stream().filter(r -> s.equals(r.state())).count());
        }
        long overdue = runners.stream()
                .filter(r -> "leased".equals(r.state()) && r.leaseExpiresAt() != null && r.leaseExpiresAt() < now)
                .count();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("total", runners.size());
        out.put("byState", counts);
        out.put("leasesPastExpiry", overdue);
        return out;
    }

    @ExceptionHandler(IOException.class)
    public ResponseEntity<Map<String, String>> unreadable(IOException e) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of("error", e.getMessage()));
    }
}
