import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const KEY = "neet-theme";

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function system(): Theme {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** Follows prefers-color-scheme until the user picks; the pick is remembered in localStorage. */
export function useTheme() {
  const [choice, setChoice] = useState<Theme | null>(stored);
  const [sys, setSys] = useState<Theme>(system);
  const theme = choice ?? sys;

  useEffect(() => {
    let mq: MediaQueryList | null = null;
    try {
      mq = window.matchMedia("(prefers-color-scheme: dark)");
    } catch {
      return;
    }
    const on = () => setSys(mq!.matches ? "dark" : "light");
    mq.addEventListener("change", on);
    return () => mq!.removeEventListener("change", on);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const toggle = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setChoice(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* storage unavailable: choice lasts for this page only */
    }
  }, [theme]);

  return { theme, toggle };
}
