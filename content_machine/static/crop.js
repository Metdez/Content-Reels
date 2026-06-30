/* Shared crop math — single source of truth for the frontend.
   computeCrop mirrors render.compute_crop EXACTLY (same rounding, same
   width-vs-height branch, same even-dimension truncation). Locked to the
   Python renderer by tests/test_crop_parity.py.
   Exposed as window.CMCrop in the browser and module.exports under Node. */
(function () {
  /* Python's round() rounds half-to-even (banker's rounding); JS Math.round
     rounds half-up. compute_crop relies on Python round(), so we must mirror it
     here or the box drifts by 1px on .5 boundaries (caught by the parity test).
     Inputs are the same IEEE-754 doubles CPython sees, so an exact .5 compare is
     safe. */
  function rnd(v) {
    const f = Math.floor(v), d = v - f;
    if (d < 0.5) return f;
    if (d > 0.5) return f + 1;
    return (f % 2 === 0) ? f : f + 1;   // exactly .5 -> nearest even
  }

  /* ---- crop math: mirrors render.compute_crop exactly (zoom + x/y pan) ---- */
  function computeCrop(sw, sh, aspect, xoff, zoom, yoff) {
    zoom = Math.max(1, parseFloat(zoom) || 1); xoff = parseFloat(xoff) || 0; yoff = parseFloat(yoff) || 0;
    const [tw, th] = aspect.split(":").map(Number);
    const tar = tw / th, sar = sw / sh;
    let bw, bh;
    if (tar <= sar) { bh = sh; bw = rnd(sh * tar); }   // width-limited
    else { bw = sw; bh = rnd(sw / tar); }              // height-limited
    let cw = Math.min(sw, rnd(bw / zoom)), ch = Math.min(sh, rnd(bh / zoom));
    const sx = sw - cw, sy = sh - ch;
    let x = rnd(sx / 2 + Math.max(-1, Math.min(1, xoff)) * sx / 2);
    let y = rnd(sy / 2 + Math.max(-1, Math.min(1, yoff)) * sy / 2);
    x = Math.max(0, Math.min(sx, x)); y = Math.max(0, Math.min(sy, y));
    cw -= cw % 2; ch -= ch % 2;
    return { x, y, w: cw, h: ch, sx, sy };
  }

  /* Draw the highlighted crop box over the source video (% of source dims). */
  function drawBox(box, tag, sw, sh, aspect, xoff, zoom, yoff) {
    if (!sw || !sh) { box.style.display = 'none'; return; } box.style.display = 'block';
    const c = computeCrop(sw, sh, aspect, xoff, zoom, yoff);
    box.style.left = (c.x / sw * 100) + '%'; box.style.width = (c.w / sw * 100) + '%';
    box.style.top = (c.y / sh * 100) + '%'; box.style.height = (c.h / sh * 100) + '%';
    if (tag) tag.textContent = aspect;
  }

  /* Live WYSIWYG: draw the cropped/zoomed/panned region of the (single) source
     video onto a canvas every frame, so the output preview plays in sync with
     the source instead of freezing on frame 0. crop aspect == output aspect, so
     the crop region maps exactly onto the output frame.
     Source dims (srcW/srcH) come from the server payload (source_dims); the
     video intrinsic dims are only a fallback when source_dims is missing. */
  function drawOut(frame, cv, srcW, srcH, video, aspect, tf, cap) {
    const [tw, th] = aspect.split(":").map(Number);
    const CAP = cap || 560;                  // cap height so tall 9:16 isn't enormous
    // Size from the STABLE parent column width, never from frame.clientWidth —
    // reading the frame's own (mutated) width fed a clamp<->unclamp oscillation
    // that made the preview flash every animation frame.
    const avail = (frame.parentElement && frame.parentElement.clientWidth) || frame.clientWidth || 0;
    if (!avail) return;
    let fw = avail, fh = fw * th / tw;
    if (fh > CAP) { fh = CAP; fw = CAP * tw / th; }   // clamp tall ratios by height
    fw = Math.round(fw); fh = Math.round(fh);
    if (frame.style.width !== fw + 'px') frame.style.width = fw + 'px';   // guarded: no per-frame reflow once settled
    if (frame.style.height !== fh + 'px') frame.style.height = fh + 'px';
    if (cv.width !== fw) cv.width = fw; if (cv.height !== fh) cv.height = fh;
    const ctx = cv.getContext('2d');
    const vw = srcW || (video && video.videoWidth), vh = srcH || (video && video.videoHeight);
    if (!vw || !vh) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, cv.width, cv.height); return; }
    const c = computeCrop(vw, vh, aspect, tf.x, tf.zoom, tf.y);
    try { ctx.drawImage(video, c.x, c.y, c.w, c.h, 0, 0, cv.width, cv.height); }
    catch (e) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, cv.width, cv.height); }
  }

  const API = { computeCrop, drawBox, drawOut };
  if (typeof window !== 'undefined') window.CMCrop = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
