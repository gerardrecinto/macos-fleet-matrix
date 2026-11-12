package dev.fleetmatrix.status;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** One runner as written by `mfm` (see src/mfm/model.py). Unknown fields are ignored. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Runner(
        @JsonProperty("runner_id") String runnerId,
        String image,
        String arch,
        String state,
        @JsonProperty("job_id") String jobId,
        @JsonProperty("lease_expires_at") Double leaseExpiresAt) {
}
