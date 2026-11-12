package dev.fleetmatrix.status;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** Reads the fleet state file on every call, so the page always shows what mfm last saved. */
@Component
public class StateReader {
    private final Path file;
    private final ObjectMapper mapper;

    public StateReader(@Value("${fleet.state-file}") String file, ObjectMapper mapper) {
        this.file = Path.of(file);
        this.mapper = mapper;
    }

    public Path file() {
        return file;
    }

    public List<Runner> read() throws IOException {
        if (!Files.isReadable(file)) {
            throw new IOException("state file not readable: " + file);
        }
        try {
            return mapper.readValue(file.toFile(), new TypeReference<List<Runner>>() { });
        } catch (JsonProcessingException e) {
            throw new IOException("state file is not a list of runners: " + file + " (" + e.getOriginalMessage() + ")", e);
        }
    }
}
