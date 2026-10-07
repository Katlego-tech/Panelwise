// One shot's card on the board (web.md §4.3; storyboard.css `.card`): its frame or the frame's
// state, the shot id and camera, the verdict, who is in it, and its verbatim source and span.

import { SpanRef } from "@/components/shared/SpanRef";
import { Verdict } from "@/components/shared/Verdict";
import type { FrameView, ShotView } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { cameraText, cardState, whoText } from "./cards";
import { FrameMedia, MEDIA_BOX, SourceText } from "./FrameMedia";
import { lineColour } from "./lined";

/** No image yet: the hatched panel, with the pencil dots while a render or audit runs. */
function PendingMedia({ text, busy }: { text: string; busy: boolean }) {
  return (
    <div className={MEDIA_BOX}>
      <div className="grid h-full place-content-center justify-items-center gap-2.5 bg-[repeating-linear-gradient(135deg,#f1f3f1_0_10px,#e9ecea_10px_20px)] text-sm text-ink-2">
        {busy && (
          <span
            aria-hidden
            className="h-2 w-11 animate-pulse bg-[radial-gradient(circle,var(--color-pencil)_3px,transparent_3.5px)] bg-size-[14px_8px] bg-repeat-x"
          />
        )}
        <p className="m-0">{text}</p>
      </div>
    </div>
  );
}

/** A frame that won't be shown: the source once, its span, and why (web.md §4.3). */
function TextCard({ shot, why }: { shot: ShotView; why: string }) {
  return (
    <div className={MEDIA_BOX}>
      <div className="flex h-full flex-col gap-1.5 border border-b-0 border-dashed border-withheld bg-paper px-4.5 py-4">
        <p className="m-0">
          <SourceText shot={shot} />
        </p>
        <p className="m-0">
          <SpanRef span={shot.span} />
        </p>
        <p className="mt-auto mb-0 text-[13px] font-bold text-withheld">{why}</p>
      </div>
    </div>
  );
}

// "Try another render" joins the withheld card with its action in T021 (web.md §4.3, staged).
const WithheldCard = TextCard;
// T021 adds the restart sweep's wording beside the renderer's (web.md §4.3, staged).
const RenderFailedCard = TextCard;

export function FrameCard({
  shot,
  k,
  frame,
  on,
  onHighlight,
}: {
  shot: ShotView;
  k: number;
  frame: FrameView | undefined;
  on: boolean;
  onHighlight: (id: string | null) => void;
}) {
  const { media, verdict, notes } = cardState(frame);
  const textCard = media.kind === "withheld" || media.kind === "failed";
  return (
    // Focused by its shot line, never tabbed to or clicked: T045's sheet makes it a button
    // (web.md §4.3, staged).
    <article
      id={`shot-${shot.id}`}
      tabIndex={-1}
      data-state={frame?.state ?? "none"}
      onMouseEnter={() => onHighlight(shot.id)}
      onMouseLeave={(event) => {
        // A focused card stays highlighted: only its blur lets go.
        if (document.activeElement !== event.currentTarget) onHighlight(null);
      }}
      onFocus={() => onHighlight(shot.id)}
      onBlur={() => onHighlight(null)}
      className={cn("scroll-mt-4 border-t-4 bg-paper shadow-page", on && "outline-2 outline-offset-[3px] outline-pencil")}
      style={{ borderTopColor: lineColour(k) }}
    >
      {media.kind === "image" && <FrameMedia url={media.url} shot={shot} />}
      {media.kind === "pending" && <PendingMedia text={media.text} busy={media.busy} />}
      {media.kind === "withheld" && <WithheldCard shot={shot} why={media.why} />}
      {media.kind === "failed" && <RenderFailedCard shot={shot} why={media.why} />}
      <header className="flex flex-wrap items-center gap-x-2.5 gap-y-1 px-3.5 pt-2.5 *:whitespace-nowrap">
        <span className="font-display text-xl leading-none font-extrabold">{shot.id}</span>
        <span className="text-[13px] text-ink-2">{cameraText(shot)}</span>
        {verdict && (
          <span className="ml-auto">
            <Verdict tone={verdict.tone}>{verdict.label}</Verdict>
          </span>
        )}
      </header>
      <p className={cn("mx-3.5 mt-1.5 text-[13px] font-bold", textCard ? "mb-3.5" : "mb-0")}>{whoText(shot)}</p>
      {!textCard && (
        <p className="mx-3.5 mt-1.5 mb-3.5 text-[13px]">
          <SourceText shot={shot} /> <SpanRef span={shot.span} />
        </p>
      )}
      {notes.map((note) => (
        <p key={note} className="mx-3.5 -mt-2 mb-3.5 text-[13px] text-warn">
          {note}
        </p>
      ))}
    </article>
  );
}
