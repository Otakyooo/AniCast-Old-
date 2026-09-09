import { NextRequest, NextResponse } from "next/server";
import { contentSecurityPolicy } from "./lib/csp";

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname !== "/" && request.nextUrl.pathname.endsWith("/")) {
    // NextURL retains its incoming trailingSlash metadata when cloned; a plain
    // URL is needed or serialization adds the removed slash back again.
    const canonical = new URL(request.url);
    canonical.pathname = canonical.pathname.replace(/\/+$/, "");
    return NextResponse.redirect(canonical, 308);
  }
  const nonce = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(24))));
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development");
  const headers = new Headers(request.headers);
  // Overwrite both values: accepting incoming nonce/CSP headers defeats isolation.
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = {
  matcher: ["/((?!api/|staff|static/|_next/).*)"],
};
