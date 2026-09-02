import { jsonLdScript } from "../lib/seo";
import { absoluteUrl } from "../lib/site";

/**
 * schema.org BreadcrumbList payload; `items` go from the broadest ancestor to
 * the current page. Rendered invisibly — search engines only.
 */
export function BreadcrumbsJsonLd({ items }: { items: Array<{ name: string; href: string }> }) {
  const data = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.href),
    })),
  };
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(data) }} />;
}
