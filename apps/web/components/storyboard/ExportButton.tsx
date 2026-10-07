// Export PDF, in the bar (web.md §4.3; storyboard.png). Staged until T027 builds the PDF: always
// disabled, saying so. T027 adds the route and the "every frame has settled" rule.

import { useId } from "react";

import { Button } from "@/components/ui/button";

export const EXPORT_STAGED = "The PDF export isn't built yet";

export function ExportButton() {
  // A disabled button takes no focus, so the reason is also its description, not only a tooltip.
  const why = useId();
  return (
    <span title={EXPORT_STAGED}>
      <Button variant="bar" disabled aria-describedby={why}>
        Export PDF
      </Button>
      <span id={why} className="sr-only">
        {EXPORT_STAGED}
      </span>
    </span>
  );
}
