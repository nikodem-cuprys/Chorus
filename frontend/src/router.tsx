import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

// A small router on the History API. The backend serves the app for every non-API path,
// so any of these can be opened directly.

const listeners = new Set<() => void>();

export function navigate(path: string): void {
  window.history.pushState(null, "", path);
  listeners.forEach((listener) => listener());
}

export function usePath(): string {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const update = () => setPath(window.location.pathname);
    listeners.add(update);
    window.addEventListener("popstate", update);
    return () => {
      listeners.delete(update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  return path;
}

export function Link({ to, className, children }: { to: string; className?: string; children: ReactNode }) {
  const follow = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  };
  return (
    <a href={to} className={className} onClick={follow}>
      {children}
    </a>
  );
}
