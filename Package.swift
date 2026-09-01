// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MacFleetMatrixTelemetry",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "MFMTelemetry", targets: ["MFMTelemetry"])
    ],
    targets: [
        .target(
            name: "MFMTelemetry",
            path: "src/mfm/Telemetry"
        ),
        .testTarget(
            name: "mfmTests",
            dependencies: ["MFMTelemetry"],
            path: "tests/mfmTests"
        )
    ]
)
