# Kerjo UI system — Compact workspace

## Direction
Kerjo is a **job-discovery workbench**: compact, calm, document-first and dense without crowded card chrome. The visual references and color/spacing primitives are derived from `howlil/howlil-app`'s `src/styles/global.css`; Kerjo defines app-specific semantic rules in its own code.

## Source of truth

| Layer | File | Responsibility |
|---|---|---|
| Foundations | `apps/web/src/styles/tokens.css` | light/dark colors, type, 4px spacing scale, radius, motion, app dimensions |
| Base & shared patterns | `apps/web/src/app.css` | resets, panel sections, forms, compact record layout, inspector details |
| Primitives | `apps/web/src/components/ui` | Button, Badge, CompanyAvatar |
| Feature components | `apps/web/src/components/jobs` | FilterSidebar, JobCard, JobInspector |
| Workspace template | `apps/web/src/components/layout/WorkspaceShell.svelte` | edge-to-edge three-pane layout, scroll containment, mobile drawers |
| Controller | `apps/web/src/App.svelte` | API requests, filtering, selected job, modal, local preferences |

Do not add a new app-wide palette in a page component. If a property is shared by multiple features, give it a semantic token/class or a small reusable component.

## Workspace template

```svelte
<WorkspaceShell filterOpen={filterOpen} detailOpen={detailOpen} onDismiss={closeOverlays}>
  {#snippet header()}<AppHeader />{/snippet}
  {#snippet filters()}<FilterSidebar {...filterProps}/>{/snippet}
  {#snippet results()}<JobResults {...resultProps}/>{/snippet}
  {#snippet inspector()}<JobInspector {...inspectorProps}/>{/snippet}
</WorkspaceShell>
```

The named snippets are replaceable presentation regions. The template owns the panel geometry. The controller owns data, user actions, API persistence, and overlays.

### Layout contract
- **0px outer padding**: the left filter panel touches the left viewport edge, the inspector touches the right edge.
- 56px app bar, 54px filter/search bar, 50px results-summary row.
- 220px left panel / fluid result area / 300px inspector on typical desktop; semantic widths adjusted by breakpoint.
- Panels scroll **independently**; prevent document-level overflow.
- Use only 1px divider lines for panel and record boundaries.
- Result records: two columns by default, one column at compact phone widths; manual list toggle remains available.
- At widths ≤900px, detail is a drawer. At widths ≤620px, filters also become a drawer.
- Mobile overlays must have dismissal, keyboard focus visibility, and Escape behavior if future modal routing is added.

### Colors
Use `--color-page #FEFEFE`, `--color-surface #F7F7F7`, `--color-text-heading #121212`, `--color-text-secondary #626262`, `--color-accent #9BB1FF`. Dark mode mirrors the Howlil neutral scale (`#080808` page, `#121212` surface, `#262626` borders). Selection uses `--color-selected` and a 3px inset accent rail; `--color-success` is for positive states, not routine buttons.

### Type and spacing
Body uses system sans; timestamps and eyebrow labels use mono. The 4px scale is encoded by `--space-1/2/3/4/5/6/8`. Typical: 8px related controls, 12px subgroup, 16px panel interior, 20px detail title. Do not add 8px external workspace gutters.

### Component recipes
- `Button`: `variant='neutral'|'primary'`; slots for text and Icon; primary is reserved for the dominant action.
- `Badge`: `tone='neutral'|'accent'|'positive'`; never stack black pills across a record.
- `CompanyAvatar`: logo with initials fallback; consumes `company`, `logo`, `size`.
- `JobCard`: scan-friendly record with independent select and save controls. It never fetches data.
- `FilterSidebar`: purely controlled. Changes go to `onFilter(type,value)` in App.
- `JobInspector`: job facts, chronology and source links. No unverified 'live' status.
- `WorkspaceShell`: generic named-snippet template; no API logic inside it.

## Data & behavior contract
- All existing server filters remain mapped to `/api/jobs`; do not replace them with client-only filtering.
- Search input is debounced; stale response payloads must not replace newer filter results.
- Clicking a position opens detail and **does not** mark a new listing as read; explicit action calls `/api/jobs/:id/seen`.
- Saved searches for cronjob remain on existing `/api/searches` APIs.
- Per-job bookmark is a **local browser preference** (`kerjo:saved-job-ids`), *not* a server-side saved job. Do not promise cross-device synchronization.
- Dark mode uses `data-theme` on `<html>`; local preference key `kerjo:theme`.
- The source link opens the authentic provider URL, not a synthetic destination.

## Release checklist
1. `cd apps/web && npm ci && npm run build`
2. Test desktop 1440/1280/1024 and mobile 900/620/390 viewports; no horizontal scrollbar.
3. Verify each sidebar control maps to API query parameters.
4. Verify duplicate/aggregated job URLs and fallback logo behavior.
5. Verify keyboard select, seen action, modal submit, empty/loading/error states.
6. Verify dark mode contrast, reduced motion, and scroll isolation.

### Creating another workspace page
Start with `WorkspaceShell`, then supply header/filters/results/inspector snippets. Reuse existing UI primitives and tokens. Only create a new component when it has a distinct responsibility or repeatable behavior. Avoid introducing generic abstract factories or nested "design system" directories for one-off UI.
