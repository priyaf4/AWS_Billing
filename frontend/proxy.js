import { NextResponse } from "next/server";
import { getSessionUser } from "./lib/session";

const PROTECTED = ["/chat", "/Filestorage"];

export function proxy(request) {
  const { pathname } = request.nextUrl;
  const user = getSessionUser(request);

  if (!user && PROTECTED.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  if (user && pathname === "/") {
    return NextResponse.redirect(new URL("/chat", request.url));
  }
  return NextResponse.next();
}

// API routes check the session themselves, so uploads are not buffered here.
export const config = {
  matcher: ["/", "/chat/:path*", "/Filestorage/:path*"],
};
