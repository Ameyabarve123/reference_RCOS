import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const signedIn = request.cookies.get("rcos_auth")?.value === "1";
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/app") && !signedIn) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if ((pathname === "/login" || pathname === "/signup") && signedIn) {
    return NextResponse.redirect(new URL("/app", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
