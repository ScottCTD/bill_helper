/**
 * CALLING SPEC:
 * - Purpose: render the `main` React UI module.
 * - Inputs: callers that import `frontend/src/main.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `main`.
 * - Side effects: React rendering and user event wiring.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { NotificationProvider } from "./components/ui/notification-center";
import { AuthProvider } from "./features/auth";
import "./styles.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </NotificationProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
