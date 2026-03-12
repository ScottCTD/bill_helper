import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";

import { NotificationProvider } from "../components/ui/notification-center";
import { AuthProvider } from "../features/auth";

export function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      },
      mutations: {
        retry: false
      }
    }
  });

  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <NotificationProvider>
          <AuthProvider>{ui}</AuthProvider>
        </NotificationProvider>
      </QueryClientProvider>
    )
  };
}
