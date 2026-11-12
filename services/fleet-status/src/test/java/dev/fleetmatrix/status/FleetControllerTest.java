package dev.fleetmatrix.status;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class FleetControllerTest {
    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) throws IOException {
        Path tmp = Files.createTempDirectory("fleet");
        try (var in = FleetControllerTest.class.getResourceAsStream("/state.json")) {
            Files.write(tmp.resolve("state.json"), in.readAllBytes());
        }
        r.add("fleet.state-file", () -> tmp.resolve("state.json").toString());
    }

    @Autowired
    MockMvc mvc;

    @Test
    void listsRunnersFromTheStateFile() throws Exception {
        mvc.perform(get("/api/runners"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(3))
                .andExpect(jsonPath("$[0].runner_id").value("m1-01"));
    }

    @Test
    void summaryCountsByStateAndFlagsExpiredLeases() throws Exception {
        mvc.perform(get("/api/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(3))
                .andExpect(jsonPath("$.byState.leased").value(2))
                .andExpect(jsonPath("$.byState.ready").value(1))
                .andExpect(jsonPath("$.leasesPastExpiry").value(1));
    }

    @Test
    void healthIsUpWithRunnerCount() throws Exception {
        mvc.perform(get("/actuator/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"))
                .andExpect(jsonPath("$.components.fleetState.details.runners").value(3));
    }
}
