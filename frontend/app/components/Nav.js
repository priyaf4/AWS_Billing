"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const LINKS = [
  { href: "/chat", label: "Chat" },
  { href: "/Filestorage", label: "File Storage" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST" });
    router.replace("/");
    router.refresh();
  }

  return (
    <nav className="nav">
      <div className="nav-links">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
            {l.label}
          </Link>
        ))}
      </div>
      <button className="secondary" onClick={handleLogout}>
        Logout
      </button>
    </nav>
  );
}
