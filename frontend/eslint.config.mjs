import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  globalIgnores([".next/**", "node_modules/**"]),
  ...nextVitals,
  {
    // Next 16 adds this optimization diagnostic. Retain visibility on the
    // existing effect-driven loaders; changing player/session state deserves
    // its own behavioral tests. New components retain the default error gate.
    files: [
      "components/account-panel.tsx", "components/community-panel.tsx",
      "components/continue-watching-block.tsx", "components/global-search.tsx",
      "components/language-switcher.tsx", "components/library-view.tsx",
      "components/profile-identity.tsx", "components/provider-player.tsx",
      "components/schedule-board.tsx", "components/schedule-strip.tsx",
      "components/title-actions.tsx", "components/watch-space.tsx",
    ],
    rules: { "react-hooks/set-state-in-effect": "warn" },
  },
]);
