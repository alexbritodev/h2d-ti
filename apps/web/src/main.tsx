import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { applyTheme, getStoredTheme } from "@/lib/theme";
import { createAppRouter } from "@/router";

import "@/styles/app.css";

applyTheme(getStoredTheme());

const queryClient = new QueryClient();
const router = createAppRouter(queryClient);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
