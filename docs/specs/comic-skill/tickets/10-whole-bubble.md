# 10 A rough box still clears its bubble

**Status.** done. The write result no longer names the items cleared whole (2026-10-18, `docs/specs/comic-scripts/`): the skill never told the bot what the list meant, and the bot sees the cleared bubble in the pictures it checks.

**What to build.** `scripts/comic/lettering/snap.py`: when a box points into a closed bubble (a light region not touching the page edge, under a size cap) that holds no other item's box, every letter line in the bubble is erased and the English goes in the bubble's own space. The write result names each item this applied to.

**Checks.** A unit test with gemma's 136.jpg box (125 px off): every Malay line is erased. Two items in one joined bubble keep today's behaviour.

**Blocked by.** 09
