package dev.fleetmatrix.status;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "fleet.state-file=/nonexistent/state.json")
@AutoConfigureMockMvc
class MissingStateTest {
    @Autowired
    MockMvc mvc;

    @Test
    void apiAnswers503WithTheReason() throws Exception {
        mvc.perform(get("/api/summary"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.error").value("state file not readable: /nonexistent/state.json"));
    }

    @Test
    void healthIsDownSoReadinessFails() throws Exception {
        mvc.perform(get("/actuator/health"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.status").value("DOWN"));
    }
}
