import SwiftUI

struct OnboardingView: View {
    @ObservedObject var composition: AppComposition
    @State private var baseURL = ""
    @State private var principalName = ""
    @State private var isConnecting = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Connect Bill Helper")
                            .font(.largeTitle.weight(.bold))
                        Text("This iPhone client uses the existing development-principal backend. Enter the API base URL and the principal name you want to use for this session.")
                            .font(.body)
                            .foregroundStyle(.secondary)
                    }

                    VStack(alignment: .leading, spacing: 14) {
                        TextField("Backend URL", text: $baseURL)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                            .textFieldStyle(.roundedBorder)

                        TextField("Principal name", text: $principalName)
                            .textInputAutocapitalization(.never)
                            .textFieldStyle(.roundedBorder)

                        if let onboardingError = composition.onboardingError, !onboardingError.isEmpty {
                            Label(onboardingError, systemImage: "exclamationmark.triangle.fill")
                                .font(.footnote)
                                .foregroundStyle(.red)
                        }

                        Button {
                            Task {
                                isConnecting = true
                                await composition.connect(baseURLString: baseURL, principalName: principalName)
                                isConnecting = false
                            }
                        } label: {
                            Label(isConnecting ? "Connecting…" : "Test connection", systemImage: "network")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isConnecting)
                    }
                    .padding(18)
                    .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Default local URL")
                            .font(.headline)
                        Text(composition.activeAPIBaseURL.absoluteString)
                            .font(.footnote.monospaced())
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(20)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Onboarding")
        }
        .onAppear {
            if baseURL.isEmpty {
                baseURL = composition.activeAPIBaseURL.absoluteString
            }
            if principalName.isEmpty {
                principalName = composition.sessionStore.currentSession?.currentUserName ?? "admin"
            }
        }
    }
}
