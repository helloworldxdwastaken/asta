// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AstaMacApp",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "AstaAPIClient", targets: ["AstaAPIClient"]),
        .executable(name: "AstaMacApp", targets: ["AstaMacApp"]),
    ],
    targets: [
        .target(
            name: "AstaAPIClient",
            path: "Sources/AstaAPIClient"
        ),
        .executableTarget(
            name: "AstaMacApp",
            dependencies: ["AstaAPIClient"],
            path: "Sources/AstaMacApp"
        ),
        .testTarget(
            name: "AstaMacAppTests",
            dependencies: ["AstaMacApp", "AstaAPIClient"],
            path: "Tests/AstaMacAppTests"
        ),
    ]
)
