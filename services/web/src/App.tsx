import { FileCheck2, ListFilter, MessageSquareText, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { AskView } from "@/views/Ask";
import { EvidenceView } from "@/views/Evidence";
import { PredictorView } from "@/views/Predictor";

type View = "ask" | "predictor" | "evidence";
const NAV: { id: View; label: string; icon: typeof Sun }[] = [
  { id: "ask", label: "Ask", icon: MessageSquareText },
  { id: "predictor", label: "Predictor", icon: ListFilter },
  { id: "evidence", label: "Evidence", icon: FileCheck2 },
];
const CREDIT = "Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in";

const fromHash = (): View => {
  const h = window.location.hash.replace(/^#\/?/, "");
  return h === "predictor" || h === "evidence" ? h : "ask";
};

export default function App() {
  const [view, setView] = useState<View>(fromHash);
  const { theme, toggle } = useTheme();

  useEffect(() => {
    const on = () => setView(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const toggleButton = (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="inline-flex size-8 items-center justify-center rounded-md text-text-2 hover:bg-muted hover:text-foreground"
    >
      {theme === "dark" ? <Sun className="size-4" aria-hidden="true" /> : <Moon className="size-4" aria-hidden="true" />}
    </button>
  );

  const navItems = (compact: boolean) =>
    NAV.map(({ id, label, icon: Icon }) => (
      <a
        key={id}
        href={`#/${id}`}
        aria-current={view === id ? "page" : undefined}
        className={cn(
          "flex items-center gap-2.5 rounded-md text-sm",
          compact ? "px-3 py-1.5" : "px-3 py-2",
          view === id ? "bg-muted font-medium text-foreground" : "text-text-2 hover:bg-muted hover:text-foreground",
        )}
      >
        <Icon aria-hidden="true" className={cn("size-4", view === id ? "text-primary" : "text-label")} />
        {label}
      </a>
    ));

  return (
    <div className="min-h-dvh bg-background text-foreground md:flex">
      {/* Side panel (md and up) */}
      <aside className="hidden w-60 shrink-0 border-r border-border bg-surface md:block">
        <div className="sticky top-0 flex h-dvh flex-col">
        <div className="px-5 pt-6 pb-5">
          <p className="text-[15px] font-semibold leading-snug tracking-tight text-foreground">NEET.info</p>
          <p className="text-[13px] leading-snug text-text-2">Counselling Assistant</p>
        </div>
        <nav aria-label="Main" className="flex flex-col gap-0.5 px-3">
          {navItems(false)}
        </nav>
        <div className="mt-auto flex items-center justify-between border-t border-border px-5 py-3">
          <span className="text-xs text-label">NEET-UG 2025 · local</span>
          {toggleButton}
        </div>
        </div>
      </aside>

      {/* Top bar (phones) */}
      <header className="sticky top-0 z-10 border-b border-border bg-surface md:hidden">
        <div className="flex items-center justify-between px-4 pt-3">
          <p className="text-sm font-semibold text-foreground">
            NEET.info <span className="font-normal text-text-2">Counselling Assistant</span>
          </p>
          {toggleButton}
        </div>
        <nav aria-label="Main" className="flex gap-1 px-2 pt-2 pb-2">
          {navItems(true)}
        </nav>
      </header>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 pt-8 pb-16 sm:px-8 md:pt-16">
          {view === "ask" && <AskView />}
          {view === "predictor" && <PredictorView />}
          {view === "evidence" && <EvidenceView />}
        </main>
        <footer className="border-t border-border">
          <p className="mx-auto max-w-4xl px-4 py-4 text-xs text-label sm:px-8">{CREDIT}</p>
        </footer>
      </div>
    </div>
  );
}
