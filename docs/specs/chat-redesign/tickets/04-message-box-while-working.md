# 04 The message box shows a moving bar and one button

**Status:** done

**What to build.**

- `frontend/components/conversation/Composer.tsx`: while `running`, a thin bar moves along the box's top edge. One button shows Stop while the box is empty during a turn, and Send otherwise. Stop turns dark ink, not red. The placeholder while running reads "Reply, and it is answered after this turn".
- `frontend/app/globals.css` gains the bar's keyframes. Under reduced motion, the bar stays still.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- By hand, with the drive-cell-harness skill: send a message. The bar moves and the one button is Stop. Clicking it stops the turn.
- By hand: during a turn, type a word. The button becomes Send. Send it, and it is queued as today.
- By hand: with Reduce motion on in macOS settings, the bar shows but does not move.

**Blocked by.** none
