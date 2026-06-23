/**
 * Componente radice: monta il RouterProvider di React Router v6.
 *
 * Perché un componente separato invece di mettere RouterProvider direttamente in main.tsx:
 *   - Separa il "wiring" dell'albero React (main.tsx) dalla scelta del router.
 *   - In futuro, se si volesse wrappare ulteriori provider DENTRO il router
 *     (es. un layout context), lo si fa qui senza toccare main.tsx.
 *   - Facilita i test: si può montare `<App />` in isolamento con un MemoryRouter.
 *
 * `RouterProvider` è l'entrypoint di React Router v6 (data router). Riceve un
 * oggetto `router` creato con `createBrowserRouter`: gestisce la history API del
 * browser (pushState / popState) e la navigazione dichiarativa via `<Link>` /
 * `useNavigate`. A differenza del vecchio `<BrowserRouter>`, il data router
 * supporta il "data loading" (loader/action) nativo di React Router 6.4+.
 */
import { RouterProvider } from "react-router-dom";

import { router } from "@/app/router";

function App() {
  return <RouterProvider router={router} />;
}

export default App;
