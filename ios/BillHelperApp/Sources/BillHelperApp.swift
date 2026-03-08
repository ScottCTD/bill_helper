import SwiftUI

@main
struct BillHelperApp: App {
    private let composition = AppComposition.live()

    var body: some Scene {
        WindowGroup {
            AppShellView(composition: composition)
        }
    }
}