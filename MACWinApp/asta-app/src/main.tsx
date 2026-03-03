import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { initThemeListener } from "./lib/theme";

// Apply saved theme (system/light/dark) and listen for OS changes
initThemeListener();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
