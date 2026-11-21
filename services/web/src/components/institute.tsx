import { namePart } from "@/lib/names";

/** Readable institute name; the full MCC display name stays available as a title and to screen readers. */
export function InstituteName({ full, withAddress = false }: { full: string; withAddress?: boolean }) {
  const name = namePart(full);
  return (
    <>
      <span title={full}>{name}</span>
      {withAddress && name !== full && <span className="mt-0.5 block text-xs font-normal text-label">{full}</span>}
    </>
  );
}
