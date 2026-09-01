import Darwin
import Foundation

/// Errors raised when a Mach or BSD telemetry call fails.
public enum HostTelemetryError: Error, CustomStringConvertible {
    case machCallFailed(String, kern_return_t)
    case sysctlFailed(String, Int32)

    public var description: String {
        switch self {
        case let .machCallFailed(name, code):
            return "\(name) failed with kern_return_t \(code)"
        case let .sysctlFailed(name, code):
            return "sysctlbyname(\(name)) failed with errno \(code)"
        }
    }
}

/// Mirrors `ProcessInfo.ThermalState`. We read thermal state through
/// `ProcessInfo` rather than a raw `sysctlbyname` call: the `machdep.xcpm.*`
/// tree some tooling still reaches for is x86-only (XCPM is Intel's Core
/// Performance Management subsystem) and simply does not exist on Apple
/// Silicon — the call fails with ENOENT. `ProcessInfo.thermalState` is the
/// stable, public signal powerd exposes on both architectures.
public enum ThermalState: String, Codable, Equatable {
    case nominal
    case fair
    case serious
    case critical
    case unknown

    init(_ state: ProcessInfo.ThermalState) {
        switch state {
        case .nominal: self = .nominal
        case .fair: self = .fair
        case .serious: self = .serious
        case .critical: self = .critical
        @unknown default: self = .unknown
        }
    }
}

public struct MemoryPressure: Codable, Equatable {
    public let pageSizeBytes: UInt64
    public let freeBytes: UInt64
    public let activeBytes: UInt64
    public let inactiveBytes: UInt64
    public let wiredBytes: UInt64
    public let compressedBytes: UInt64
    public let swapTotalBytes: UInt64
    public let swapUsedBytes: UInt64
    public let swapFreeBytes: UInt64
}

public struct HostHealthState: Codable, Equatable {
    public let timestamp: Date
    public let thermalState: ThermalState
    public let memory: MemoryPressure
}

/// Plain `.iso8601` truncates to whole seconds, which loses enough
/// precision to make round-tripped timestamps compare unequal to the
/// samples that produced them. Fractional-second ISO 8601 keeps millisecond
/// resolution on both sides of the encode/decode boundary.
private let telemetryDateFormatter: ISO8601DateFormatter = {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter
}()

public extension JSONEncoder {
    static var telemetryEncoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .custom { date, encoder in
            var container = encoder.singleValueContainer()
            try container.encode(telemetryDateFormatter.string(from: date))
        }
        return encoder
    }
}

public extension JSONDecoder {
    static var telemetryDecoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let raw = try container.decode(String.self)
            guard let date = telemetryDateFormatter.date(from: raw) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "\(raw) is not a valid ISO 8601 timestamp"
                )
            }
            return date
        }
        return decoder
    }
}

public extension HostHealthState {
    func jsonData(prettyPrinted: Bool = false) throws -> Data {
        let encoder = JSONEncoder.telemetryEncoder
        if prettyPrinted {
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        }
        return try encoder.encode(self)
    }
}

/// Reads hardware health signals directly from the Mach host port and BSD
/// sysctl tree. No shell-outs to `top`, `vm_stat`, or `powermetrics`: those
/// tools read the same kernel counters through a fork/exec and text-parse
/// round trip, which is both slower and one output-format change away from
/// silently breaking a scheduler.
public enum HostTelemetryProbe {

    public static func sample() throws -> HostHealthState {
        let thermal = ThermalState(ProcessInfo.processInfo.thermalState)
        let memory = try sampleMemory()
        return HostHealthState(timestamp: Date(), thermalState: thermal, memory: memory)
    }

    static func sampleMemory() throws -> MemoryPressure {
        var pageSize: vm_size_t = 0
        let pageSizeResult = host_page_size(mach_host_self(), &pageSize)
        guard pageSizeResult == KERN_SUCCESS else {
            throw HostTelemetryError.machCallFailed("host_page_size", pageSizeResult)
        }

        var vmStats = vm_statistics64()
        var count = mach_msg_type_number_t(
            MemoryLayout<vm_statistics64>.stride / MemoryLayout<integer_t>.stride
        )
        let vmResult = withUnsafeMutablePointer(to: &vmStats) { statsPointer -> kern_return_t in
            statsPointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { rebound in
                host_statistics64(mach_host_self(), HOST_VM_INFO64, rebound, &count)
            }
        }
        guard vmResult == KERN_SUCCESS else {
            throw HostTelemetryError.machCallFailed("host_statistics64", vmResult)
        }

        let page = UInt64(pageSize)
        let swap = try sampleSwap()

        return MemoryPressure(
            pageSizeBytes: page,
            freeBytes: UInt64(vmStats.free_count) * page,
            activeBytes: UInt64(vmStats.active_count) * page,
            inactiveBytes: UInt64(vmStats.inactive_count) * page,
            wiredBytes: UInt64(vmStats.wire_count) * page,
            compressedBytes: UInt64(vmStats.compressor_page_count) * page,
            swapTotalBytes: swap.total,
            swapUsedBytes: swap.used,
            swapFreeBytes: swap.avail
        )
    }

    /// `vm.swapusage` reports `xsw_usage` fields already in bytes, not pages.
    static func sampleSwap() throws -> (total: UInt64, used: UInt64, avail: UInt64) {
        var usage = xsw_usage()
        var size = MemoryLayout<xsw_usage>.stride
        let result = sysctlbyname("vm.swapusage", &usage, &size, nil, 0)
        guard result == 0 else {
            throw HostTelemetryError.sysctlFailed("vm.swapusage", errno)
        }
        return (usage.xsu_total, usage.xsu_used, usage.xsu_avail)
    }
}
