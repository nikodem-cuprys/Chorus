import type { ReactNode } from "react";
import { t } from "./i18n";
import { Link } from "./router";

/** The header every screen shares. */
export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="page">
      <header className="top">
        <Link to="/" className="brand">
          {t("app.name")}
        </Link>
        <nav className="nav">
          <Link to="/">{t("nav.library")}</Link>
          <Link to="/import">{t("nav.import")}</Link>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
