import XCTest
@testable import MFMTelemetry

final class HostTelemetryProbeTests: XCTestCase {

    func testSampleReportsNonZeroMemoryCounters() throws {
        let state = try HostTelemetryProbe.sample()

        XCTAssertGreaterThan(state.memory.pageSizeBytes, 0)
        XCTAssertGreaterThan(
            state.memory.freeBytes
                + state.memory.activeBytes
                + state.memory.inactiveBytes
                + state.memory.wiredBytes,
            0,
            "host_statistics64 returned an all-zero snapshot, which never happens on a live host"
        )
    }

    func testSampleSwapAccountingIsInternallyConsistent() throws {
        let state = try HostTelemetryProbe.sample()

        XCTAssertGreaterThanOrEqual(state.memory.swapTotalBytes, state.memory.swapUsedBytes)
        XCTAssertGreaterThanOrEqual(state.memory.swapTotalBytes, state.memory.swapFreeBytes)
    }

    func testSampleThermalStateIsARecognizedCase() throws {
        let state = try HostTelemetryProbe.sample()

        // .unknown only fires on an @unknown default from a future OS enum
        // case; on a supported host this must resolve to a known state.
        XCTAssertNotEqual(state.thermalState, .unknown)
    }

    func testHostHealthStateRoundTripsThroughJSON() throws {
        let state = try HostTelemetryProbe.sample()
        let data = try state.jsonData()
        let decoded = try JSONDecoder.telemetryDecoder.decode(HostHealthState.self, from: data)

        XCTAssertEqual(decoded.thermalState, state.thermalState)
        XCTAssertEqual(decoded.memory, state.memory)
        // ISO 8601 with fractional seconds round-trips to millisecond
        // precision, not the full Double precision of the in-memory Date.
        XCTAssertEqual(
            decoded.timestamp.timeIntervalSince1970,
            state.timestamp.timeIntervalSince1970,
            accuracy: 0.001
        )
    }

    /// Not a substitute for Instruments, but 500 back-to-back Mach/BSD calls
    /// is enough for `leaks --atExit -- swift test` to catch a port or
    /// buffer leak in host_statistics64 or sysctlbyname handling in CI.
    func testRepeatedSamplingStaysStable() throws {
        for _ in 0..<500 {
            _ = try HostTelemetryProbe.sample()
        }
    }
}
