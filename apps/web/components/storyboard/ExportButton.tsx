// Export PDF, in the bar (web.md §4.3; storyboard.png). Staged until T027 builds the PDF: always
// disabled, saying so. T027 adds the route and the "every frame has settled" rule.

import { Button } from "@/components/ui/button";

export const EXPORT_STAGED = "The PDF export isn't built yet";

export function ExportButton() {
  return (
    <span title={EXPORT_STAGED}>
      <Button variant="bar" disabled>
        Export PDF
      </Button>
    </span>
  );
}
