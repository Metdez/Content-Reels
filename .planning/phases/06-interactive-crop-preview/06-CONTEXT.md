# Phase 6: Interactive Crop Preview Before Run — Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (autonomous, discuss skipped)

<domain>
## Phase Boundary

Insert an interactive preview/configure step between upload and pipeline start.
Today `/upload` immediately spawns the pipeline with a blind numeric x_offset.
After this phase, upload stages the source and lands the user on a preview page
where they position the crop with a live overlay + slider, set run options, and
click Run to start transcribe→select→render with the chosen offset.
</domain>

<decisions>
## Implementation Decisions

- Upload moves the file into `data/<id>/source<ext>` (previewable via `/media`),
  probes dimensions, writes manifest with `awaiting_run: true` + `source_dims`,
  and does NOT start the pipeline.
- `/api/job/{id}/run` (POST) receives x_offset + run options, flips
  `awaiting_run` off, and starts the background pipeline against the staged source.
- Preview UI: `<video>` of the source with an absolutely-positioned crop-box
  overlay sized in % of source dims, an aspect toggle (9:16 / 1:1 / 16:9), and an
  x_offset range slider. Crop math mirrors `render.compute_crop` exactly.
- Run options (max_clips, model, captions) move from index to the preview page so
  all run params are chosen alongside the crop.
- Index becomes: file picker → "Upload & preview" + library.
</decisions>

<specifics>
## Success Criteria
1. Upload stages source + shows preview; pipeline does NOT auto-start.
2. Crop-box overlay moves live with the slider for 9:16 and 1:1.
3. Run button starts the pipeline with chosen x_offset; progress displays as before.
4. Browser crop math matches render.compute_crop.
</specifics>
