"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

const LINKS = [
  { href: "/", label: "Board", match: (p: string) => p === "/" || p.startsWith("/jobs") || p.startsWith("/requests") },
  { href: "/customers", label: "Customers", match: (p: string) => p.startsWith("/customers") },
  { href: "/technicians", label: "Technicians", match: (p: string) => p.startsWith("/technicians") },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex items-center gap-0.5 sm:gap-1">
      {LINKS.map((link) => {
        const active = link.match(pathname);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-lg py-1.5 text-sm font-medium whitespace-nowrap transition-colors sm:px-3 max-sm:px-1.5",
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
