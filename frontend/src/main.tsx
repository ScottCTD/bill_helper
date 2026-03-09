import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { NotificationProvider } from "./components/ui/notification-center";
import { PrincipalSessionProvider } from "./features/session";
import "./styles.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <PrincipalSessionProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </PrincipalSessionProvider>
      </NotificationProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
