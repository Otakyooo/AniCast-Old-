import Link from "next/link";
import { SiteHeader, type NavSection } from "./site-header";
import { SiteFooter } from "./site-footer";

interface PageShellProps {
  active: NavSection;
  /** Renders the sticky back link row used by detail pages. */
  back?: { href: string; label: string };
  /** Optional page heading block rendered above the content. */
  heading?: { eyebrow?: string; title?: string; subtitle?: string };
  children: React.ReactNode;
}

/**
 * Single owner of the page frame: global header, content width and the
 * optional back link. Pages render only their own content, so the shell markup
 * exists exactly once per route. Navigation lives in the header at every
 * breakpoint -- on phones it moves to a second header row.
 */
export async function PageShell({ active, back, heading, children }: PageShellProps) {
  const hasHeading = Boolean(heading?.eyebrow || heading?.title || heading?.subtitle);

  return (
    <div className="shell">
      <SiteHeader active={active} />
      <main className="content">
        {back && (
          <div className="page-back">
            <Link className="back-link" href={back.href}>← {back.label}</Link>
          </div>
        )}
        {hasHeading && (
          <div className="page-heading">
            {heading?.eyebrow && <p className="eyebrow">{heading.eyebrow}</p>}
            {heading?.title && <h1>{heading.title}</h1>}
            {heading?.subtitle && <p className="muted">{heading.subtitle}</p>}
          </div>
        )}
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
