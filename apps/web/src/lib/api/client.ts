import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type User = components["schemas"]["UserOut"];
export type Role = components["schemas"]["Role"];

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // Resolve o fetch a cada chamada, e não na criação do cliente.
  fetch: (request) => globalThis.fetch(request),
});
