import SwiftUI

@main
struct BillHelperApp: App {
    @StateObject private var composition = AppComposition.live()

    var body: some Scene {
        WindowGroup {
            AppRootView(composition: composition)
                .task {
                    await composition.restoreIfNeeded()
                }
        }
    }
}
