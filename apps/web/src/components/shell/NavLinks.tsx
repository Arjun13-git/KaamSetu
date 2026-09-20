"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

const LINKS = [
  { href: "/", label: "Board", match: (p: string) => p === "/" || p.startsWith("/jobs") || p.startsWith("/requests") },
  { href: "/customers", label: "Customers", match: (p: string) => p.startsWith("/customers") },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex items-center gap-1">
      {LINKS.map((link) => {
        const active = link.match(pathname);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              active ? "bg-brand-tint text-brand-strong" : "text-ink-2 hover:bg-sunken hover:text-ink",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
