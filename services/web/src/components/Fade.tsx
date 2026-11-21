import { type ComponentProps, lazy, Suspense } from "react";

// FadeContent pulls in gsap; keep it out of the first-load bundle. It is preloaded once the page is
// idle, so by the time an answer arrives the chunk is already here.
const load = () => import("@/components/FadeContent");
const FadeContent = lazy(load);
if (typeof window !== "undefined") {
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void) => void }).requestIdleCallback;
  (idle ?? ((cb: () => void) => setTimeout(cb, 300)))(() => void load());
}

/** Answer wrapper: fades in once the verified response is on screen (no motion under reduced-motion). */
export function Fade(props: ComponentProps<typeof FadeContent>) {
  return (
    <Suspense fallback={<div style={{ opacity: 0 }}>{props.children}</div>}>
      <FadeContent {...props} />
    </Suspense>
  );
}
